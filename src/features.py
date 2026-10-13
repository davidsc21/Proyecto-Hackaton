"""Feature engineering for seismic-risk classification."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import (
    CELL_SIZE_DEG,
    EARTHQUAKES_PATH,
    FEATURES_PATH,
    MESA_CENTER,
    SANTANDER_BBOX,
)


def _distance_km(lat1, lon1, lat2, lon2) -> float:
    # Equirectangular approximation, good enough for small distances.
    r = 6371.0
    x = math.radians(lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    y = math.radians(lat2 - lat1)
    return r * math.hypot(x, y)


def load_earthquakes(path: Path | None = None) -> pd.DataFrame:
    path = path or EARTHQUAKES_PATH
    df = pd.read_csv(path)
    df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
    df = df.dropna(subset=["latitude", "longitude", "magnitude"])
    return df


def make_grid(cell: float = CELL_SIZE_DEG) -> pd.DataFrame:
    min_lat, max_lat, min_lon, max_lon = SANTANDER_BBOX
    lats = np.round(np.arange(min_lat, max_lat + cell, cell), 6)
    lons = np.round(np.arange(min_lon, max_lon + cell, cell), 6)
    grid = pd.MultiIndex.from_product([lats, lons], names=["cell_lat", "cell_lon"]).to_frame(index=False)
    grid["cell_id"] = grid["cell_lat"].astype(str) + "_" + grid["cell_lon"].astype(str)
    return grid


def aggregate_features(df: pd.DataFrame, cell: float = CELL_SIZE_DEG) -> pd.DataFrame:
    """Aggregate earthquake events into spatial grid cells."""
    if df.empty:
        grid = make_grid(cell)
        for col in ["n_events", "max_magnitude", "mean_magnitude", "mean_depth_km",
                    "log_energy", "events_per_year", "years_active"]:
            grid[col] = 0.0 if col != "mean_depth_km" else 150.0
        grid["risk_level"] = "Low"
        return grid

    work = df.copy()
    work["cell_lat"] = np.round(work["latitude"] / cell) * cell
    work["cell_lon"] = np.round(work["longitude"] / cell) * cell
    work["cell_lat"] = work["cell_lat"].round(6)
    work["cell_lon"] = work["cell_lon"].round(6)
    work["energy"] = 10 ** (1.5 * work["magnitude"])

    agg = work.groupby(["cell_lat", "cell_lon"]).agg(
        n_events=("magnitude", "size"),
        max_magnitude=("magnitude", "max"),
        mean_magnitude=("magnitude", "mean"),
        mean_depth_km=("depth_km", "mean"),
        sum_energy=("energy", "sum"),
        first_year=("time", lambda s: s.dt.year.min()),
        last_year=("time", lambda s: s.dt.year.max()),
    ).reset_index()

    agg["log_energy"] = np.log1p(agg["sum_energy"])
    agg["events_per_year"] = agg["n_events"] / 20.0
    agg["years_active"] = (agg["last_year"] - agg["first_year"] + 1).clip(lower=1)

    grid = make_grid(cell)
    merged = grid.merge(agg, on=["cell_lat", "cell_lon"], how="left")
    merged["n_events"] = merged["n_events"].fillna(0).astype(int)
    merged["max_magnitude"] = merged["max_magnitude"].fillna(0.0)
    merged["mean_magnitude"] = merged["mean_magnitude"].fillna(0.0)
    merged["mean_depth_km"] = merged["mean_depth_km"].fillna(150.0)
    merged["log_energy"] = merged["log_energy"].fillna(0.0)
    merged["events_per_year"] = merged["events_per_year"].fillna(0.0)
    merged["years_active"] = merged["years_active"].fillna(0).astype(int)
    merged["sum_energy"] = merged["sum_energy"].fillna(0.0)

    # Risk labelling (heuristic thresholds for Santander seismicity).
    def label(row):
        if row["max_magnitude"] >= 4.5 or row["n_events"] >= 10:
            return "High"
        if row["max_magnitude"] >= 4.2 or row["n_events"] >= 3:
            return "Medium"
        return "Low"

    merged["risk_level"] = merged.apply(label, axis=1)

    # Distances that help the model generalise to new points.
    merged["dist_to_mesa_km"] = merged.apply(
        lambda r: _distance_km(r["cell_lat"], r["cell_lon"], MESA_CENTER[0], MESA_CENTER[1]), axis=1
    )
    nest_lat = float(agg.loc[agg["n_events"].idxmax(), "cell_lat"]) if not agg.empty else MESA_CENTER[0]
    nest_lon = float(agg.loc[agg["n_events"].idxmax(), "cell_lon"]) if not agg.empty else MESA_CENTER[1]
    merged["dist_to_seismic_nest_km"] = merged.apply(
        lambda r: _distance_km(r["cell_lat"], r["cell_lon"], nest_lat, nest_lon), axis=1
    )
    return merged


FEATURE_COLUMNS = [
    "cell_lat",
    "cell_lon",
    "n_events",
    "max_magnitude",
    "mean_magnitude",
    "mean_depth_km",
    "log_energy",
    "events_per_year",
    "years_active",
    "dist_to_mesa_km",
    "dist_to_seismic_nest_km",
]


def feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    return df[FEATURE_COLUMNS].copy()


def build_and_save(cell: float = CELL_SIZE_DEG) -> pd.DataFrame:
    df = load_earthquakes()
    features = aggregate_features(df, cell=cell)
    FEATURES_PATH.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(FEATURES_PATH, index=False)
    return features
