"""Train and persist the seismic-risk classifier."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.config import MODEL_PATH
from src.features import FEATURE_COLUMNS, feature_matrix


def build_pipeline(random_state: int = 42) -> Pipeline:
    return Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=300,
                    max_depth=12,
                    min_samples_leaf=2,
                    class_weight="balanced",
                    random_state=random_state,
                    n_jobs=-1,
                ),
            ),
        ]
    )


def train(features_df, test_size: float = 0.25, random_state: int = 42):
    X = feature_matrix(features_df)
    y = features_df["risk_level"].astype(str)

    stratify = y if y.nunique() > 1 and y.value_counts().min() >= 2 else None
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=stratify
    )

    pipeline = build_pipeline(random_state=random_state)
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
    cm = confusion_matrix(y_test, y_pred, labels=sorted(y.unique()))

    metrics = {
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "classes": sorted(y.unique().tolist()),
        "classification_report": report,
        "confusion_matrix": cm.tolist(),
    }

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": pipeline, "feature_columns": FEATURE_COLUMNS, "metrics": metrics}, MODEL_PATH)
    return pipeline, metrics


def load_model():
    if not MODEL_PATH.exists():
        return None
    bundle = joblib.load(MODEL_PATH)
    return bundle


def predict(X: pd.DataFrame | None = None, rows=None):
    import pandas as pd

    bundle = load_model()
    if bundle is None:
        return None
    model = bundle["model"]
    cols = bundle["feature_columns"]
    if X is None:
        X = pd.DataFrame(rows, columns=cols)
    X = X[cols]
    pred = model.predict(X)
    proba = None
    if hasattr(model, "predict_proba"):
        try:
            proba = model.predict_proba(X)
        except Exception:
            proba = None
    return pred, proba, bundle.get("metrics")
