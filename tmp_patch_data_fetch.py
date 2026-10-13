from pathlib import Path
p = Path("src/data_fetch.py")
s = p.read_text()
addition = '''

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
'''
# insert before load_raw? just append
if "def load_sismo" not in s:
    p.write_text(s + addition)
    print("patched")
else:
    print("already present")
PY