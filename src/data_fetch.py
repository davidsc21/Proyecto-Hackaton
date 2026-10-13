"""Fetch seismic events from the USGS FDSN catalog for Santander, Colombia."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"

SANTANDER_BBOX = {
    "minlatitude": 5.7,
    "maxlatitude": 8.5,
    "minlongitude": -74.7,
    "maxlongitude": -72.2,
}

MESA_BBOX = {
    "minlatitude": 6.4,
    "maxlatitude": 7.2,
    "minlongitude": -73.4,
    "maxlongitude": -72.7,
}

USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"


def fetch_year(year: int, min_magnitude: float = 2.0, bbox: dict | None = None) -> pd.DataFrame:
    """Fetch all events for a single calendar year."""
    bbox = bbox or SANTANDER_BBOX
    params = {
        "format": "geojson",
        "starttime": f"{year}-01-01",
        "endtime": f"{year}-12-31",
        "minmagnitude": min_magnitude,
        "orderby": "time",
        "limit": 20000,
        **bbox,
    }
    response = requests.get(USGS_URL, params=params, timeout=120)
    response.raise_for_status()
    payload = response.json()
    rows = []
    for feature in payload.get("features", []):
        props = feature.get("properties", {})
        coords = feature.get("geometry", {}).get("coordinates", [None, None, None])
        rows.append(
            {
                "event_id": feature.get("id"),
                "time": datetime.fromtimestamp(props["time"] / 1000, tz=timezone.utc).isoformat(),
                "latitude": coords[1],
                "longitude": coords[0],
                "depth_km": coords[2],
                "magnitude": props.get("mag"),
                "mag_type": props.get("magType"),
                "place": props.get("place"),
                "status": props.get("status"),
                "url": props.get("url"),
            }
        )
    return pd.DataFrame(rows)


def fetch_santander_history(start_year: int = 2005, end_year: int | None = None, min_magnitude: float = 2.0) -> pd.DataFrame:
    """Fetch Santander seismic history, one year at a time (avoids API caps)."""
    end_year = end_year or datetime.now(timezone.utc).year
    frames = []
    for year in range(start_year, end_year + 1):
        print(f"Fetching {year}...")
        try:
            frame = fetch_year(year, min_magnitude=min_magnitude)
            frames.append(frame)
            time.sleep(0.4)
        except Exception as exc:  # noqa: BLE001 - keep partial progress
            print(f"  failed for {year}: {exc}")
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out = out.dropna(subset=["latitude", "longitude", "magnitude", "time"])
    out = out.drop_duplicates(subset=["event_id"])
    return out


def save_raw(df: pd.DataFrame, filename: str = "earthquakes_santander.csv") -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / filename
    df.to_csv(path, index=False)
    return path


def load_raw(filename: str = "earthquakes_santander.csv") -> pd.DataFrame:
    path = RAW_DIR / filename
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
    return df


def events_to_supabase(df: pd.DataFrame, client) -> int:
    """Upsert events into Supabase. Returns number of rows sent."""
    if df.empty or client is None:
        return 0
    records = []
    for row in df.to_dict(orient="records"):
        records.append(
            {
                "event_id": row["event_id"],
                "time": pd.Timestamp(row["time"]).isoformat() if not isinstance(row["time"], str) else row["time"],
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
                "depth_km": float(row["depth_km"]) if pd.notna(row["depth_km"]) else None,
                "magnitude": float(row["magnitude"]),
                "mag_type": row.get("mag_type"),
                "place": row.get("place"),
                "status": row.get("status"),
                "url": row.get("url"),
            }
        )
    total = 0
    chunk = 500
    for i in range(0, len(records), chunk):
        client.table("earthquakes").upsert(records[i : i + chunk], on_conflict="event_id").execute()
        total += len(records[i : i + chunk])
    return total


def load_sismo() -> pd.DataFrame:
    """Load seismic events from Supabase PostgreSQL (table: sismo)."""
    from src.database import get_connection

    try:
        conn = get_connection()
    except Exception:  # noqa: BLE001
        return pd.DataFrame()

    try:
        query = """
        select
            s.id_sismo::text            as event_id,
            s.fecha_hora_utc            as time,
            s.latitud                   as latitude,
            s.longitud                  as longitude,
            s.profundidad_km            as depth_km,
            s.magnitud                  as magnitude,
            t.nombre                    as mag_type,
            r.nombre                    as place,
            'reported'::text            as status,
            null::text                  as url
        from public.sismo s
        left join public.tipo_magnitud t
            on s.id_tipo_magnitud = t.id_tipo_magnitud
        left join public.region r
            on s.id_region = r.id_region
        order by s.fecha_hora_utc;
        """
        df = pd.read_sql(query, conn)
    finally:
        conn.close()

    if df.empty:
        return df
    for col in ["latitude", "longitude", "depth_km", "magnitude"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
    df = df.dropna(subset=["latitude", "longitude", "magnitude", "time"])
    return df
