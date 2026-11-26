"""Stage 3: temporal split, fit, evaluate, write metrics.

Two baselines and two models, on purpose.

  baseline_mean         predict the 2011 average for every day
  baseline_persistence  predict yesterday's count (cnt_lag_1)
  ridge                 standardised linear model on the audited features
  hgb                   gradient-boosted trees on the same features

The mean baseline shows what "the distribution moved" costs. Persistence
is the baseline that actually matters: ridge's features are dominated by
lagged demand, so if it cannot beat "yesterday again" it has learned
nothing worth reporting. The booster is there because it fails, and the
reason it fails is the headline result.

Run: python -m src.train

Exercise 4 (not the graded pipeline): `--target ratio_roll7` or
`--target diff_roll7` fits ridge and hgb on cnt relative to the trailing
7-day mean and maps predictions back to counts. It scores validation only
unless `--final` is passed, and writes reports/metrics_target_<name>.json,
never reports/metrics.json.
"""
import argparse
import json

import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin, clone
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.config import (
    METRICS,
    PROCESSED,
    REPORTS,
    TARGET,
    TRAIN_END,
    VALID_END,
)
from src.features import feature_columns


class PersistenceBaseline(BaseEstimator, RegressorMixin):
    """Predict a single lagged column unchanged. Nothing is fit."""

    def __init__(self, column: str = "cnt_lag_1"):
        self.column = column

    def fit(self, X, y=None):
        if self.column not in X.columns:
            raise ValueError(f"persistence baseline needs column {self.column!r}")
        return self

    def predict(self, X):
        return X[self.column].to_numpy(dtype=float)


class RelativeTarget(BaseEstimator, RegressorMixin):
    """Fit `estimator` on cnt relative to a lagged level column, then map
    predictions back to counts. `base` must be a past-only feature (it is
    cnt_roll_7, shifted before rolling), so the transform uses nothing a
    forecaster would not have at prediction time."""

    def __init__(self, estimator=None, base: str = "cnt_roll_7", kind: str = "ratio"):
        self.estimator = estimator
        self.base = base
        self.kind = kind

    def _forward(self, X, y):
        level = X[self.base].to_numpy(dtype=float)
        return y / level if self.kind == "ratio" else y - level

    def fit(self, X, y):
        self.estimator_ = clone(self.estimator).fit(X, self._forward(X, y.to_numpy(dtype=float)))
        return self

    def predict(self, X):
        level = X[self.base].to_numpy(dtype=float)
        z = self.estimator_.predict(X)
        return level * z if self.kind == "ratio" else level + z


TARGET_TRANSFORMS = {"ratio_roll7": "ratio", "diff_roll7": "diff"}


MODELS = {
    "baseline_mean": DummyRegressor(strategy="mean"),
    "baseline_persistence": PersistenceBaseline("cnt_lag_1"),
    "ridge": make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
    "hgb": HistGradientBoostingRegressor(random_state=0, max_iter=300),
}


def temporal_split(df: pd.DataFrame):
    """Split by date, never at random. A random split on a time series
    puts tomorrow in train and today in test."""
    train = df[df.dteday <= TRAIN_END]
    valid = df[(df.dteday > TRAIN_END) & (df.dteday <= VALID_END)]
    test = df[df.dteday > VALID_END]
    return train, valid, test


def models_for(target: str = "raw") -> dict:
    """The four models, with ridge and hgb wrapped for a transformed target.
    Baselines never change: they are the yardstick, not a contender."""
    if target == "raw":
        return MODELS
    kind = TARGET_TRANSFORMS[target]
    return {
        name: RelativeTarget(model, kind=kind) if name in ("ridge", "hgb") else model
        for name, model in MODELS.items()
    }


def fit_and_score(target: str = "raw", splits: tuple[str, ...] = ("valid", "test")) -> dict:
    df = pd.read_parquet(PROCESSED)
    cols = feature_columns(df)
    train, valid, test = temporal_split(df)

    results = {
        "n_features": len(cols),
        "features": cols,
        "n_train": len(train),
        "n_valid": len(valid),
        "n_test": len(test),
    }
    if target != "raw":
        results["target"] = target
    parts = {"valid": valid, "test": test}
    for name, model in models_for(target).items():
        model.fit(train[cols], train[TARGET])
        results[name] = {
            split: {
                "r2": round(float(r2_score(part[TARGET], model.predict(part[cols]))), 4),
                "mae": round(float(mean_absolute_error(part[TARGET], model.predict(part[cols]))), 1),
            }
            for split, part in parts.items()
            if split in splits
        }
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="raw", choices=["raw", *TARGET_TRANSFORMS])
    ap.add_argument("--final", action="store_true",
                    help="with --target: also score the test split (do this once)")
    ns = ap.parse_args()
    if ns.target == "raw":
        res, out = fit_and_score(), METRICS
    else:
        splits = ("valid", "test") if ns.final else ("valid",)
        res = fit_and_score(ns.target, splits)
        out = REPORTS / f"metrics_target_{ns.target}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2))
    print(json.dumps({k: v for k, v in res.items() if k != "features"}, indent=2))
