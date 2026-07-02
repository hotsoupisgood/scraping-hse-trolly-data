"""Fit the selected base (v4.6, AR(2)) on the non-primary scalings.

Per10k is already fitted; this adds the bed, budget, and 65+ scalings so the
multi-scaling ranking sensitivity uses the AR(2) base throughout.
"""
from pyjags_pipeline import run_model

SCALINGS = [
    'data/wide_weekly_scaledPerBed.csv',
    'data/wide_weekly_scaledPerBudgetThousands.csv',
    'data/wide_weekly_scaledPer1kOver65.csv',
]

for path in SCALINGS:
    res = run_model('v4.6', data_path=path, seed=42)
    print(f'{path}  ->  DIC {res.dic["DIC"]:.1f}   {res.output_dir}')
