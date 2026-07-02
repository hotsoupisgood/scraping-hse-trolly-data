# Modeling HSE daily trolley data
[hsereport.ie](https://hsereport.ie)

Bayesian analysis of the HSE Urgent and Emergency Care Report trolley data. Weekly regional trolley rates are modelled in JAGS with an AR(2) error structure, a region-specific annual cycle, a date-anchored New Year effect, and a Mid West reset block. Models are compared by DIC across several rate scalings. The manuscript lives in `thesis/`.

![Our poster presentation](./poster/Poster_Presentation.png "Poster 2026/02/04")

## Setup

Requires Python 3.14 and the JAGS system library (`brew install jags` on macOS).

```sh
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

## Running the models

`run_models.ipynb` at the project root is the canonical entrypoint. It fits each model via `pyjags_pipeline.run_model(version, data_path)` and compares DIC. Outputs (samples, DIC, Gelman-Rubin, plots, significance tests) go to `data/models/{csv_stem}/{version}/`.

Model definitions live in `pyjags_pipeline/defs/`, one file per model.

## Data lineage

1. Daily scrape of the HSE TrolleyGAR report (one GET per day from `https://uec.hse.ie/uec/TGAR.php`) produces the raw CSVs in `data/raw data/`.
2. `preprocessing/generate_*_scaled.py` turns the weekly regional export into the scaled response CSVs `data/wide_weekly_scaled*.csv`.
3. `run_models.ipynb` fits the models on those CSVs.

Reproducible refit scripts for the reported results are in `validation/`.

## Trolley rate scalings
The weekly regional trolley count is normalised under several denominators (response = trolleys per unit). These are the complete set of scalings, all in `data/wide_weekly_scaled*.csv`:
* `Per10k` — per 10,000 residents (baseline population normalisation)
* `Per1kOver65` — per 1,000 residents aged 65+
* `Per1k75plus` — per 1,000 residents aged 75+
* `Per1kUnder65` — per 1,000 residents aged under 65
* `Per1kMedicalCard` — per 1,000 medical-card holders
* `PerBed` — per 100 inpatient beds (system overcapacity)
* `PerBudgetThousands` — per €1 billion of regional HSE budget
* `Per100Cancellations` — per 100 hospital-initiated cancellations
* `surge_scaledPer10k` — surge-bed-days per 10,000 residents (a separate demand variable, not a trolley-response scaling)

Model fitting and the DIC scaling comparison use the first four (`Per10k`, `Per1kOver65`, `PerBed`, `PerBudgetThousands`). The rest are sensitivity and presentation variants.

## Data sources
* [Emergency care report](https://www2.hse.ie/services/urgent-emergency-care-report/)
* [Health region populations (Census 2022)](https://www.cso.ie/en/releasesandpublications/fp/fp-hhr/hsehealthregions2022/)
* [NUTS3 population estimates 2022-2025 (CSO PEA04)](https://www.cso.ie/en/releasesandpublications/ep/p-pme/populationandmigrationestimatesapril2025/data/)
