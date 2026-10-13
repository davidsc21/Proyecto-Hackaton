# Riesgo sísmico en Santander (Mesa de los Santos)

Aplicación en Python que analiza el comportamiento sísmico de Santander en los últimos 20 años,
construye variables geoespaciales y clasifica el riesgo sísmico (Bajo / Medio / Alto) con
Machine Learning, y se conecta con Supabase para almacenar eventos, zonas de riesgo y predicciones.

## Estructura

```
Proyecto-Hackaton/
├── app.py                     # App Streamlit
├── requirements.txt
├── .env.example
├── src/
│   ├── config.py
│   ├── data_fetch.py          # Descarga eventos USGS
│   ├── features.py            # Ingeniería de variables por celda
│   ├── model.py               # RandomForest + métricas
│   ├── train.py               # Pipeline de entrenamiento y sync Supabase
│   └── supabase_client.py
├── supabase/schema.sql        # Tablas para Supabase
├── data/raw/earthquakes_santander.csv
├── data/processed/risk_zones.csv
└── models/seismic_risk_model.joblib
```

## Instalación

```bash
python -m pip install -r requirements.txt
copy .env.example .env   # completar credenciales de Supabase (opcional)
```

## Ejecutar

```bash
# 1. Descargar datos + entrenar modelo
python -m src.train            # usa data/raw si existe
python -m src.train --fetch   # vuelve a descargar desde USGS

# 2. Lanzar la app
streamlit run app.py
```

## Deploy en Render

La app ya incluye `Procfile`, `runtime.txt` y `render.yaml`.

1. Sube este proyecto a GitHub.
2. En Render crea un **Web Service** desde el repositorio.
3. Configura las variables de entorno:
   - `DATABASE_URL` = pooler de Supabase (recomendado para Render/IPv4)
   - `DIRECT_DATABASE_URL` opcional
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY` o `SUPABASE_PUBLISHABLE_KEY` para el cliente; reserva `SUPABASE_SERVICE_ROLE_KEY` para tareas privadas del servidor
4. Render ejecutará `pip install -r requirements.txt` y luego:

   ```bash
   streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true
   ```

## Supabase

1. Crear un proyecto en Supabase.
2. Ejecutar `supabase/schema.sql` en el SQL Editor.
3. Copiar `SUPABASE_URL` y la llave `anon` o `publishable` en `.env`. Mantener `SUPABASE_SERVICE_ROLE_KEY` solo en el servidor y nunca en el frontend.
4. `python -m src.train` sincroniza eventos y zonas de riesgo; la app guarda predicciones.

La app funciona en modo offline si no hay credenciales.

## Notas de los datos

- Fuente: USGS FDSN (`earthquake.usgs.gov`) para el bounding box de Santander, 2005-2025, M >= 2.0.
- Las variables por celda incluyen conteo de eventos, magnitud máxima/media, profundidad media,
  energía sísmica logarítmica, eventos/año, distancia a Mesa de los Santos y al nido sísmico.
- Etiquetado de riesgo por umbrales de sismicidad histórica; clasificador `RandomForest` balanceado.
```