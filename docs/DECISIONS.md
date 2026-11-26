# Decisions

One line per methodological decision: what you chose, why, and what it changed.
Agents append here via the `/new-feature` skill; you append here by hand.

- Exclude `casual`, `registered`: they sum to `cnt` exactly. Leaky model R^2 1.000 -> honest ridge 0.583.
- Exclude `cnt_2d_bfr`: a shipped 2-day lag we cannot test the alignment of. Build our own lags instead.
- Exclude `instant`, `yr`, `days_since_2011`: time indexes let a tree predict a flat constant past 2011 and a linear model extrapolate a trend we have no grounds for.
- Split 2011 / H1 2012 / H2 2012 by date. Test set touched once, after all feature work.
- Report mean and persistence baselines with every score. Persistence (test R^2 0.510, MAE 840) is within 0.07 R^2 of ridge and beats it on MAE; that caveat goes in the report.
- 2026-11-25: Classify every raw column in `src/config.py` (`ENCODED_COLS` = holiday/workday/weather, re-encoded as numeric features; `REDUNDANT_COLS` = season/mnth/weekday, string copies of dteday). New `test_every_raw_column_is_classified` reads the CSV header and fails on any column nobody has decided about. No metric changed.
- 2026-11-25: Track `reports/` in git (removed from `.gitignore`) so `metrics.json` and `audit.jsonl` are graded artefacts. `reports/metrics_before_feature.json` is a frozen copy of the starter pipeline's metrics, the "before" rows of the REPORT table.
