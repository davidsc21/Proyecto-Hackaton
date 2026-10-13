from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database import get_connection, test_connection

st.set_page_config(page_title="Sismos · Santander", page_icon="🌎", layout="wide")
PAGE_SIZE = 100


@st.cache_data(ttl=60, show_spinner=False)
def load_summary() -> dict:
    connection = get_connection()
    connection.set_session(readonly=True)
    try:
        with connection.cursor() as cur:
            cur.execute("""
                select count(*), min(magnitud), max(magnitud), min(fecha_hora_utc), max(fecha_hora_utc),
                       avg(magnitud), avg(profundidad_km)
                from public.sismo
            """)
            total, min_magnitude, max_magnitude, first_date, last_date, mean_magnitude, mean_depth = cur.fetchone()
            cur.execute("""
                select coalesce(t.nombre, 'Sin tipo'), count(*)
                from public.sismo s
                left join public.tipo_magnitud t on t.id_tipo_magnitud = s.id_tipo_magnitud
                group by t.nombre order by count(*) desc, t.nombre
            """)
            by_type = cur.fetchall()
            cur.execute("""
                select extract(year from fecha_hora_utc)::integer as anio, count(*) as sismos
                from public.sismo
                group by anio order by anio
            """)
            by_year = cur.fetchall()
        return {
            "total": total or 0,
            "min_magnitude": float(min_magnitude) if min_magnitude is not None else None,
            "first_date": first_date,
            "last_date": last_date,
            "mean_magnitude": float(mean_magnitude) if mean_magnitude is not None else None,
            "max_magnitude": float(max_magnitude) if max_magnitude is not None else None,
            "mean_depth": float(mean_depth) if mean_depth is not None else None,
            "by_type": pd.DataFrame(by_type, columns=["Tipo de magnitud", "Sismos"]),
            "by_year": pd.DataFrame(by_year, columns=["Año", "Sismos"]),
        }
    finally:
        connection.close()


@st.cache_data(ttl=60, show_spinner=False)
def load_catalog_tables() -> dict[str, pd.DataFrame]:
    connection = get_connection()
    connection.set_session(readonly=True)
    try:
        return {
            "regiones": pd.read_sql_query(
                "select id_region, nombre from public.region order by id_region", connection
            ),
            "tipos": pd.read_sql_query(
                "select id_tipo_magnitud, nombre from public.tipo_magnitud order by id_tipo_magnitud", connection
            ),
        }
    finally:
        connection.close()


@st.cache_data(ttl=60, show_spinner=False)
def load_sismos(page: int, region_id: int | None, min_magnitude: float, max_magnitude: float) -> pd.DataFrame:
    connection = get_connection()
    connection.set_session(readonly=True)
    try:
        query = """
            select s.id_sismo as "ID sismo",
                   s.fecha_hora_utc as "Fecha y hora UTC",
                   s.latitud as "Latitud",
                   s.longitud as "Longitud",
                   s.profundidad_km as "Profundidad (km)",
                   s.magnitud as "Magnitud",
                   t.nombre as "Tipo de magnitud",
                   s.fases as "Fases",
                   s.rms_seg as "RMS (s)",
                   s.gap_grados as "Gap (°)",
                   s.error_lat_km as "Error latitud (km)",
                   s.error_long_km as "Error longitud (km)",
                   s.error_prof_km as "Error profundidad (km)",
                   r.nombre as "Región"
            from public.sismo s
            left join public.tipo_magnitud t on t.id_tipo_magnitud = s.id_tipo_magnitud
            left join public.region r on r.id_region = s.id_region
            where s.magnitud between %s and %s
              and (%s is null or s.id_region = %s)
            order by s.fecha_hora_utc desc, s.id_sismo desc
            limit %s offset %s
        """
        offset = (page - 1) * PAGE_SIZE
        return pd.read_sql_query(
            query,
            connection,
            params=(min_magnitude, max_magnitude, region_id, region_id, PAGE_SIZE, offset),
        )
    finally:
        connection.close()


@st.cache_data(ttl=60, show_spinner=False)
def count_sismos(region_id: int | None, min_magnitude: float, max_magnitude: float) -> int:
    connection = get_connection()
    connection.set_session(readonly=True)
    try:
        with connection.cursor() as cur:
            cur.execute(
                "select count(*) from public.sismo where magnitud between %s and %s and (%s is null or id_region = %s)",
                (min_magnitude, max_magnitude, region_id, region_id),
            )
            return cur.fetchone()[0]
    finally:
        connection.close()


def main() -> None:
    st.title("Sismos de Santander")
    st.caption("Consulta de las tablas existentes en Supabase PostgreSQL: sismo, region y tipo_magnitud.")

    connected, message = test_connection()
    if not connected:
        st.error(f"No fue posible conectar con Supabase: {message}")
        st.info("Verifica la variable de conexión PostgreSQL configurada para el proyecto.")
        st.stop()

    try:
        summary = load_summary()
        catalogs = load_catalog_tables()
    except Exception as exc:
        st.error(f"No se pudieron leer las tablas de Supabase: {exc}")
        st.stop()

    st.success("Conexión activa · consultas de solo lectura")
    metric_cols = st.columns(4)
    metric_cols[0].metric("Sismos registrados", f"{summary['total']:,}")
    metric_cols[1].metric("Magnitud media", f"{summary['mean_magnitude']:.2f}" if summary["mean_magnitude"] is not None else "—")
    metric_cols[2].metric("Magnitud máxima", f"{summary['max_magnitude']:.2f}" if summary["max_magnitude"] is not None else "—")
    metric_cols[3].metric("Profundidad media", f"{summary['mean_depth']:.2f} km" if summary["mean_depth"] is not None else "—")
    if summary["first_date"] is not None:
        st.caption(f"Periodo disponible: {summary['first_date']} a {summary['last_date']} (UTC)")

    tab_resumen, tab_sismos, tab_regiones, tab_tipos = st.tabs(
        ["Resumen", "Sismos", "Regiones", "Tipos de magnitud"]
    )

    with tab_resumen:
        left, right = st.columns(2)
        with left:
            st.subheader("Registros por año")
            st.bar_chart(summary["by_year"].set_index("Año"), use_container_width=True)
        with right:
            st.subheader("Registros por tipo de magnitud")
            st.dataframe(summary["by_type"], use_container_width=True, hide_index=True)

    with tab_sismos:
        st.subheader("Tabla sismo")
        filters = st.columns([2, 2, 1])
        min_mag = float(summary["min_magnitude"] or 0.0)
        max_mag = float(summary["max_magnitude"] or min_mag)
        magnitude_range = filters[0].slider(
            "Rango de magnitud", min_value=min_mag, max_value=max_mag,
            value=(min_mag, max_mag), step=0.1,
        )
        regions = catalogs["regiones"]
        region_options = {"Todas": None}
        region_options.update({row["nombre"]: int(row["id_region"]) for _, row in regions.iterrows()})
        selected_region_name = filters[1].selectbox("Región", list(region_options))
        selected_region = region_options[selected_region_name]
        total_filtered = count_sismos(selected_region, magnitude_range[0], magnitude_range[1])
        total_pages = max(1, (total_filtered + PAGE_SIZE - 1) // PAGE_SIZE)
        page = filters[2].number_input("Página", min_value=1, max_value=total_pages, value=1, step=1)
        try:
            records = load_sismos(int(page), selected_region, magnitude_range[0], magnitude_range[1])
            st.dataframe(records, use_container_width=True, hide_index=True)
            start_row = (int(page) - 1) * PAGE_SIZE + 1 if total_filtered else 0
            end_row = min(int(page) * PAGE_SIZE, total_filtered)
            st.caption(f"Mostrando {start_row:,}–{end_row:,} de {total_filtered:,} registros · {PAGE_SIZE} por página.")
        except Exception as exc:
            st.error(f"No se pudieron cargar los registros de sismo: {exc}")

    with tab_regiones:
        st.subheader("Tabla region")
        st.dataframe(catalogs["regiones"], use_container_width=True, hide_index=True)
        st.caption(f"{len(catalogs['regiones']):,} registros existentes.")

    with tab_tipos:
        st.subheader("Tabla tipo_magnitud")
        st.dataframe(catalogs["tipos"], use_container_width=True, hide_index=True)
        st.caption(f"{len(catalogs['tipos']):,} registros existentes.")


if __name__ == "__main__":
    main()

