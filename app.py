from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.supabase_client import get_server_client, test_connection

st.set_page_config(page_title="Sismos · Santander", page_icon="🌎", layout="wide")
PAGE_SIZE = 100
SUMMARY_PAGE_SIZE = 1000
SISMO_COLUMNS = (
    "id_sismo,fecha_hora_utc,latitud,longitud,profundidad_km,magnitud,"
    "id_tipo_magnitud,fases,rms_seg,gap_grados,error_lat_km,error_long_km,"
    "error_prof_km,id_region"
)


def _client_or_raise():
    client = get_server_client()
    if client is None:
        raise RuntimeError("Configura SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en el servidor.")
    return client


@st.cache_data(ttl=600, show_spinner="Consultando los sismos existentes en Supabase...")
def load_summary() -> dict:
    """Load existing sismo rows in read-only pages and calculate display summaries."""
    client = _client_or_raise()
    first = client.table("sismo").select(
        "fecha_hora_utc,magnitud,profundidad_km,id_tipo_magnitud", count="exact"
    ).order("id_sismo").range(0, SUMMARY_PAGE_SIZE - 1).execute()
    rows = list(first.data or [])
    total = first.count if first.count is not None else len(rows)

    def fetch_summary_page(start: int) -> list[dict]:
        end = min(start + SUMMARY_PAGE_SIZE, total) - 1
        page = client.table("sismo").select(
            "fecha_hora_utc,magnitud,profundidad_km,id_tipo_magnitud"
        ).order("id_sismo").range(start, end).execute()
        return page.data or []

    page_starts = range(SUMMARY_PAGE_SIZE, total, SUMMARY_PAGE_SIZE)
    with ThreadPoolExecutor(max_workers=8) as pool:
        for batch in pool.map(fetch_summary_page, page_starts):
            rows.extend(batch)

    if len(rows) != total:
        raise RuntimeError("La API no devolvió todos los registros para el resumen.")
    data = pd.DataFrame(rows)
    if data.empty:
        return {
            "total": 0, "min_magnitude": None, "max_magnitude": None,
            "first_date": None, "last_date": None, "mean_magnitude": None,
            "mean_depth": None,
            "by_type": pd.DataFrame(columns=["id_tipo_magnitud", "Sismos"]),
            "by_year": pd.DataFrame(columns=["Año", "Sismos"]),
        }

    data["fecha_hora_utc"] = pd.to_datetime(data["fecha_hora_utc"], utc=True, errors="coerce")
    data["magnitud"] = pd.to_numeric(data["magnitud"], errors="coerce")
    data["profundidad_km"] = pd.to_numeric(data["profundidad_km"], errors="coerce")
    by_type = (
        data.groupby("id_tipo_magnitud", dropna=False)
        .size().rename("Sismos").reset_index()
    )
    years = data.dropna(subset=["fecha_hora_utc"]).assign(
        Año=lambda frame: frame["fecha_hora_utc"].dt.year
    )
    by_year = years.groupby("Año").size().rename("Sismos").reset_index()
    magnitudes = data["magnitud"].dropna()
    depths = data["profundidad_km"].dropna()
    dates = data["fecha_hora_utc"].dropna()
    return {
        "total": total,
        "min_magnitude": float(magnitudes.min()) if not magnitudes.empty else None,
        "max_magnitude": float(magnitudes.max()) if not magnitudes.empty else None,
        "first_date": dates.min() if not dates.empty else None,
        "last_date": dates.max() if not dates.empty else None,
        "mean_magnitude": float(magnitudes.mean()) if not magnitudes.empty else None,
        "mean_depth": float(depths.mean()) if not depths.empty else None,
        "by_type": by_type,
        "by_year": by_year,
    }


@st.cache_data(ttl=600, show_spinner=False)
def load_catalog_tables() -> dict[str, pd.DataFrame]:
    client = _client_or_raise()
    regions = client.table("region").select("id_region,nombre").order("id_region").execute()
    types = client.table("tipo_magnitud").select(
        "id_tipo_magnitud,nombre"
    ).order("id_tipo_magnitud").execute()
    return {
        "regiones": pd.DataFrame(regions.data or [], columns=["id_region", "nombre"]),
        "tipos": pd.DataFrame(types.data or [], columns=["id_tipo_magnitud", "nombre"]),
    }


@st.cache_data(ttl=60, show_spinner=False)
def count_sismos(region_id: int | None, min_magnitude: float, max_magnitude: float) -> int:
    query = _client_or_raise().table("sismo").select("id_sismo", count="exact")
    query = query.gte("magnitud", min_magnitude).lte("magnitud", max_magnitude)
    if region_id is not None:
        query = query.eq("id_region", region_id)
    result = query.limit(1).execute()
    return int(result.count or 0)


@st.cache_data(ttl=60, show_spinner=False)
def load_sismos(page: int, region_id: int | None, min_magnitude: float, max_magnitude: float) -> pd.DataFrame:
    query = _client_or_raise().table("sismo").select(SISMO_COLUMNS)
    query = query.gte("magnitud", min_magnitude).lte("magnitud", max_magnitude)
    if region_id is not None:
        query = query.eq("id_region", region_id)
    offset = max(0, page - 1) * PAGE_SIZE
    result = (
        query.order("fecha_hora_utc", desc=True)
        .order("id_sismo", desc=True)
        .range(offset, offset + PAGE_SIZE - 1)
        .execute()
    )
    return pd.DataFrame(result.data or [])


def _display_sismos(records: pd.DataFrame, catalogs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    if records.empty:
        return records
    types = catalogs["tipos"].rename(columns={"nombre": "nombre_tipo"})
    regions = catalogs["regiones"].rename(columns={"nombre": "nombre_region"})
    result = records.merge(types, on="id_tipo_magnitud", how="left")
    result = result.merge(regions, on="id_region", how="left")
    return result.rename(columns={
        "id_sismo": "ID sismo",
        "fecha_hora_utc": "Fecha y hora UTC",
        "latitud": "Latitud",
        "longitud": "Longitud",
        "profundidad_km": "Profundidad (km)",
        "magnitud": "Magnitud",
        "nombre_tipo": "Tipo de magnitud",
        "nombre_region": "Región",
        "fases": "Fases",
        "rms_seg": "RMS (s)",
        "gap_grados": "Gap (°)",
        "error_lat_km": "Error latitud (km)",
        "error_long_km": "Error longitud (km)",
        "error_prof_km": "Error profundidad (km)",
    })


def main() -> None:
    st.title("Sismos de Santander")
    st.caption("Datos consultados en modo lectura desde las tablas existentes: sismo, region y tipo_magnitud.")

    server_client = get_server_client()
    connected, _ = test_connection(server_client)
    if server_client is None or not connected:
        st.error("No se pudo conectar con Supabase. Revisa SUPABASE_URL y las credenciales configuradas en el servidor.")
        st.stop()

    try:
        with st.spinner("Cargando datos de Supabase..."):
            summary = load_summary()
            catalogs = load_catalog_tables()
    except Exception as exc:
        st.error(f"No se pudieron leer las tablas existentes ({type(exc).__name__}). Revisa los permisos de lectura.")
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
            if not summary["by_year"].empty:
                st.bar_chart(summary["by_year"].set_index("Año"), width="stretch")
            else:
                st.info("No hay registros para mostrar.")
        with right:
            st.subheader("Registros por tipo de magnitud")
            by_type = summary["by_type"].merge(
                catalogs["tipos"], on="id_tipo_magnitud", how="left"
            )
            by_type["Tipo de magnitud"] = by_type["nombre"].fillna("Sin tipo")
            st.dataframe(
                by_type[["Tipo de magnitud", "Sismos"]],
                width="stretch",
                hide_index=True,
            )

    with tab_sismos:
        st.subheader("Tabla sismo")
        if summary["total"] == 0 or summary["min_magnitude"] is None:
            st.info("La tabla sismo no contiene registros para mostrar.")
        else:
            filters = st.columns([2, 2])
            min_mag = summary["min_magnitude"]
            max_mag = summary["max_magnitude"]
            if min_mag < max_mag:
                magnitude_range = filters[0].slider(
                    "Rango de magnitud", min_value=min_mag, max_value=max_mag,
                    value=(min_mag, max_mag), step=0.1,
                )
            else:
                magnitude_range = (min_mag, max_mag)
                filters[0].caption(f"Magnitud disponible: {min_mag:g}")

            regions = catalogs["regiones"]
            region_options = {"Todas": None}
            region_options.update({row["nombre"]: int(row["id_region"]) for _, row in regions.iterrows()})
            selected_region_name = filters[1].selectbox("Región", list(region_options))
            selected_region = region_options[selected_region_name]
            total_filtered = count_sismos(selected_region, magnitude_range[0], magnitude_range[1])
            total_pages = max(1, (total_filtered + PAGE_SIZE - 1) // PAGE_SIZE)
            current_page = min(max(int(st.session_state.get("sismos_page", 1)), 1), total_pages)
            st.session_state["sismos_page"] = current_page
            previous_col, page_col, next_col = st.columns([1, 3, 1])
            if previous_col.button("‹", disabled=current_page <= 1, key="sismos_previous"):
                st.session_state["sismos_page"] = current_page - 1
                st.rerun()
            page_col.caption(f"Página {current_page} / {total_pages}")
            if next_col.button("›", disabled=current_page >= total_pages, key="sismos_next"):
                st.session_state["sismos_page"] = current_page + 1
                st.rerun()

            try:
                records = load_sismos(current_page, selected_region, magnitude_range[0], magnitude_range[1])
                records = _display_sismos(records, catalogs)
                st.dataframe(records, width="stretch", hide_index=True)
                start_row = (current_page - 1) * PAGE_SIZE + 1 if total_filtered else 0
                end_row = min(current_page * PAGE_SIZE, total_filtered)
                st.caption(f"Mostrando {start_row:,}–{end_row:,} de {total_filtered:,} registros · {PAGE_SIZE} por página.")
            except Exception as exc:
                st.error(f"No se pudieron cargar los sismos ({type(exc).__name__}).")

    with tab_regiones:
        st.subheader("Tabla region")
        st.dataframe(catalogs["regiones"], width="stretch", hide_index=True)
        st.caption(f"{len(catalogs['regiones']):,} registros existentes.")

    with tab_tipos:
        st.subheader("Tabla tipo_magnitud")
        st.dataframe(catalogs["tipos"], width="stretch", hide_index=True)
        st.caption(f"{len(catalogs['tipos']):,} registros existentes.")


if __name__ == "__main__":
    main()
