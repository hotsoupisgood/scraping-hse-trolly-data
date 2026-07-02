"""Fit the restructured v4.x development ladder and print the DIC table.

Build order: mean structure first, AR last.
  v4.1 Baseline -> v4.2 +Annual cycle -> v4.3 +Regional New Year (date-anchored)
  -> v4.4 +MW reset -> v4.5 +AR(1) -> v4.6 +AR(2) [base]
Extensions on the AR(2) base (each independent):
  v4.7 +4-week cycle, v4.8 +8-week cycle, v4.9 +26-week cycle

Outputs land in data/models/wide_weekly_scaledPer10k/v4.x/ via the pipeline.
"""
from pyjags_pipeline import run_model

LADDER = ['v4.1', 'v4.2', 'v4.3', 'v4.4', 'v4.5', 'v4.6', 'v4.7', 'v4.8', 'v4.9']

rows = []
for v in LADDER:
    res = run_model(v)
    d = res.dic
    rows.append((v, d['deviance'], d['penalty'], d['DIC']))

print('\n=== v4.x DIC ladder (wide_weekly_scaledPer10k) ===')
print(f'{"ver":<6}{"deviance":>11}{"pD":>9}{"DIC":>11}    delta-vs-prev')
prev = None
for v, dev, pd_, dic in rows:
    delta = '' if prev is None else f'{dic - prev:+.1f}'
    print(f'{v:<6}{dev:>11.1f}{pd_:>9.1f}{dic:>11.1f}   {delta}')
    prev = dic
