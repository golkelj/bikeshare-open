"""The tests that make the agent honest.

test_no_forbidden_features is the single most valuable test in this repo:
casual + registered == cnt exactly, so any model handed those columns
scores R^2 = 1.0 and looks brilliant while having learned nothing.
"""
import pandas as pd
import pytest

from src.config import FORBIDDEN, TARGET
from src.features import build_features, feature_columns
from src.ingest import load_raw


@pytest.fixture(scope="module")
def feats():
    return build_features(load_raw())


def test_leakage_identity_holds(feats):
    """Documents *why* casual and registered are forbidden."""
    assert (feats.casual + feats.registered == feats[TARGET]).all()


def test_no_forbidden_features(feats):
    """Guards the gate, not the data: feature_columns() excludes FORBIDDEN by
    construction, so this cannot discover a *new* leaky column. What it
    catches is someone editing feature_columns() or FORBIDDEN -- which is
    exactly the fault the Step 7 hook demonstrates."""
    cols = set(feature_columns(feats))
    assert not (cols & FORBIDDEN), f"forbidden columns in feature set: {cols & FORBIDDEN}"


def test_lags_are_true_calendar_lags(feats):
    """cnt_lag_1 for date d must equal cnt on d-1, in calendar days."""
    by_date = feats.set_index("dteday")[TARGET]
    checked = 0
    for date, lag in feats.set_index("dteday").cnt_lag_1.items():
        prev = date - pd.Timedelta(days=1)
        if prev in by_date.index:
            assert lag == pytest.approx(by_date[prev]), f"bad lag at {date.date()}"
            checked += 1
    assert checked > 600, "too few rows actually verified"


def test_lag_is_not_the_target(feats):
    assert not (feats.cnt_lag_1 == feats[TARGET]).all()


def test_rolling_mean_excludes_today(feats):
    """cnt_roll_7 must be the mean of the 7 calendar days *before* today."""
    by_date = feats.set_index("dteday")[TARGET]
    date = feats.dteday.iloc[200]
    window = [date - pd.Timedelta(days=k) for k in range(1, 8)]
    if all(d in by_date.index for d in window):
        expected = sum(by_date[d] for d in window) / 7
        assert feats.set_index("dteday").cnt_roll_7[date] == pytest.approx(expected)


def test_rolling_std_is_hand_computed_from_prior_week(feats):
    """cnt_roll_7_std on 2011-06-15 is the sample std (ddof=1) of cnt on
    2011-06-08 .. 2011-06-14, copied by hand from data/raw/bike_daily.csv.
    Today's count (5180) is not in the window; if .shift(1) is dropped the
    value becomes stdev(3915 .. 5180) = 432.99 and this fails."""
    prior_week = [4401, 3915, 4586, 4966, 4460, 5020, 4891]
    mean = sum(prior_week) / 7  # 4605.571...
    expected = (sum((x - mean) ** 2 for x in prior_week) / 6) ** 0.5  # 392.31
    got = feats.set_index("dteday").cnt_roll_7_std[pd.Timestamp("2011-06-15")]
    assert got == pytest.approx(expected, abs=1e-6)
    assert got == pytest.approx(392.31, abs=0.01)


def test_rolling_std_respects_the_calendar_gap(feats):
    """2011-03-10 is absent. The window for 2011-03-17 covers it, so that row
    must be dropped rather than silently computed over a 2011-03-09 count;
    2011-03-18 is the first day after the gap with a full prior week."""
    dates = set(feats.dteday)
    assert pd.Timestamp("2011-03-17") not in dates
    assert pd.Timestamp("2011-03-18") in dates


def test_no_missing_values(feats):
    assert feats[feature_columns(feats)].isna().sum().sum() == 0


def test_dates_are_sorted_and_unique(feats):
    assert feats.dteday.is_monotonic_increasing
    assert feats.dteday.is_unique
