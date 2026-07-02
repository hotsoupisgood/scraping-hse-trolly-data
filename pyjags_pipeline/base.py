from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import data as _data
from . import fitting as _fitting
from . import diagnostics as _diag
from . import plotting as _plot
from . import significance as _sig


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_MODELS_ROOT = _PROJECT_ROOT / 'data' / 'models'

_DEFAULT_DATA_PATH = 'data/wide_weekly_scaledPer10k.csv'


def _resolve_output_dir(version: str, data_path: str) -> Path:
    """Compute output dir: data/models/{csv_stem}/{version}/"""
    stem = Path(data_path).stem
    d = _MODELS_ROOT / stem / version
    d.mkdir(parents=True, exist_ok=True)
    return d


@dataclass
class ModelResult:
    """Container for everything produced by a model run."""
    raw_df: pd.DataFrame
    pyjags_samples: dict
    dic: dict
    gelman: pd.DataFrame
    df_mu: pd.DataFrame
    df_mu_lower: pd.DataFrame
    df_mu_upper: pd.DataFrame
    df_fitted: pd.DataFrame
    df_residuals: pd.DataFrame
    df_std_resid: pd.DataFrame
    df_og: pd.DataFrame             # observed data (weeks as rows, regions as columns)
    regions: list[str]
    n_region: int
    n_weeks: int
    indicators: dict
    output_dir: Path = field(default=None)
    metadata: dict = field(default_factory=dict)


class BaseModel(ABC):

    # ------------------------------------------------------------------ #
    # Abstract — subclass MUST define these
    # ------------------------------------------------------------------ #

    @property
    @abstractmethod
    def version(self) -> str:
        """e.g. 'v3.1'"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable, e.g. 'Partial Pooling Alpha'"""

    @property
    @abstractmethod
    def jags_model_string(self) -> str:
        """The JAGS model block as a raw Python string."""

    @property
    @abstractmethod
    def monitor_params(self) -> list[str]:
        """Parameter names to monitor during sampling.
        Must include 'mu', 'fullmod', and 'resid' so that _build_result
        can extract them directly from the JAGS posterior."""

    @abstractmethod
    def jags_data(self, y, n_region, n_weeks, regions) -> dict:
        """Build the data dict passed to pyjags.Model()."""

    # ------------------------------------------------------------------ #
    # Optional overrides
    # ------------------------------------------------------------------ #

    def extra_significance_tests(self, result, output_dir):
        pass

    def extra_plots(self, result, plot_dir):
        pass

    # ------------------------------------------------------------------ #
    # Matrix extraction helpers (JAGS-monitored 2-D nodes)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _extract_matrix_summary(arr, regions):
        """Return (df_mean, df_lower, df_upper) from a monitored 2-D JAGS node.

        pyjags returns shape (n_region, n_weeks, n_iter, n_chains).
        Outputs are DataFrames of shape (n_weeks, n_region).
        """
        n_region, n_weeks, n_iter, n_chains = arr.shape
        flat = arr.reshape(n_region, n_weeks, -1)   # (n_region, n_weeks, n_samples)
        mean  = flat.mean(axis=2).T                  # (n_weeks, n_region)
        lower = np.quantile(flat, 0.025, axis=2).T
        upper = np.quantile(flat, 0.975, axis=2).T
        return (pd.DataFrame(mean,  columns=regions),
                pd.DataFrame(lower, columns=regions),
                pd.DataFrame(upper, columns=regions))

    @staticmethod
    def _extract_matrix_mean(arr, regions):
        """Return a posterior-mean DataFrame from a monitored 2-D JAGS node.

        pyjags returns shape (n_region, n_weeks, n_iter, n_chains).
        Output is a DataFrame of shape (n_weeks, n_region).
        """
        n_region, n_weeks, n_iter, n_chains = arr.shape
        flat = arr.reshape(n_region, n_weeks, -1)
        mean = flat.mean(axis=2).T                   # (n_weeks, n_region)
        return pd.DataFrame(mean, columns=regions)

    # ------------------------------------------------------------------ #
    # Pipeline methods
    # ------------------------------------------------------------------ #

    def _load_data(self, data_path):
        """Load observed data and build indicators."""
        df_og_wide, regions, n_region, n_weeks, y_matrix = _data.load_observed(data_path)
        # transpose: weeks as rows, regions as columns (using known region names)
        df_og = pd.DataFrame(df_og_wide.values.T.astype(float), columns=regions)
        indicators = _data.build_event_indicators(n_weeks, regions)
        return df_og, regions, n_region, n_weeks, y_matrix, indicators

    def fit(self, data_path=_DEFAULT_DATA_PATH,
            chains=4, burnin=10000, sample=20000, adapt=1000, seed=None):
        """Full pipeline: fit -> diagnose -> reconstruct -> residuals -> export."""
        output_dir = _resolve_output_dir(self.version, data_path)
        df_og, regions, n_region, n_weeks, y_matrix, indicators = self._load_data(data_path)

        print(f'[{self.version}] Fitting {self.name}...')
        data_dict = self.jags_data(y_matrix, n_region, n_weeks, regions)
        pyjags_samples, model = _fitting.fit_jags(
            self.jags_model_string, data_dict, self.monitor_params,
            chains=chains, burnin=burnin, sample=sample, adapt=adapt, seed=seed,
        )

        print(f'[{self.version}] Computing DIC...')
        dic = _fitting.compute_dic(model, n_iter=sample)

        # Pop 2-D matrix nodes immediately — shape (n_region, n_weeks, n_iter, n_chains)
        # would break both compute_gelman and flatten_samples, which expect 1-D or scalar nodes.
        mu_arr    = pyjags_samples.pop('mu',      None)
        fm_arr    = pyjags_samples.pop('fullmod', None)
        resid_arr = pyjags_samples.pop('resid',   None)

        print(f'[{self.version}] Computing Gelman-Rubin...')
        gelman = _fitting.compute_gelman(pyjags_samples)

        raw_df = _fitting.flatten_samples(pyjags_samples, chains)

        return self._build_result(raw_df, pyjags_samples, dic, gelman,
                                  df_og, regions, n_region, n_weeks, indicators,
                                  output_dir,
                                  mu_arr=mu_arr, fm_arr=fm_arr, resid_arr=resid_arr)

    def _build_result(self, raw_df, pyjags_samples, dic, gelman,
                      df_og, regions, n_region, n_weeks, indicators, output_dir,
                      mu_arr=None, fm_arr=None, resid_arr=None):
        """Extract mu, fullmod, and resid directly from monitored JAGS nodes."""
        print(f'[{self.version}] Extracting mu, fitted, and residuals from posterior...')
        df_mu, df_mu_lower, df_mu_upper = self._extract_matrix_summary(mu_arr, regions)
        df_fitted    = self._extract_matrix_mean(fm_arr, regions)
        df_residuals = self._extract_matrix_mean(resid_arr, regions)
        df_std_resid = df_residuals / df_residuals.std()

        # free the large sample arrays immediately
        del mu_arr, fm_arr, resid_arr

        return ModelResult(
            raw_df=raw_df,
            pyjags_samples=pyjags_samples,
            dic=dic,
            gelman=gelman,
            df_mu=df_mu,
            df_mu_lower=df_mu_lower,
            df_mu_upper=df_mu_upper,
            df_fitted=df_fitted,
            df_residuals=df_residuals,
            df_std_resid=df_std_resid,
            df_og=df_og,
            regions=regions,
            n_region=n_region,
            n_weeks=n_weeks,
            indicators=indicators,
            output_dir=output_dir,
        )

    def plot_all(self, result):
        """Generate all standard diagnostic plots."""
        plot_dir = result.output_dir / 'plots'
        plot_dir.mkdir(parents=True, exist_ok=True)

        _plot.plot_mu(result.df_mu, result.df_mu_lower, result.df_mu_upper,
                      plot_dir / 'mu_fit.png')
        _plot.plot_fitted(result.df_fitted, plot_dir / 'fitted.png')
        _plot.plot_residuals_combined(result.df_std_resid, plot_dir / 'residuals_combined.png')
        _plot.plot_residuals_ts(result.df_std_resid, plot_dir / 'residuals_ts.png')
        _plot.plot_residuals_acf(result.df_std_resid, plot_dir / 'residuals_acf.png')
        _plot.plot_residuals_pacf(result.df_std_resid, plot_dir / 'residuals_pacf.png')
        _plot.plot_residuals_vs_fitted(result.df_std_resid, result.df_fitted,
                                       plot_dir / 'residuals_vs_fitted.png')
        _plot.plot_residuals_qq(result.df_std_resid, plot_dir / 'residuals_qq.png')
        _plot.plot_residuals_periodogram(result.df_std_resid, plot_dir / 'residuals_periodogram.png')
        _plot.plot_ccf_grid(result.df_og, plot_dir / 'ccf_raw.png',
                            title='Inter-region CCF (raw observed data)')
        _plot.plot_ccf_grid(result.df_std_resid, plot_dir / 'ccf_residuals.png',
                            title=f'[{self.version}] Inter-region CCF (residuals)')

        if result.pyjags_samples is not None:
            _time_params = {'mu', 'fullmod', 'resid'}
            trace_vars = [p for p in self.monitor_params if p not in _time_params]
            _diag.trace_with_dist(result.pyjags_samples,
                                  trace_vars, save_dir=plot_dir)

        self.extra_plots(result, plot_dir)
        print(f'[{self.version}] Plots saved to {plot_dir}')

    def test_all(self, result):
        """Run standard significance tests, dispatched by monitor_params."""
        od = result.output_dir
        raw_df = result.raw_df
        regions = result.regions

        # global parameter summary
        scalar_params = [p for p in raw_df.columns
                         if p != 'chain' and '[' not in p]
        if scalar_params:
            df_global = _sig.summarize_global_parameters(raw_df, scalar_params)
            df_global.to_csv(od / 'global_parameters.csv', index=False)

        # alpha ranking
        ranked = _sig.build_ranked_alpha(raw_df, regions)
        rank_summary = ranked.describe().T[['mean', 'std', '25%', '50%', '75%']]
        rank_summary['ranked_mean'] = rank_summary['mean'].rank(method='average')
        rank_summary.to_csv(od / 'ranks.csv')

        # winter (Dec-Feb) peak probability (if model has annual harmonic)
        if any(f'beta[{i}]' in raw_df.columns for i in range(1, 7)):
            winter_prob = _sig.compute_winter_probability(raw_df, regions)
            winter_prob.to_csv(od / 'winter_probability.csv', index=False)

        # psi tests (if model has Mid West reset)
        if 'psi_pre' in raw_df.columns:
            psi_summary = _sig.summarize_global_parameters(
                raw_df, ['psi_pre', 'psi_mid', 'psi_post'])
            psi_summary.to_csv(od / 'psi_overall.csv', index=False)

        self.extra_significance_tests(result, od)
        print(f'[{self.version}] Significance tests saved to {od}')

    def export(self, result):
        """Save raw samples, DIC, and Gelman to the output directory."""
        od = result.output_dir
        result.raw_df.to_csv(od / 'raw_samples.csv', index=False)
        dic_row = {'version': self.version, 'description': self.name, **result.dic}
        pd.DataFrame([dic_row]).to_csv(od / 'dic.csv', index=False)
        result.gelman.to_csv(od / 'gelman.csv', index=False)
        gelman_summary = (
            result.gelman
            .assign(param=result.gelman['param'].str.replace(r'\[\d+\]$', '', regex=True))
            .groupby('param', sort=False)[['Point est.']]
            .max()
            .reset_index()
        )
        gelman_summary.to_csv(od / 'gelman_summary.csv', index=False)
        result.df_fitted.to_csv(od / 'fitted.csv', index=False)
        result.df_mu.to_csv(od / 'mu.csv', index=False)
        result.df_mu_lower.to_csv(od / 'mu_lower.csv', index=False)
        result.df_mu_upper.to_csv(od / 'mu_upper.csv', index=False)
        result.df_residuals.to_csv(od / 'residuals_posterior_mean.csv', index=False)

        print(f'[{self.version}] Outputs exported to {od}')

    def run(self, data_path=_DEFAULT_DATA_PATH,
            chains=4, burnin=10000, sample=20000, adapt=1000, seed=None):
        """Full pipeline: fit -> export -> plot -> test."""
        result = self.fit(data_path=data_path, chains=chains, burnin=burnin,
                          sample=sample, adapt=adapt, seed=seed)
        self.export(result)
        self.plot_all(result)
        self.test_all(result)
        print(f'[{self.version}] Done.')
        return result
