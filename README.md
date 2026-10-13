# Explorador de sismos de Santander

Aplicación web en Streamlit para consultar y explorar los registros sísmicos existentes en el proyecto Supabase configurado. La aplicación lee las tablas `sismo`, `region` y `tipo_magnitud`; no crea tablas ni agrega, modifica o elimina registros.

## Contexto del reto

El reto propone una jornada presencial en la que equipos de distintas universidades construyen, usando datos sísmicos reales del Servicio Geológico Colombiano (SGC), un sistema de Machine Learning que analiza y clasifica el riesgo sísmico de una zona de Santander en tres categorías: **Básico, Medio y Avanzado**.

Santander presenta alta actividad sísmica. Bajo la Mesa de Los Santos se encuentra el Nido Sísmico de Bucaramanga, una de las zonas de sismicidad intermedia más activas del mundo. El SGC registra y publica estos eventos. El propósito del reto es transformar esos registros en modelos que permitan analizar y clasificar el riesgo de una zona y, si el equipo lo decide, explorar su anticipación.

Cada equipo elige primero su zona de estudio y luego filtra los datos correspondientes. Como referencia para quienes participan por primera vez, se propone estudiar el comportamiento sísmico de Santander durante los últimos 20 años.

### Requisito central

En cualquiera de los niveles, la entrega debe implementar y demostrar un sistema de Machine Learning funcional entrenado con datos reales de una fuente oficial. No basta con una presentación conceptual, una interfaz visual sin modelo o un sistema basado únicamente en reglas fijas.

### Alcance actual de esta aplicación

La aplicación actual permite inspeccionar los datos que ya existen en Supabase: presenta indicadores, registros por año, distribución por tipo de magnitud y tablas consultables con paginación y filtros. **Esta interfaz de consulta no entrena ni ejecuta todavía un modelo de Machine Learning, y por sí sola no satisface el requisito central del reto.** El modelo deberá incorporarse como una etapa de trabajo posterior usando datos oficiales verificados y una metodología documentada. No se deben presentar las categorías del reto como predicciones hasta que exista un modelo funcional que las produzca.

## Objetivo de la aplicación

Facilitar la exploración de los registros sísmicos disponibles para entender su periodo, magnitudes, profundidades, distribución temporal y catálogos relacionados, como base para seleccionar una zona de estudio y preparar el trabajo posterior de Machine Learning.

## Qué muestra

- **Resumen:** cantidad de sismos, magnitud media y máxima, profundidad media, periodo disponible, eventos por año y registros agrupados por tipo de magnitud.
- **Sismos:** registros de la tabla `sismo`, ordenados por fecha, con filtros de región y rango de magnitud, y paginación de 100 filas.
- **Regiones:** contenido existente de la tabla `region`.
- **Tipos de magnitud:** contenido existente de la tabla `tipo_magnitud`.

Los datos se consultan directamente en Supabase mediante su API REST. Las consultas son de solo lectura y los resultados se almacenan temporalmente en caché durante un máximo de 10 minutos para el resumen y los catálogos, y 1 minuto para consultas de la tabla de sismos.

## Requisitos

- Windows PowerShell, macOS o Linux.
- Python 3.11 o la versión indicada en `runtime.txt`.
- Acceso de red al proyecto Supabase.
- Credenciales de Supabase con permiso para leer las tablas utilizadas.

## Instalación y ejecución en Windows PowerShell

1. Abre PowerShell en la carpeta del proyecto (`Proyecto-Hackaton`). Por ejemplo:

   ```powershell
   cd "D:\OneDrive - Unidades Tecnológicas de Santander\Escritorio\Proyecto-Hackaton"
   ```

2. Comprueba que Python esté instalado:

   ```powershell
   py --version
   ```

   Si el comando `py` no está disponible, instala Python y habilita la opción para agregarlo al `PATH`; también puedes probar `python --version`.

3. (Recomendado) Crea y activa un entorno virtual:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   Si PowerShell bloquea la activación, puedes continuar sin activar el entorno usando `\.venv\Scripts\python.exe` en los siguientes comandos.

4. Instala las dependencias:

   ```powershell
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

   Si no activaste el entorno virtual, reemplaza `python` por `\.venv\Scripts\python.exe`. Si `python` no está en el `PATH`, prueba `py`.

5. Configura las variables de entorno en un archivo `.env` en la raíz del proyecto. Si todavía no existe, puedes partir de la plantilla:

   ```powershell
   Copy-Item .env.example .env
   ```

   Configura como mínimo:

   ```dotenv
   SUPABASE_URL=https://<project-ref>.supabase.co
   SUPABASE_SERVICE_ROLE_KEY=<clave-secreta-del-servidor>
   ```

   La aplicación Streamlit consulta Supabase desde el servidor usando `SUPABASE_SERVICE_ROLE_KEY`. Esa clave tiene privilegios elevados: mantenla solo en `.env` local o en el gestor de secretos del servicio de despliegue. **Nunca la incluyas en `app.py`, en el navegador, en Git ni en capturas públicas.** El `.gitignore` ya excluye `.env`.

   `SUPABASE_ANON_KEY` o `SUPABASE_PUBLISHABLE_KEY` se reservan para clientes públicos y no sustituyen la clave requerida por el servidor de esta aplicación cuando las políticas RLS impiden la lectura pública. No es necesario configurar `DATABASE_URL` ni `DIRECT_DATABASE_URL` para ejecutar la app: se consulta la API REST de Supabase.

6. Inicia la aplicación:

   ```powershell
   python -m streamlit run app.py
   ```

   También puedes usar `py -m streamlit run app.py`. El navegador se abrirá automáticamente; si no ocurre, copia en el navegador la dirección local que muestra Streamlit (normalmente `http://localhost:8501`). Para detenerla, vuelve a PowerShell y pulsa `Ctrl+C`.

### Si aparece “No module named streamlit”

Asegúrate de haber instalado los requisitos con el mismo Python con que ejecutas la aplicación:

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Con entorno virtual, comprueba que `(.venv)` aparezca al inicio de la línea de PowerShell. Si no, reactívalo con `\.venv\Scripts\Activate.ps1`.

## Configuración de Supabase y datos

La aplicación espera que ya existan estas tablas en el esquema `public`:

- `sismo`: eventos y sus campos de fecha, coordenadas, magnitud, profundidad y mediciones asociadas.
- `region`: catálogo de regiones.
- `tipo_magnitud`: catálogo de tipos de magnitud.

La aplicación no necesita ni ejecuta `supabase/schema.sql`, no sincroniza datos externos y no requiere crear tablas. Los nombres y columnas consultados están definidos en `app.py`. Si la estructura de la base de datos no coincide o faltan permisos de lectura, la página mostrará un error de conexión o de consulta.

La conexión del proyecto se configura mediante `SUPABASE_URL` y la clave de servidor en `.env`. No publiques credenciales ni las incluyas en este README. Si una clave privilegiada se expuso fuera de un canal seguro, rótala desde el panel de Supabase.

## Verificaciones

Para comprobar la sintaxis de Python sin iniciar el servidor:

```powershell
python -m compileall app.py src
```

Para iniciar la verificación de conexión y la interfaz, ejecuta `python -m streamlit run app.py` y confirma que aparecen el estado de conexión, los indicadores y las cuatro secciones. La primera carga del resumen puede tardar porque consulta y procesa los registros existentes.

## Estructura relevante

```text
Proyecto-Hackaton/
├── app.py                  # Interfaz Streamlit de consulta de datos
├── requirements.txt        # Dependencias Python
├── .env.example            # Plantilla de configuración sin secretos
├── .gitignore              # Excluye .env y archivos locales
├── src/
│   ├── config.py           # Variables de entorno
│   └── supabase_client.py  # Clientes públicos y de servidor
└── supabase/
    └── schema.sql          # Archivo histórico; no se ejecuta al iniciar la app
```

## Despliegue

El repositorio incluye `render.yaml` y `Procfile` como configuración de referencia para Render. Configura en el servicio las variables `SUPABASE_URL` y `SUPABASE_SERVICE_ROLE_KEY` en el apartado seguro de variables de entorno. No las guardes en el repositorio. El comando de inicio previsto es:

```bash
streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true
```

Verifica en el proveedor de despliegue que las versiones de Python y dependencias sean compatibles con `runtime.txt` y `requirements.txt`.
