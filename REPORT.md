# Bikeshare demand: methodology report

Daily Capital Bikeshare counts (`cnt`), 2011-01-03 to 2012-12-31 (728 rows,
2011-03-10 missing). Split by date: train = 2011 (348 rows after the 7-day
warm-up), validation = H1 2012 (182), test = H2 2012 (184). Every number below
comes from `make all` on the final commit (`reports/metrics.json`) or from the
frozen starter run (`reports/metrics_before_feature.json`), to the digit.

## 1. Results

"Before" is the starter feature set (14 features). "After" adds
`cnt_roll_7_std`, the sample standard deviation of `cnt` over days d-7..d-1
(15 features). The rows, split and models are otherwise identical.

| Model | Features | Valid R^2 | Valid MAE | Test R^2 | Test MAE |
|---|---|---:|---:|---:|---:|
| baseline_mean | before | -0.9318 | 2002.2 | -2.1441 | 2847.7 |
| baseline_mean | after | -0.9318 | 2002.2 | -2.1441 | 2847.7 |
| baseline_persistence | before | 0.4507 | 900.6 | 0.5099 | 840.1 |
| baseline_persistence | after | 0.4507 | 900.6 | 0.5099 | 840.1 |
| ridge | before | 0.6475 | 832.9 | 0.5833 | 947.1 |
| ridge | after | 0.7224 | 700.4 | 0.6356 | 840.3 |
| hgb | before | 0.2185 | 1296.6 | -0.4975 | 1972.6 |
| hgb | after | 0.0977 | 1381.6 | -0.6959 | 2108.4 |

The baselines do not use the new column, so their rows cannot move. That
they match is a check, not a result.

**The feature (Exercise 1).** The validation delta is +0.0749 R^2 and -132.5
MAE for ridge, and -0.1208 R^2 for hgb. I chose it from six candidates
screened on validation only (`cnt_lag_2`, `cnt_roll_7_std`, `cnt_roll_14`,
`cnt_roll_28`, `cnt_ewm_7`, `temp_diff_1`; see `docs/DECISIONS.md`), so some
of the gain is selection optimism. It is still 7x the 0.01 bar the skill sets
for noise, and it is not a disguised level feature (correlation with
`cnt_roll_7` is 0.16 on train). Its standardised ridge coefficient is +174.
A plausible reading: a volatile week usually contains a bad-weather dip that
drags `cnt_roll_7` down, and the std tells the model that the mean is
depressed. The test columns were not looked at until the feature was
committed. Kept.

**Verification.** `make test` runs 22 tests (14 starter + 8 added). Five
faults were seeded (`docs/SEEDED_FAULTS.md`). Faults 1 and 2 went red at
once, in the hook and in the suite. Faults 3 and 5 left the suite **green**
until a test was added, and the fault-4 write to `data/raw/` would have
passed every test. Each of those three now has a test that fails against the
broken code.

## 2. Headline finding

**Gradient boosting trained on 2011 cannot predict 2012, and the reason is
the level, not the model.** Train `cnt` tops out at 6043. In validation, 71
of 182 days exceed that; in test, 104 of 184 do (test mean 6043, max 8714).
A tree's prediction is an average of training leaves, so hgb's predictions
never exceed 5927 on train and stay at or below 5564 on validation and test.
It predicts a 2011-sized city every day. Its test R^2 (-0.6959) is worse
than predicting the 2011 mean, which is itself -2.1441 only because the mean
is also a 2011 number. Ridge extrapolates through the lag features (if
yesterday was 7000, it predicts near 7000), so it beats persistence on R^2
(0.6356 vs 0.5099). The new feature widens the gap: it helps ridge and hurts
hgb.

Ridge still carries the level problem. Its mean residual on test is +372
(it under-predicts H2 2012). Hurricane Sandy (2012-10-29, 22 rides) is
ridge's single largest test error (4284 rides). For persistence, the
largest error is two days later (2012-10-31, 4470, when it copies the storm
forward), and Sandy ranks 3rd. Sandy is only the 70th-largest error for the
mean baseline and the 143rd for hgb, whose errors are dominated by
under-predicting ordinary high-demand days.

## 3. Exercise 4: target transformation

Question: is there a target hgb can learn that does not require
extrapolation? `python -m src.train --target ratio_roll7` fits ridge and hgb
on `cnt / cnt_roll_7`, today relative to the trailing week, and multiplies
the prediction back. `--target diff_roll7` uses `cnt - cnt_roll_7`.
`RelativeTarget` in `src/train.py` does the wrapping. The baselines are
untouched. The graded `reports/metrics.json` is the untransformed pipeline
and is byte-identical with or without this code.

Process. I screened four transforms on validation (hgb valid R^2):
`diff_lag1` 0.5642, `logratio_roll7` 0.7079, `diff_roll7` 0.7167,
`ratio_roll7` 0.7483 (raw ridge: 0.7224). I committed the choice with
validation numbers only (`--target` scores test only with `--final`), then
ran `--final` once (`reports/metrics_target_*.json`):

| Model | Target | Valid R^2 | Valid MAE | Test R^2 | Test MAE |
|---|---|---:|---:|---:|---:|
| hgb | raw | 0.0977 | 1381.6 | -0.6959 | 2108.4 |
| hgb | ratio_roll7 | 0.7483 | 685.5 | 0.6280 | 832.8 |
| hgb | diff_roll7 | 0.7167 | 725.9 | 0.6271 | 829.1 |
| ridge | raw | 0.7224 | 700.4 | 0.6356 | 840.3 |
| ridge | ratio_roll7 | 0.6128 | 857.3 | 0.1977 | 1323.3 |
| ridge | diff_roll7 | 0.7263 | 690.5 | 0.6408 | 828.1 |

hgb now competes with ridge (test R^2 0.6280 vs 0.6356). It does not beat
it.

**Is it defensible? Yes, with one caveat.** The denominator `cnt_roll_7` is
built with `.shift(1)` and is a model feature already, so nothing unknown at
prediction time enters. The transform is honest, and it fixes the actual
failure: the tree now predicts "how today compares to last week", a quantity
whose range was the same in 2011 and 2012. Two different relative targets
(ratio and difference) both work, so this is a mechanism, not a lucky draw.
The caveat is selection. I tried four transforms against 182 validation days
and kept the best, so the 0.7483 is optimistic; the test number (0.6280),
seen once, is the honest one. The transform is also model-specific: ratio
wrecks ridge (test 0.1977), because a linear model of a ratio multiplied by
the level is no longer linear in the features.

## 4. Exercise 5: is ridge worth deploying over persistence?

On these numbers, ridge is **not** worth deploying over persistence for a
forecast judged on typical-day error, and is worth it only if the cost is
in the large misses. On the test half-year the two have the same MAE (840.3
vs 840.1). A weekly-block bootstrap of the daily MAE difference gives a 95%
interval of [-107, +90] rides, and ridge is closer than persistence on only
80 of 184 days, with a worse median absolute error (743 vs 506). Ridge's
higher R^2 (0.6356 vs 0.5099) comes entirely from the tail: its
90th-percentile error is 1556 against persistence's 1960, because it does not
copy yesterday's storm or holiday into today. Validation told a different
story (MAE 700.4 vs 900.6, interval [94, 339]), and the gap between the two
halves of 2012 is the level drift. Ridge under-predicts H2 2012 by 372 rides
on average, while persistence has no level to get wrong. Deploy ridge only
with a level correction (or retraining on 2012) and only if an operator cares
more about avoiding a 2000-ride miss than about being closer on an ordinary
Tuesday. Otherwise, "yesterday again" is cheaper, has no fitted parameters,
and is as good.

## 5. Attribution

**Model and harness.** All agent work in this repo was done in Claude Code
driving **Claude Opus 5.5** (`claude-opus-5-5`), a hosted Anthropic model.
Its parameter count is not published. This was **not** the local
`bikeshare-coder` (qwen3.5:9b) the starter configures: Ollama was not
installed on this machine, and the `model`/`env` override was removed from
the working copy of `.claude/settings.json`, outside git. The committed
`.claude/settings.json` is the starter's. `reports/audit.jsonl` was produced
by `agent/audit.py` with `AUDIT_MODEL=claude-sonnet-5-5`, also hosted. There
was no switch of model mid-assignment, and Exercise 6 was not attempted.
Results from a 9B local model would not be comparable.

**Agent-generated (Claude Opus 5.5), reviewed through tests and commits:**
- `src/config.py`: `ENCODED_COLS`, `REDUNDANT_COLS`, `DATE_COL`, `RAW_SHA256`, `REPORTS`.
- `src/features.py`: `cnt_roll_7_std`.
- `src/ingest.py`: `verify_raw` and its call in `make data`.
- `src/train.py`: `RelativeTarget`, `models_for`, the `--target` / `--final` flags.
- `tests/`: the 8 new tests (classification, hash x2, roll-std x2, weather x2, lag-7).
- `Makefile`: `PYTHON ?=` venv selection.
- `.claude/skills/seed-fault/SKILL.md`.
- The CLAUDE.md additions.
- `docs/SEEDED_FAULTS.md`.
- Drafts of this report, including the Exercise 5 paragraph.
- The candidate screens for the feature and the transform (validation only; their outputs are recorded in DECISIONS.md).

**Decisions, each traced to a dated line in `docs/DECISIONS.md`.**

- What to predict: `cnt`, next-day total rides (starter).
- Leakage definition: `casual`/`registered`/`cnt` excluded as arithmetic restatements of the target; time indexes and the unverified `cnt_2d_bfr` excluded too (starter lines). Every raw column must now be classified.
- Split: 2011 / H1 2012 / H2 2012, by date. Test was scored once per question: the feature (after commit) and the transform (`--final`, once).
- Baselines: mean and persistence on every row of every table.
- Believability: R^2 = 1.000 is rejected as leakage. hgb's negative R^2 is reported as the headline, not hidden. Exercise 4's validation gain is marked as selection-inflated.
- Keeping the feature: kept (+0.075 ridge validation R^2, above the 0.01 bar).
- Exercise 4 transform: defensible, but not adopted in the graded pipeline.
- Fault-4 fix: a hash check rather than a Bash PreToolUse hook.
- Acting on audit finding 2: done (Makefile).
