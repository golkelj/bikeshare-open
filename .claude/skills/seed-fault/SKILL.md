---
name: seed-fault
description: Deliberately break one guard in src/, prove the suite and hook go red (or record that they do not), fix it, and log it in docs/SEEDED_FAULTS.md. Use when asked to seed, inject, or test a fault.
argument-hint: <one-line description of the fault, e.g. "drop .shift(1) from cnt_lag_7">
allowed-tools: Read, Edit, Bash(python -m pytest*), Bash(make test*), Bash(git diff*), Bash(git status*), Bash(git commit*), Bash(git log*)
---

# Faults seeded so far

!`git log --oneline | grep "SEEDED FAULT" || echo "(none yet)"`

# Seeding: $ARGUMENTS

Do these in order. The point is evidence, so paste real output and never
paraphrase it.

1. **Start green.** Run `make test`. If anything already fails, stop and say
   so; a fault seeded on a red suite proves nothing. Confirm
   `git status --short src/` is empty.

2. **Seed the fault with the Edit tool**, never with sed or a Bash heredoc:
   the PostToolUse hook only fires on Edit/Write, and its reaction is part of
   what is being tested. Make the smallest edit that produces
   "$ARGUMENTS". Do not touch `data/raw/`; the permission rules deny it, and
   a Bash write would be a different fault (number 4) with its own write-up.

3. **Record what fired.** Copy the hook's stderr verbatim if it blocked, or
   write "hook exit 0, no stderr" if it did not. Then run `make test` and
   keep the `E ...`, `FAILED ...` and summary lines.

4. **Commit the broken state** on its own: `SEEDED FAULT <n>: $ARGUMENTS`,
   with a body saying whether the suite went red. Stage only the file you
   broke.

5. **If the suite stayed green, that is the finding.** Write the missing test
   first, in `tests/test_leakage.py` (so the hook covers it next time), and
   run `make test` against the still-broken code to show that it now fails.
   A test that passes with the fault still in place is not a fix.

6. **Fix it and count the turns.** Revert or repair with Edit, run
   `make test` to green, and commit `Fix seeded fault <n>: ...`. A turn is one
   tool call from seeing red to seeing green.

7. **Log it** in `docs/SEEDED_FAULTS.md` under a new `## Fault <n>` heading:
   the diff, the `make test` output, the hook stderr, the turns to fix, and
   both commit hashes. Shorten the absolute repo path to `<repo>`.

Finish with one line: fault, caught by (hook / suite / nothing), turns to fix.
