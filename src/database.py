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
