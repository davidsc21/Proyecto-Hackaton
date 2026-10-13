"""Direct PostgreSQL helpers for the Supabase database."""
from __future__ import annotations

import psycopg2
from src.config import get_database_url


def get_connection(prefer_direct: bool = False):
    url = get_database_url(prefer_direct=prefer_direct)
    if not url:
        raise RuntimeError("DATABASE_URL is not configured in .env")
    return psycopg2.connect(url, connect_timeout=15)


def test_connection() -> tuple[bool, str]:
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("select current_database(), current_user, now() at time zone 'utc'")
            db, user, now = cur.fetchone()
        conn.close()
        return True, "Connected to PostgreSQL ({}) as {} at {}.".format(db, user, now)
    except Exception as exc:
        return False, "PostgreSQL connection failed: {}".format(exc)


def list_tables(schema: str = "public") -> list[str]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select table_name
                from information_schema.tables
                where table_schema = %s and table_type = 'BASE TABLE'
                order by table_name;
                """,
                (schema,),
            )
            return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def run_schema(path: str) -> None:
    with open(path, encoding="utf-8") as f:
        sql = f.read()
    conn = get_connection(prefer_direct=False)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    finally:
        conn.close()


def seed_earthquakes(csv_path: str) -> int:
    import pandas as pd
    from psycopg2.extras import execute_values

    df = pd.read_csv(csv_path)
    if df.empty:
        return 0
    conn = get_connection()
    try:
        rows = [
            (
                r.get("event_id"),
                r.get("time"),
                r.get("latitude"),
                r.get("longitude"),
                r.get("depth_km"),
                r.get("magnitude"),
                r.get("mag_type"),
                r.get("place"),
                r.get("status"),
                r.get("url"),
            )
            for r in df.to_dict(orient="records")
        ]
        with conn.cursor() as cur:
            execute_values(
                cur,
                """
                insert into public.earthquakes
                    (event_id, time, latitude, longitude, depth_km, magnitude, mag_type, place, status, url)
                values %s
                on conflict (event_id) do nothing;
                """,
                rows,
                page_size=200,
            )
        conn.commit()
        with conn.cursor() as cur:
            cur.execute("select count(*) from public.earthquakes")
            return cur.fetchone()[0]
    finally:
        conn.close()


def seed_risk_zones(features_df) -> int:
    import pandas as pd
    from psycopg2.extras import execute_values

    if isinstance(features_df, str):
        features_df = pd.read_csv(features_df)
    try:
        from pathlib import Path as _Path

        if isinstance(features_df, _Path):
            features_df = pd.read_csv(features_df)
    except Exception:  # noqa: BLE001
        pass

    if "cell_id" not in features_df.columns:
        features_df = features_df.copy()
        features_df["cell_id"] = features_df["cell_lat"].astype(str) + "_" + features_df["cell_lon"].astype(str)

    conn = get_connection()
    try:
        rows = []
        for r in features_df.to_dict(orient="records"):
            rows.append(
                (
                    r.get("cell_id"),
                    float(r["cell_lat"]),
                    float(r["cell_lon"]),
                    int(r.get("n_events", 0)),
                    float(r.get("max_magnitude", 0.0)),
                    float(r.get("mean_magnitude", 0.0)),
                    float(r.get("mean_depth_km", 150.0)),
                    float(r.get("log_energy", 0.0)),
                    float(r.get("events_per_year", 0.0)),
                    str(r.get("risk_level", "Low")),
                    float(r.get("dist_to_mesa_km", 0.0)),
                    float(r.get("dist_to_seismic_nest_km", 0.0)),
                )
            )
        with conn.cursor() as cur:
            execute_values(
                cur,
                """
                insert into public.risk_zones
                    (cell_id, cell_lat, cell_lon, n_events, max_magnitude, mean_magnitude,
                     mean_depth_km, log_energy, events_per_year, risk_level,
                     dist_to_mesa_km, dist_to_seismic_nest_km)
                values %s
                on conflict (cell_id) do update set
                    cell_lat = excluded.cell_lat,
                    cell_lon = excluded.cell_lon,
                    n_events = excluded.n_events,
                    max_magnitude = excluded.max_magnitude,
                    mean_magnitude = excluded.mean_magnitude,
                    mean_depth_km = excluded.mean_depth_km,
                    log_energy = excluded.log_energy,
                    events_per_year = excluded.events_per_year,
                    risk_level = excluded.risk_level,
                    dist_to_mesa_km = excluded.dist_to_mesa_km,
                    dist_to_seismic_nest_km = excluded.dist_to_seismic_nest_km,
                    updated_at = now();
                """,
                rows,
                page_size=200,
            )
        conn.commit()
        with conn.cursor() as cur:
            cur.execute("select count(*) from public.risk_zones")
            return cur.fetchone()[0]
    finally:
        conn.close()


def record_model_run(model_name: str = "RandomForest", metrics=None) -> None:
    import json

    payload = metrics if metrics is not None else {}
    try:
        payload = json.loads(json.dumps(payload, default=str))
    except Exception:  # noqa: BLE001
        payload = {"raw": str(payload)}
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "insert into public.model_runs (model_name, metrics) values (%s, %s)",
                (model_name, json.dumps(payload)),
            )
        conn.commit()
    finally:
        conn.close()


def sync_all(features_df=None) -> dict:
    from pathlib import Path

    result = {}
    try:
        result["earthquakes"] = seed_earthquakes(
            str(Path(__file__).resolve().parents[1] / "data" / "raw" / "earthquakes_santander.csv")
        )
    except Exception as exc:  # noqa: BLE001
        result["earthquakes_error"] = str(exc)
    try:
        if features_df is None:
            from src.features import aggregate_features, load_earthquakes

            features_df = aggregate_features(load_earthquakes())
        result["risk_zones"] = seed_risk_zones(features_df)
    except Exception as exc:  # noqa: BLE001
        result["risk_zones_error"] = str(exc)
    return result
