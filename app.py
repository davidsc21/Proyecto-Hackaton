"""Streamlit application for seismic-risk analysis in Santander, Colombia."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import EARTHQUAKES_PATH, FEATURES_PATH, MODEL_PATH, MESA_CENTER
from src.features import FEATURE_COLUMNS, aggregate_features, load_earthquakes, build_and_save
from src.model import FEATURE_COLUMNS as MODEL_FEATURES, load_model, predict, train
from src.supabase_client import get_client, test_connection
from src.data_fetch import load_raw

st.set_page_config(
    page_title="Riesgo Sísmico - Santander",
    page_icon="earthquake",
    layout="wide",
)

RISK_COLORS = {"High": "#d62728", "Medium": "#ff7f0e", "Low": "#2ca02c"}


@st.cache_data(show_spinner=False)
def cached_features() -> pd.DataFrame:
    if FEATURES_PATH.exists():
        return pd.read_csv(FEATURES_PATH)
    features = build_and_save()
    return features


@st.cache_data(show_spinner=False)
def cached_earthquakes() -> pd.DataFrame:
    if EARTHQUAKES_PATH.exists():
        return pd.read_csv(EARTHQUAKES_PATH)
    return load_raw()


def ensure_model():
    bundle = load_model()
    if bundle is None:
        features = cached_features()
        _, _ = train(features)
        bundle = load_model()
    return bundle


def risk_badge(level: str) -> str:
    colors = {"High": "red", "Medium": "orange", "Low": "green"}
    return f":{colors.get(level, 'gray')}[{level}]"


def local_features(lat: float, lon: float, radius_deg: float = 0.15) -> pd.DataFrame:
    eq = cached_earthquakes()
    if eq.empty:
        sub = pd.DataFrame()
    else:
        mask = (
            eq["latitude"].between(lat - radius_deg, lat + radius_deg)
            & eq["longitude"].between(lon - radius_deg, lon + radius_deg)
        )
        sub = eq.loc[mask].copy()

    if sub.empty:
        n_events = 0
        max_mag = 0.0
        mean_mag = 0.0
        mean_depth = 150.0
        log_energy = 0.0
    else:
        sub["energy"] = 10 ** (1.5 * sub["magnitude"])
        n_events = len(sub)
        max_mag = float(sub["magnitude"].max())
        mean_mag = float(sub["magnitude"].mean())
        mean_depth = float(sub["depth_km"].mean())
        log_energy = float(math.log1p(sub["energy"].sum()))

    years_active = 20 if n_events else 0
    events_per_year = n_events / 20.0
    dist_mesa = math.hypot(lat - MESA_CENTER[0], lon - MESA_CENTER[1]) * 111.0
    # Use seismic nest approximated from data center
    nest_lat, nest_lon = 6.78, -73.02
    dist_nest = math.hypot(lat - nest_lat, lon - nest_lon) * 111.0

    row = {
        "cell_lat": lat,
        "cell_lon": lon,
        "n_events": n_events,
        "max_magnitude": max_mag,
        "mean_magnitude": mean_mag,
        "mean_depth_km": mean_depth,
        "log_energy": log_energy,
        "events_per_year": events_per_year,
        "years_active": years_active,
        "dist_to_mesa_km": dist_mesa,
        "dist_to_seismic_nest_km": dist_nest,
    }
    return pd.DataFrame([row], columns=MODEL_FEATURES)


def main():
    st.title("Clasificación del riesgo sísmico - Santander (Mesa de los Santos)")
    st.caption("Análisis del comportamiento sísmico de Santander en los últimos 20 años usando Machine Learning.")

    bundle = ensure_model()
    features = cached_features()
    earthquakes = cached_earthquakes()

    client = get_client()
    connected, status_msg = test_connection(client)

    # Sidebar
    with st.sidebar:
        st.header("Estado")
        if connected:
            st.success(status_msg)
        else:
            st.warning(status_msg)
        st.metric("Eventos sísmicos", len(earthquakes))
        st.metric("Celdas analizadas", len(features))
        st.metric("Modelo", "RandomForest")

        if st.button("Re-entrenar modelo"):
            features2 = build_and_save()
            train(features2)
            st.cache_data.clear()
            st.rerun()

    tabs = st.tabs(["Mapa de riesgo", "Datos sísmicos", "Modelo ML", "Predicción", "Supabase"])

    # --- Tab 1: Risk map ---
    with tabs[0]:
        col1, col2 = st.columns([3, 1])
        with col2:
            selected = st.multiselect("Nivel de riesgo", ["High", "Medium", "Low"], default=["High", "Medium", "Low"])
            size_by = st.selectbox("Tamaño por", ["n_events", "max_magnitude", "log_energy"], index=0)
        with col1:
            show_df = features[features["risk_level"].isin(selected)].copy()
            fig = px.scatter_map(
                show_df,
                lat="cell_lat",
                lon="cell_lon",
                color="risk_level",
                size=size_by,
                color_discrete_map=RISK_COLORS,
                hover_data=["n_events", "max_magnitude", "mean_magnitude", "mean_depth_km"],
                zoom=7,
                height=650,
                title="Riesgo sísmico por celda (Santander)",
            )
            fig.update_layout(map_style="open-street-map")
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("**Distribución de riesgo**")
        st.bar_chart(features["risk_level"].value_counts())

    # --- Tab 2: Earthquake data ---
    with tabs[1]:
        st.subheader("Eventos sísmicos (USGS) - Santander")
        st.dataframe(
            earthquakes[["time", "latitude", "longitude", "depth_km", "magnitude", "mag_type", "place"]]
            .sort_values("time", ascending=False)
            .head(2000),
            use_container_width=True,
            hide_index=True,
        )
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Magnitud por año**")
            eq = earthquakes.copy()
            eq["year"] = pd.to_datetime(eq["time"], utc=True, errors="coerce").dt.year
            st.line_chart(eq.groupby("year")["magnitude"].agg(["count", "max"]))
        with c2:
            st.markdown("**Magnitudes**")
            st.bar_chart(earthquakes["magnitude"].round(1).value_counts().sort_index())

    # --- Tab 3: Model ---
    with tabs[2]:
        metrics = bundle.get("metrics", {})
        st.subheader("Métricas del modelo")
        c1, c2, c3 = st.columns(3)
        report = metrics.get("classification_report", {})
        accuracy = report.get("accuracy", 0.0)
        c1.metric("Accuracy", f"{accuracy:.3f}")
        c2.metric("Entrenamiento", metrics.get("n_train", 0))
        c3.metric("Prueba", metrics.get("n_test", 0))

        st.markdown("**Reporte de clasificación**")
        rows = []
        for cls in ["High", "Low", "Medium"]:
            if cls in report:
                r = report[cls]
                rows.append(
                    {
                        "Clase": cls,
                        "Precision": round(r.get("precision", 0), 3),
                        "Recall": round(r.get("recall", 0), 3),
                        "F1": round(r.get("f1-score", 0), 3),
                        "Soporte": r.get("support", 0),
                    }
                )
        st.dataframe(pd.DataFrame(rows), hide_index=True)

        st.markdown("**Matriz de confusión**")
        cm = metrics.get("confusion_matrix", [])
        labels = metrics.get("classes", ["High", "Low", "Medium"])
        if cm:
            st.dataframe(pd.DataFrame(cm, index=labels, columns=labels))

        st.markdown("**Importancia de variables**")
        model = bundle["model"].named_steps["classifier"]
        imp = pd.Series(model.feature_importances_, index=MODEL_FEATURES).sort_values(ascending=True)
        st.bar_chart(imp)

    # --- Tab 4: Prediction ---
    with tabs[3]:
        st.subheader("Predecir riesgo para un punto / zona")
        col1, col2 = st.columns(2)
        with col1:
            lat = st.number_input("Latitud", value=float(MESA_CENTER[0]), format="%.5f")
            lon = st.number_input("Longitud", value=float(MESA_CENTER[1]), format="%.5f")
            radius = st.slider("Radio de análisis (grados)", 0.05, 0.5, 0.15, 0.05)
        with col2:
            st.markdown("El modelo toma los eventos sísmicos dentro del radio indicado y calcula las features en tiempo real.")
            if st.button("Predecir riesgo"):
                X = local_features(lat, lon, radius)
                result = predict(X=X)
                if result is None:
                    st.error("Modelo no disponible.")
                else:
                    pred, proba, _ = result
                    pred = pred[0]
                    st.markdown(f"### Riesgo estimado: {risk_badge(pred)}")
                    if proba is not None:
                        proba_df = pd.DataFrame(proba, columns=bundle["model"].classes_)
                        st.bar_chart(proba_df.T)
                    st.json(X.iloc[0].to_dict())

                    # Show nearby events
                    ev = earthquakes.copy()
                    mask = (
                        ev["latitude"].between(lat - radius, lat + radius)
                        & ev["longitude"].between(lon - radius, lon + radius)
                    )
                    near = ev.loc[mask]
                    st.markdown(f"**Eventos cercanos:** {len(near)}")
                    if not near.empty:
                        st.dataframe(
                            near[["time", "magnitude", "depth_km", "place"]].sort_values("time", ascending=False).head(20),
                            use_container_width=True,
                            hide_index=True,
                        )

                    # Optional Supabase logging
                    if connected:
                        try:
                            prob_map = {}
                            if proba is not None:
                                prob_map = {cls: float(p) for cls, p in zip(bundle["model"].classes_, proba[0])}
                            client.table("predictions").insert(
                                {
                                    "latitude": float(lat),
                                    "longitude": float(lon),
                                    "radius_deg": float(radius),
                                    "predicted_risk": str(pred),
                                    "probabilities": prob_map,
                                    "features": X.iloc[0].to_dict(),
                                }
                            ).execute()
                            st.success("Predicción guardada en Supabase.")
                        except Exception as exc:  # noqa: BLE001
                            st.warning(f"No se pudo guardar la predicción: {exc}")

    # --- Tab 5: Supabase ---
    with tabs[4]:
        st.subheader("Conexión con Supabase")
        st.code("SUPABASE_URL / SUPABASE_KEY en archivo .env (ver .env.example)")
        if connected:
            st.success(status_msg)
            if st.button("Probar consulta"):
                try:
                    res = client.table("earthquakes").select("event_id").limit(5).execute()
                    st.write(res.data)
                except Exception as exc:
                    st.error(str(exc))
            if st.button("Sincronizar datos y zonas de riesgo"):
                try:
                    from src.train import main as train_main

                    train_main()
                    st.success("Sincronización ejecutada (ver consola).")
                except Exception as exc:
                    st.error(str(exc))
        else:
            st.warning(status_msg)
            st.markdown("Configure `.env` con credenciales y reinicie la app.")


if __name__ == "__main__":
    main()
