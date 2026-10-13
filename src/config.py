"""Central configuration for the seismic-risk project."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=False)

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()

# Geographic focus
CELL_SIZE_DEG = 0.1
SANTANDER_BBOX = (5.7, 8.5, -74.7, -72.2)  # min_lat, max_lat, min_lon, max_lon
MESA_CENTER = (6.75, -73.10)  # Mesa de los Santos approx.
MESA_BBOX = (6.4, 7.2, -73.4, -72.7)

# Time window
START_YEAR = 2005

# Model
MODEL_PATH = PROJECT_ROOT / "models" / "seismic_risk_model.joblib"
FEATURES_PATH = PROJECT_ROOT / "data" / "processed" / "risk_zones.csv"
EARTHQUAKES_PATH = PROJECT_ROOT / "data" / "raw" / "earthquakes_santander.csv"


def has_supabase() -> bool:
    return bool(SUPABASE_URL and SUPABASE_KEY)
