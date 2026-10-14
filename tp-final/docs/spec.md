# QUANTLAB — Especificación del MVP

## 1. Objetivo

QUANTLAB es una aplicación web académica para explorar datos de ETF y comparar
dos estrategias de inversión bajo parámetros comunes. El MVP ofrece análisis
descriptivo de precios históricos locales y un modo experimental separado que
usa series OHLC sintéticas deterministas.

No ejecuta operaciones financieras reales ni ofrece recomendaciones de
inversión.

## 2. Alcance implementado

- Catálogo backend de SPY, QQQ, IWM, TLT y GLD con estados y capacidades.
- Análisis descriptivo histórico local de SPY y QQQ: resumen de `Close`,
  estadísticas descriptivas y gráfico del precio de cierre por período.
- Interfaz para elegir modo, ETF de referencia, escenario y parámetros.
- Comparación experimental de Buy & Hold y SMA con escenarios sintéticos de
  tendencia alcista, mercado lateral y alta volatilidad.
- Curvas de patrimonio, métricas financieras y tabla de operaciones para la
  comparación experimental.
- API FastAPI para catálogo, series y resumen descriptivo, comparación
  histórica bloqueada cuando los activos/eventos no son aptos, y comparación
  experimental.
- Validaciones de parámetros, OHLC, acciones corporativas y serialización JSON.
- Pruebas automatizadas de backend y una prueba frontend con Node.js.

El ETF seleccionado en modo experimental es solo una referencia visual. No
cambia el escenario ni los datos sintéticos usados por el motor.

## 3. Fuera del alcance implementado

- Persistencia SQLite.
- Historial persistente de experimentos.
- Aprendizaje por refuerzo.
- Simulación histórica habilitada para SPY o QQQ.
- Análisis descriptivo de IWM, TLT o GLD mientras no haya datos locales
  validados registrados.
- Procesamiento y conciliación completa de dividendos y splits reales para
  habilitar backtesting histórico.

## 4. Arquitectura y tecnologías

- **Frontend:** HTML, CSS, JavaScript nativo y Canvas; consume la API mediante
  `fetch`.
- **Backend:** Python 3.12 y FastAPI; Pydantic define los esquemas HTTP.
- **Datos y cálculos:** pandas y NumPy; yfinance se declara para adquisición
  controlada, no para descargar datos durante peticiones HTTP.
- **Servidor local:** Uvicorn para la API y el servidor HTTP estándar de
  Python para los archivos estáticos.
- **Pruebas:** pytest para backend y Node.js `node:test` para el test de
  frontend, sin framework de interfaz.
- **Entorno:** uv y `uv.lock` para dependencias.

## 5. Reglas de simulación experimental

- Buy & Hold compra en la primera apertura evaluada y mantiene la posición.
- SMA20/SMA50 calcula señales con cierres disponibles hasta la sesión actual;
  una señal al cierre se ejecuta en la apertura de la sesión siguiente.
- Las sesiones de calentamiento quedan fuera del período evaluado.
- Ambas estrategias comparten capital, comisión, período y fechas de valoración.
- El costo configurado se aplica sobre el nocional de cada operación. La
  configuración predeterminada es 0,1 %.
- Las posiciones abiertas se valoran al último `Close`; no se liquida
  artificialmente la cartera.
- El modo experimental marca explícitamente el origen sintético.

Las convenciones contables y métricas se detallan en
[`data_contract.md`](data_contract.md). Estas simulaciones demuestran el flujo
de la aplicación; no son evidencia de rendimiento histórico real.

## 6. Datos históricos y limitaciones

- SPY y QQQ están habilitados solo para análisis descriptivo local.
- Las comparaciones históricas para SPY y QQQ permanecen bloqueadas porque los
  eventos corporativos no están completamente procesados y reconciliados.
- La conciliación documentada de dividendos SPY conserva una discrepancia y
  distingue resultados comunicados de verificaciones independientes.
- Los datos de QQQ contienen eventos corporativos cuya conciliación sigue
  pendiente.
- IWM, TLT y GLD están pendientes de validación; no se declaran períodos ni
  datos disponibles.
- La variación descriptiva de `Close` no es rentabilidad total: no incluye las
  distribuciones.
- Los escenarios sintéticos no representan precios ni rentabilidades
  históricas de ningún ETF.
- No se modelan impuestos, retenciones, deslizamiento, spread, liquidez,
  custodia ni restricciones de intermediarios.

## 7. Estructura principal

```text
backend/       API, catálogo, adquisición, motor, métricas y datos sintéticos
data/raw/      instantáneas históricas locales (excluidas de Git)
docs/          especificación, plan, contrato de datos y guía de API
frontend/      interfaz web estática
tests/         pruebas backend y frontend
pyproject.toml configuración de Python y pytest
uv.lock        versiones resueltas por uv
```

## 8. Ejecución y pruebas

Requisitos: Python 3.12, uv y Node.js (para la prueba frontend). Desde la raíz
de QUANTLAB, sincroniza las dependencias fijadas:

```powershell
uv sync
```

Inicia el backend y el frontend en terminales separadas:

```powershell
uv run uvicorn backend.api:app --reload --host 127.0.0.1 --port 8000
```

```powershell
uv run python -m http.server 5500 --bind localhost --directory frontend
```

Abre `http://localhost:5500`. La configuración CORS de la API permite el
origen local documentado `http://localhost:5500`.

Comandos de pruebas:

```powershell
uv run pytest -v
node --test tests/frontend_409.test.cjs
node --check frontend/app.js
```

La guía de rutas y respuestas está en [`api.md`](api.md).

## 9. Criterios de aceptación del MVP

- El catálogo distingue estados y capacidades sin aceptar rutas locales del
  cliente.
- El análisis descriptivo presenta datos locales reales como descripción de
  `Close`, sin llamarlos rentabilidad total.
- El modo experimental identifica el origen sintético y compara ambas
  estrategias con parámetros comunes.
- La API conserva las validaciones y bloquea los activos/eventos no habilitados
  para simulación histórica.
- Las pruebas automatizadas pueden ejecutarse sin depender de descargas vivas.
