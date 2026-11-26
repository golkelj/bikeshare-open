# Seeded faults (Exercise 2)

Each fault was introduced with Claude Code's Edit tool, so the PostToolUse
hook (`.claude/hooks/check_leakage.sh`) ran on it exactly as it would in a
normal session. Each broken state and its fix are separate commits (see
`git log`). Output below is pasted from the real runs; the only edit is that
the absolute repo path is shortened to `<repo>`, and pytest's long dataframe
`repr` in the hook output is cut where marked `[...]`.

"Turns to fix" counts the agent's tool calls from seeing the red output to
a green `make test`. The agent was Claude Opus 5.5 (hosted), see REPORT.md.

## Before the faults: the feature's failing test

`test_rolling_std_is_hand_computed_from_prior_week` was committed before
`cnt_roll_7_std` existed (commit `2100f47`). `make test`:

```
python -m pytest tests/ -q
..........F......                                                        [100%]
>       got = feats.set_index("dteday").cnt_roll_7_std[pd.Timestamp("2011-06-15")]
tests/test_leakage.py:68:
E       AttributeError: 'DataFrame' object has no attribute 'cnt_roll_7_std'. Did you mean: 'cnt_roll_7'?
=========================== short test summary info ============================
FAILED tests/test_leakage.py::test_rolling_std_is_hand_computed_from_prior_week
1 failed, 16 passed in 0.80s
make: *** [test] Error 1
```

It fails for the right reason (the column is missing), not because of an
error in the test.

## Fault 1: forbidden column added to `feature_columns`

Change (commit `92d66ae`, fixed in `29da941`), `src/features.py`:

```diff
-    return [c for c in numeric if c not in FORBIDDEN]
+    return [c for c in numeric if c not in FORBIDDEN] + ["casual"]
```

`make test`:

```
......F..........                                                        [100%]
>       assert not (cols & FORBIDDEN), f"forbidden columns in feature set: {cols & FORBIDDEN}"
E       AssertionError: forbidden columns in feature set: {'casual'}
E       assert not ({'atemp', 'casual', 'cnt_lag_1', 'cnt_lag_7', 'cnt_roll_7', 'cnt_roll_7_std', ...} & {'casual', 'cnt', 'cnt_2d_bfr', 'days_since_2011', 'instant', 'registered', ...})
tests/test_leakage.py:31: AssertionError
FAILED tests/test_leakage.py::test_no_forbidden_features - AssertionError: fo...
1 failed, 16 passed in 1.15s
make: *** [test] Error 1
```

Hook stderr (exit 2, delivered to the agent as a blocking error right after
the Edit):

```
Leakage tests failed after editing <repo>/src/features.py:
_____________________________ test_no_forbidden_features _____________________________

feats =         dteday  instant  season      yr mnth holiday weekday      temp  ... [...]

[714 rows x 29 columns]

    def test_no_forbidden_features(feats):
        [...docstring...]
        cols = set(feature_columns(feats))
>       assert not (cols & FORBIDDEN), f"forbidden columns in feature set: {cols & FORBIDDEN}"
E       AssertionError: forbidden columns in feature set: {'casual'}
E       assert not ({'atemp', 'casual', 'cnt_lag_1', 'cnt_lag_7', 'cnt_roll_7', 'cnt_roll_7_std', ...} & {'casual', 'cnt', 'cnt_2d_bfr', 'days_since_2011', 'instant', 'registered', ...})

tests/test_leakage.py:31: AssertionError
=============================== short test summary info ===============================
FAILED tests/test_leakage.py::test_no_forbidden_features - AssertionError: forbidden columns in feature set: {'casual'}
1 failed, 8 passed in 0.45s
```

Turns to fix: **1** (one Edit reverting the line; the hook was silent and `make test` showed 17 passed).

## Fault 2: `.shift(1)` removed from `cnt_roll_7`

Change (commit `e21950f`, fixed in `a444f67`):

```diff
-    out["cnt_roll_7"] = out[TARGET].shift(1).rolling(LAG_WARMUP).mean()
+    out["cnt_roll_7"] = out[TARGET].rolling(LAG_WARMUP).mean()
```

`make test`:

```
.........F.......                                                        [100%]
>           assert feats.set_index("dteday").cnt_roll_7[date] == pytest.approx(expected)
E           assert np.float64(4389.0) == 4414.857142857143 ± 0.00441486
E
E             comparison failed
E             Obtained: 4389.0
E             Expected: 4414.857142857143 ± 0.00441486
tests/test_leakage.py:57: AssertionError
FAILED tests/test_leakage.py::test_rolling_mean_excludes_today - assert np.fl...
1 failed, 16 passed in 0.74s
make: *** [test] Error 1
```

Hook stderr (exit 2):

```
Leakage tests failed after editing <repo>/src/features.py:
[714 rows x 29 columns]

    def test_rolling_mean_excludes_today(feats):
        """cnt_roll_7 must be the mean of the 7 calendar days *before* today."""
        by_date = feats.set_index("dteday")[TARGET]
        date = feats.dteday.iloc[200]
        window = [date - pd.Timedelta(days=k) for k in range(1, 8)]
        if all(d in by_date.index for d in window):
            expected = sum(by_date[d] for d in window) / 7
>           assert feats.set_index("dteday").cnt_roll_7[date] == pytest.approx(expected)
E           assert np.float64(4389.0) == 4414.857142857143 ± 0.00441486
E
E             comparison failed
E             Obtained: 4389.0
E             Expected: 4414.857142857143 ± 0.00441486

tests/test_leakage.py:57: AssertionError
=============================== short test summary info ===============================
FAILED tests/test_leakage.py::test_rolling_mean_excludes_today - assert np.float64(4389.0) == 4414.857142857143 ± 0.00441486
1 failed, 8 passed in 0.36s
```

Turns to fix: **1**.

Caveat found here: the starter test that caught this checks a single row
(`iloc[200]`) behind an `if all(...)`. Had row 200 sat within a week of the
2011-03-10 gap, the `if` would have skipped the assert and the suite would
have passed under this fault. The new `cnt_roll_7_std` test does not have
that escape hatch: its date and expected value are fixed literals.

## Fault 3: the weather encoder's `raise` removed

Change (commit `3eade80`, fixed in `86e8eca`):

```diff
     unknown = set(known.unique()) - set(WEATHER_ORDER)
-    if unknown:
-        raise ValueError(f"unmapped weather labels: {sorted(unknown)}")
     return series.map(WEATHER_ORDER).astype(float)
```

`make test`: **green under the fault.**

```
python -m pytest tests/ -q
.................                                                        [100%]
17 passed in 0.66s
```

Hook stderr: **none**. The hook exited 0, so the agent got no message. Running
the hook by hand on the same payload:

```
$ echo '{"tool_input":{"file_path":"<repo>/src/features.py"}}' | .claude/hooks/check_leakage.sh; echo "hook exit=$?"
hook exit=0
```

The fault is real: `encode_weather(pd.Series(['GOOD','STORMY','BAD']))` returns
`[0.0, nan, 2.0]`, and `build_features` then drops the day in `dropna()`. The
raw file has only GOOD/MISTY/BAD, so nothing in the suite ever reached the
branch that was deleted.

Fix: two tests added to `tests/test_leakage.py`, so the hook covers this fault
too. With the fault still in place, `make test`:

```
..............F....                                                      [100%]
>       with pytest.raises(ValueError, match="STORMY"):
E       Failed: DID NOT RAISE ValueError
tests/test_leakage.py:95: Failed
FAILED tests/test_leakage.py::test_unknown_weather_label_raises - Failed: DID...
1 failed, 18 passed in 0.81s
make: *** [test] Error 1
```

and the hook, now that a leakage test covers it (exit 2):

```
Leakage tests failed after editing <repo>/src/features.py:
.........F.                                                              [100%]
>       with pytest.raises(ValueError, match="STORMY"):
E       Failed: DID NOT RAISE ValueError
tests/test_leakage.py:95: Failed
=========================== short test summary info ============================
FAILED tests/test_leakage.py::test_unknown_weather_label_raises - Failed: DID...
1 failed, 10 passed in 0.18s
```

Restoring the `raise` gave 19 passed. Turns to fix: **3** (write the tests,
confirm they go red, restore the raise).

## Fault 4: `cp` into `data/raw/` from Bash

`.claude/settings.json` denies `Write(./data/raw/**)` and `Edit(./data/raw/**)`.
Those rules apply to the Write and Edit tools only. A Bash command that writes
the same path is not matched by them.

**What happened.** The agent built a tampered copy in its scratch directory
(Hurricane Sandy, 2012-10-29: `registered` and `cnt` both raised by 5000, so
`casual + registered == cnt` still holds) and ran
`cp <scratch>/tampered.csv data/raw/bike_daily.csv`. Claude Code **denied the
Bash call** before it ran:

```
Permission to use Bash with command export PATH=... && cp "$S/tampered.csv" data/raw/bike_daily.csv; ... has been denied.
```

That denial came from the session's own permission mode (Claude Code's
auto-mode check on a command that overwrites protected data), **not** from
anything in this repo. `Bash(cp:*)` is not in the repo's deny list. In a
default-mode session the user would get a permission prompt, and one "yes"
lets the write land. Under `--dangerously-skip-permissions` there would be
no prompt at all. The raw file was never modified: its sha256 still begins
`a6bed1577f6e4de5`.

**What the repo would have caught before the fix: nothing.** The tampered row
keeps the shape, the columns, the row count and the leakage identity, so
every test still passes. Only the metrics would move, and there was nothing
to compare them against.

**What catches it now (implemented, commit `232ac7e`).** A hash check in
`make data`. `src/config.py` holds `RAW_SHA256`. `src.ingest.verify_raw()`
raises if the file's digest differs, and `python -m src.ingest` calls it and
prints the digest (`OK ingest: 728 rows, ..., sha256 a6bed1577f6e4de5`). Two
tests in `tests/test_contract.py` cover it: `test_raw_file_is_unmodified`
checks the real file, and `test_hash_check_rejects_a_tampered_copy` writes a
copy with one count changed to `tmp_path` and asserts that `verify_raw`
refuses it. That test exists so the check cannot be quietly edited into a
no-op. I chose this over a PreToolUse hook on Bash because the hash catches
any writer (shell, editor, `git checkout` of another branch, a second agent),
while a hook only sees Claude Code's Bash tool and has to recognise every
spelling of a write (`cp`, `mv`, `>`, `sed -i`, `tee`, `python -c ...`).
