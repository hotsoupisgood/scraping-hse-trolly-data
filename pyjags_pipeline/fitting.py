import numpy as np
import pandas as pd
import pyjags
from pyjags.dic import dic_samples as _dic_samples
from pyjags import from_pyjags
import arviz as az


def fit_jags(model_string, data, monitor, chains=4, burnin=10000,
             sample=20000, adapt=1000, seed=None):
    """Compile, burn-in, and sample a JAGS model via pyjags.

    Uses threads=2, chains_per_thread=chains//2 to keep DIC working
    (pD needs >=2 chains per thread).

    Parameters
    ----------
    seed : int, optional
        RNG seed for reproducibility. pyjags derives independent per-chain
        seeds via numpy.random.SeedSequence.

    Returns
    -------
    samples : dict
        pyjags samples dict with shape (dim..., n_iter, n_chains) per key.
    model : pyjags.Model
        The compiled model object (needed for DIC).
    """
    cpt = max(chains // 2, 2)
    threads = max(chains // cpt, 1)

    model = pyjags.Model(
        code=model_string,
        data=data,
        chains=chains,
        adapt=adapt,
        threads=threads,
        chains_per_thread=cpt,
        seed=seed,
    )

    # burn-in
    model.sample(burnin, vars=[])

    # posterior samples
    samples = model.sample(sample, vars=monitor)

    return samples, model


def compute_dic(model, n_iter=20000):
    """Compute DIC from a fitted model.

    Returns
    -------
    dict with keys 'deviance', 'penalty', 'DIC'.
    """
    dic = _dic_samples(model, n_iter)
    return {
        'deviance': float(np.sum(dic.deviance)),
        'penalty': float(np.sum(dic.penalty)),
        'DIC': float(np.sum(dic.deviance) + np.sum(dic.penalty)),
    }


def flatten_samples(pyjags_samples, n_chains):
    """Convert pyjags samples dict to a flat DataFrame matching R's raw_samples.csv format.

    pyjags returns {param: array of shape (dim..., n_iter, n_chains)}.
    This produces columns like 'alpha[1]', 'alpha[2]', ..., 'phi', 'chain'
    with rows = n_iter * n_chains.
    """
    # collect all param columns
    param_data = {}  # {col_name: array of shape (n_iter, n_chains)}
    for param, arr in pyjags_samples.items():
        if arr.ndim == 3 and arr.shape[0] > 1:
            # vector param: shape (n_elem, n_iter, n_chains)
            n_elem = arr.shape[0]
            for i in range(n_elem):
                col = f'{param}[{i + 1}]'
                param_data[col] = arr[i]  # (n_iter, n_chains)
        elif arr.ndim == 3 and arr.shape[0] == 1:
            # scalar param returned as (1, n_iter, n_chains)
            param_data[param] = arr[0]
        else:
            # shouldn't happen with pyjags, but handle gracefully
            param_data[param] = arr.reshape(-1, n_chains) if arr.ndim > 2 else arr

    # sort columns alphabetically to match R's write.csv behaviour
    sorted_cols = sorted(param_data.keys())

    # build per-chain DataFrames, then concatenate
    chain_dfs = []
    for c in range(n_chains):
        chain_data = {col: param_data[col][:, c] for col in sorted_cols}
        df = pd.DataFrame(chain_data)
        df['chain'] = c + 1  # 1-indexed like R
        chain_dfs.append(df)

    return pd.concat(chain_dfs, ignore_index=True)


def compute_gelman(pyjags_samples):
    """Compute R-hat for all parameters using ArviZ.

    Returns DataFrame with columns: param, Point est.
    """
    idata = from_pyjags(pyjags_samples)
    rhat = az.rhat(idata)

    rows = []
    for var in rhat.data_vars:
        vals = np.atleast_1d(rhat[var].values)
        for i, r in enumerate(vals):
            label = f'{var}[{i + 1}]' if len(vals) > 1 else str(var)
            rows.append({
                'param': label,
                'Point est.': float(r),
            })

    return pd.DataFrame(rows)
