# Audit of a teammate's repo (Exercise 3)

**Repo audited:** https://github.com/dsouza-dylan/DSC180A-Methodology-6 at
commit `eec7f5c` ("Add REPORT.md and modify DECISIONS and SEEDED_FAULTS").
**Diff under review:** `git diff 18c77d3 HEAD -- src tests`, everything since
their unmodified starter commit.

**How it was run.** The repo was cloned into a scratch directory, and I read
its code diff before anything executed it. The auditor has Bash, so it runs
the code under review. The diff makes no network calls (the raw file is
present, so `download()` is skipped), writes only inside its own clone, and
the raw file's sha256 begins `a6bed1577f6e4de5`, as expected. The auditor is
this repo's `.claude/agents/leakage-auditor.md` subagent, invoked from Claude
Code (Claude Opus 5.5, `model: inherit`). It was told to use the pinned
`.venv` interpreter.

## Auditor output (verbatim)

Only the absolute scratch-directory prefix is shortened to `<scratch>`.

> ## Methodology audit: teammate repo (diff `18c77d3..HEAD -- src tests`)
>
> All five checks pass, `reports/metrics.json` reproduces byte for byte, and every number in REPORT.md matches either `metrics.json` or a recomputation. I have no findings that change a number or a conclusion.
>
> ### The five checks
> 1. **Target leakage: pass.** `temp_change_1` is `temp.diff(1)` (`src/features.py:73`). It is built only from same-day and prior-day `temp`, and `cnt`, `casual` and `registered` never enter it. `RelativeToRoll7` (`src/train.py:50-69`) trains on `y - cnt_roll_7` and adds `cnt_roll_7` back at predict time. `cnt_roll_7` is `shift(1).rolling(7).mean()`, so it contains no day-t target.
> 2. **Temporal ordering: pass.** Every lag and rolling feature shifts before it aggregates (`src/features.py:78-80`). The split is by date (`src/train.py:80-86`). The `StandardScaler` sits inside the ridge pipeline and is fitted on train rows only (`src/train.py:108`). The `--diff-roll7` transform was chosen on validation, and the test set was then run once.
> 3. **Calendar gaps: pass.** `diff(1)` runs after `reindex_to_calendar`. I checked the raw file by hand. On 2012-03-02 the value is 8.606651 - 14.834151 = -6.2275. On 2011-03-18 it is 17.38 - 11.505 = 5.875, the first kept row after the missing 2011-03-10. The values that would straddle the gap are NaN, and those rows are already removed by the existing lag warm-up.
> 4. **Silent row loss: pass.** 728 raw rows become 714. `test_only_expected_rows_are_dropped` caps the loss at 7 + 7×1 = 14, and the actual loss is exactly 14. `temp_change_1` adds no extra NaN rows, so the before and after row sets are identical. `encode_weather` raises on unmapped labels.
> 5. **Unreported baseline: pass.** Both the mean and persistence baselines appear in `metrics.json` and in the REPORT.md results table. The `--diff-roll7` path leaves both baselines unwrapped.
>
> ### Reproduction (pinned `.venv` interpreter)
> - `python -m src.ingest`: hash check passes; 728 rows, 2011-01-03 to 2012-12-31.
> - `python -m src.features`: 714 rows, 15 features.
> - `python -m src.train`: the regenerated `reports/metrics.json` is identical to the committed file (`diff` prints nothing).
> - `pytest tests -q`: 19 passed.
> - The working tree was clean afterwards.
>
> ### REPORT.md against the computed values
> - **Results table (lines 13-22), "after" rows:** these match `metrics.json` exactly.
> - **"Before" rows:** I recomputed them by dropping `temp_change_1` from the feature list. That is equivalent to the starter set because the row set does not change. Ridge scores 0.6475 / 832.9 on valid and 0.5833 / 947.1 on test. Hgb scores 0.2185 / 1296.6 and -0.4975 / 1972.6. All four match the table.
> - **Exercise 4 validation table:** I recomputed all six target transforms and they match: 0.159, 0.644, 0.618, 0.759, 0.774, 0.765, with the MAEs as shown.
> - **Exercise 4 test table:** `--diff-roll7` gives hgb 0.6442 / 817.6 and ridge 0.6341 / 852.7, as reported.
> - **Exercise 5:** these also match.
>   - Median absolute error is 506.5 for persistence and 795 for ridge.
>   - Ridge is closer on 83 of 184 days.
>   - On persistence's worst 10% of days, persistence's mean error is 2,909 and ridge's is 1,791 on the same days.
>   - RMSE is 1,062 for ridge and 1,219 for persistence.
>   - The Sandy sequence is 22, then 1,096, then 5,566.
>
> Relevant paths:
> - <scratch>/teammate/repo/src/features.py
> - <scratch>/teammate/repo/src/train.py
> - <scratch>/teammate/repo/reports/metrics.json
> - <scratch>/teammate/repo/REPORT.md
> - Verification script: <scratch>/teammate/check.py
> - Copy of the committed metrics: <scratch>/teammate/metrics.committed.json

## My verdict

I agree with the auditor's bottom line: nothing in this repo changes a
number. I checked the central claim myself rather than taking it on trust.
With the pinned interpreter, `src.ingest` -> `src.features` -> `src.train`
left the clone's working tree clean, so the committed `reports/metrics.json`
reproduces exactly, and `pytest` gives 19 passed. I also agree that
`temp_change_1` is available at prediction time. It needs day d's temperature,
the same assumption the starter already makes for `temp`, so it is a
"same-day weather" feature, not a lag. That assumption, not leakage, is the
thing to state in their report.

One observation does not change any current number, so it is not an auditor
finding. It is a gap in their verification suite, and mine had the same gap
(my fault 5). If `cnt_lag_7` is built with `shift(6)` instead of
`shift(LAG_WARMUP)`, their suite stays green: I applied that edit to the
clone, got 19 passed, and reverted it. No test pins `cnt_lag_7`'s alignment,
so a future edit could misalign it silently. The fix is a test like my
`test_lag_7_is_seven_calendar_days`: one hand-copied value on a named date,
plus a full-column check against `cnt` shifted 7 calendar days.
