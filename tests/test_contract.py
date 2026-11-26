"""Guard rails on the ingest contract and the trained model's behaviour."""
import pandas as pd
import pytest
from sklearn.metrics import r2_score

from src.config import (
    DATE_COL,
    ENCODED_COLS,
    FORBIDDEN,
    LAG_WARMUP,
    RAW,
    REDUNDANT_COLS,
    TARGET,
)
from src.features import build_features, feature_columns, reindex_to_calendar
from src.ingest import load_raw, verify_raw
from src.train import MODELS, temporal_split


@pytest.fixture(scope="module")
def raw():
    return load_raw().sort_values("dteday").reset_index(drop=True)


@pytest.fixture(scope="module")
def feats(raw):
    return build_features(raw)


def test_calendar_is_complete_before_lagging(raw):
    """The reindexed frame must have no gaps, or the lags are wrong."""
    grid = reindex_to_calendar(raw)
    assert set(grid.dteday.diff().dropna().dt.days.unique()) == {1}


def test_only_expected_rows_are_dropped(raw, feats):
    """Rows may only vanish for the lag warm-up or downstream of a genuinely
    absent day -- never because an encoder produced a silent NaN.

    Accounting: the first LAG_WARMUP days have no complete history. Each
    absent calendar day m costs the LAG_WARMUP rows after it (cnt_lag_1 is
    NaN on m+1, cnt_roll_7 is NaN on m+1..m+7, cnt_lag_7 on m+7; their
    union is 7 rows). Day m itself was never in `raw`, so it is not a loss.
    The bound is exact for the current feature set; add a longer lag and
    LAG_WARMUP in src/config.py must grow with it.
    """
    full = pd.date_range(raw.dteday.min(), raw.dteday.max(), freq="D")
    missing_days = len(full) - len(raw)
    allowed_loss = LAG_WARMUP + LAG_WARMUP * missing_days
    lost = len(raw) - len(feats)
    assert lost <= allowed_loss, f"lost {lost} rows; expected at most {allowed_loss}"


def test_beats_the_mean_baseline(feats):
    """A model that cannot beat predicting the training mean is not a result."""
    cols = feature_columns(feats)
    train, _, test = temporal_split(feats)
    ridge = MODELS["ridge"]
    ridge.fit(train[cols], train[TARGET])
    assert r2_score(test[TARGET], ridge.predict(test[cols])) > 0.4


def test_every_raw_column_is_classified(feats):
    """Each column of the raw CSV must be forbidden, a model feature, the date,
    or explicitly listed as encoded or redundant in src/config.py. A column the
    mirror adds (as it added days_since_2011 and cnt_2d_bfr) fails here until
    someone decides what it is. The header is read from the file itself, not
    from anything the pipeline derived from it."""
    header = pd.read_csv(RAW, nrows=0).columns
    known = FORBIDDEN | set(feature_columns(feats)) | {DATE_COL} | ENCODED_COLS | REDUNDANT_COLS
    unclassified = sorted(set(header) - known)
    assert not unclassified, f"raw columns not classified in src/config.py: {unclassified}"


def test_raw_file_is_unmodified():
    """The checked-in raw file must hash to RAW_SHA256. Bash can write to
    data/raw/ even though Write/Edit are denied; this is the check that
    notices."""
    verify_raw()


def test_hash_check_rejects_a_tampered_copy(tmp_path):
    """Change one count in a copy (Hurricane Sandy, cnt 22 -> 5022). The
    shape, columns and row count are all unchanged, so ingest's own checks
    accept it; the hash check must refuse it. Guards against verify_raw
    being edited into a no-op."""
    tampered = tmp_path / "bike_daily.csv"
    tampered.write_bytes(RAW.read_bytes().replace(b',22,"Y"', b',5022,"Y"', 1))
    assert tampered.read_bytes() != RAW.read_bytes()
    with pytest.raises(ValueError, match="raw data was modified"):
        verify_raw(tampered)


def test_persistence_baseline_is_reported():
    """The baseline that matters for a lag-driven model is 'yesterday again'.
    It must be in the comparison, whatever its score."""
    assert "baseline_persistence" in MODELS
