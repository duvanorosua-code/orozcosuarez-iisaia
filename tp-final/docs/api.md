# API de QUANTLAB

La API FastAPI usa rutas bajo `/api/v1`. Los datos históricos son locales y
administrados por el servidor: el cliente usa `dataset_id` del catálogo y no
puede enviar rutas de archivos. Las peticiones HTTP no descargan datos.

## Ejecución local

Desde la raíz del proyecto, sincroniza las dependencias declaradas en
`pyproject.toml` y `uv.lock`:

```powershell
uv sync
```

Terminal 1 — backend:

```powershell
uv run uvicorn backend.api:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2 — frontend estático:

```powershell
uv run python -m http.server 5500 --bind localhost --directory frontend
```

Abre `http://localhost:5500`. CORS se limita a ese origen local, con los
métodos y cabeceras necesarios y sin credenciales.

## Rutas

| Método y ruta | Uso | Respuestas relevantes |
|---|---|---|
| `GET /api/v1/datasets` | Lista los cinco registros del catálogo, sus estados, capacidades y metadatos disponibles. | `200` |
| `GET /api/v1/datasets/{dataset_id}` | Consulta metadatos de un activo registrado. | `200`, `404` si el identificador no existe. |
| `GET /api/v1/datasets/{dataset_id}/summary` | Estadísticas descriptivas del precio `Close`; admite `start_date` y `end_date` opcionales e inclusivas. | `200`, `404` inexistente/no disponible, `409` si el análisis descriptivo no está habilitado, `422` rango inválido, rango sin sesiones o datos no válidos. |
| `GET /api/v1/datasets/{dataset_id}/series` | Puntos `{date, close}` para el gráfico descriptivo; admite `start_date` y `end_date` opcionales e inclusivas. | `200`, `404` inexistente, `409` sin capacidad descriptiva, `422` intervalo inválido o sin observaciones, `503` si el archivo local registrado falta o no pasa validación. |
| `POST /api/v1/comparisons` | Solicita comparación histórica de Buy & Hold y SMA sobre un dataset. | `200` si el dataset está habilitado y pasa validación; `404` dataset inexistente/no disponible; `409` activo bloqueado por estado o acciones corporativas pendientes; `422` parámetros o datos inválidos; `500` si no puede serializarse una respuesta JSON finita. |
| `POST /api/v1/experimental/comparisons` | Compara Buy & Hold y SMA con una serie sintética determinista. | `200`; `422` parámetros inválidos; `500` si la respuesta no puede serializarse como JSON finito. |

Los errores siguen el formato de FastAPI, con un campo `detail`. Los errores
de validación de parámetros devueltos por Pydantic usan HTTP `422`.

## Catálogo y estados

El catálogo registra SPY, QQQ, IWM, TLT y GLD. SPY y QQQ están habilitados
para análisis descriptivo local, no para simulación histórica. La simulación
permanece bloqueada por eventos corporativos sin procesar y reconciliar. IWM,
TLT y GLD están pendientes de datos locales validados; no se les atribuyen
períodos ni hashes inexistentes.

Los estados son `pending_validation`, `descriptive_only` y
`historical_simulation`. Las capacidades se devuelven explícitamente. Las
rutas descriptivas rechazan activos que no tengan esa capacidad. El listado y
los metadatos no exponen rutas locales.

El resumen calcula estadísticas de `Close`, no de `Adj Close`. El cambio de
precio no incluye distribuciones y no es rentabilidad total. Si faltan
observaciones para una métrica, el valor se devuelve como `null` con un motivo
en `unavailable_reasons`. Los rangos de resumen/serie se ajustan a sesiones
observadas dentro de las fechas inclusivas solicitadas; no se rellenan
sesiones.

## Comparación histórica

La petición de `POST /api/v1/comparisons` admite:

```json
{
  "dataset_id": "spy-2020-2025",
  "initial_capital": 1000000,
  "evaluation_start": "2022-01-03",
  "evaluation_end": "2024-12-31",
  "transaction_cost_rate": 0.001,
  "short_window": 20,
  "long_window": 50
}
```

La fecha final es inclusiva. Los valores predeterminados para comisión y
ventanas son `0.001`, `20` y `50`. El inicio requiere suficientes cierres
previos para el calentamiento SMA; esas sesiones no se incluyen en las curvas
ni en las métricas. La respuesta incluye configuración efectiva, dataset y
SHA-256, fechas, curvas, ejecuciones, métricas y advertencias. Fechas se
serializan como `YYYY-MM-DD`; no se devuelven NaN ni infinitos. En el estado
actual SPY y QQQ reciben `409` para esta ruta.

## Comparación experimental

`POST /api/v1/experimental/comparisons` acepta el escenario `uptrend`,
`sideways` o `high_volatility`, capital, cantidad de sesiones, comisión y
ventanas SMA. Los valores predeterminados son capital `1,000,000`, 252
sesiones, comisión `0.001` y ventanas `20/50`. El servicio ejecuta ambas
estrategias bajo la misma configuración. La respuesta identifica
`mode: experimental`, `data_origin: synthetic`, `ticker: SYNTHETIC`, el
escenario, curvas, operaciones, métricas y configuración efectiva. El ETF que
la interfaz muestra como referencia no forma parte de la solicitud
experimental.

Los valores son generados por QUANTLAB y no son precios o rendimientos
históricos reales de SPY, QQQ u otro ETF. No se deben comparar como evidencia
de desempeño histórico.

## Pruebas

Backend completo:

```powershell
uv run pytest -v
```

Pruebas de frontend disponibles (Node.js, sin dependencias de UI):

```powershell
node --test tests/frontend_409.test.cjs
node --check frontend/app.js
```

Las pruebas backend usan fixtures y proveedores sintéticos; no requieren
Internet ni ejecutan las estrategias con el CSV real.
