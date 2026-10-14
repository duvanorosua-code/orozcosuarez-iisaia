# QUANTLAB

QUANTLAB es un MVP académico para explorar precios históricos de ETF y comparar
dos estrategias de inversión bajo parámetros comunes. La aplicación separa el
análisis descriptivo de datos locales de la comparación experimental con datos
sintéticos.

## Objetivo y alcance

El MVP permite consultar el catálogo, analizar descriptivamente SPY y QQQ,
visualizar sus precios de cierre y ejecutar comparaciones experimentales entre
Buy & Hold y SMA20/SMA50. Las simulaciones experimentales usan escenarios
sintéticos deterministas. No se ejecutan operaciones financieras reales ni se
emiten recomendaciones de inversión.

## Funcionalidades

- Catálogo de SPY, QQQ, IWM, TLT y GLD con estado y capacidades.
- Resumen de precios `Close` y gráfico histórico descriptivo para SPY y QQQ.
- Configuración de capital, comisión, sesiones, escenario y ventanas SMA en
  modo experimental.
- Curvas de patrimonio, métricas financieras y tabla de operaciones para las
  dos estrategias.
- API HTTP con validación de parámetros y datos.

En el modo experimental, el ETF seleccionado solo es una referencia visual:
la fuente utilizada para comparar es sintética y depende del escenario
seleccionado.

## Arquitectura y tecnologías

- **Frontend:** HTML, CSS y JavaScript nativo; Canvas para gráficos y `fetch`
  para consumir la API.
- **Backend:** Python 3.12, FastAPI y esquemas Pydantic.
- **Cálculos y datos:** pandas y NumPy; yfinance para adquisición controlada.
- **Ejecución local:** uv/Uvicorn para backend y el servidor HTTP estándar de
  Python para el frontend.
- **Pruebas:** pytest para backend; Node.js `node:test` y `node --check` para
  frontend.

El frontend consume el backend FastAPI. El backend administra las ubicaciones
locales de los datasets, valida los datos y delega los cálculos al motor
financiero existente. El navegador no proporciona rutas de archivo.

## Estructura

```text
backend/       API, catálogo, adquisición, motor financiero y generador sintético
data/raw/      CSV y metadatos históricos locales (ignorados por Git)
docs/          especificación, plan, contrato de datos y guía de API
frontend/      interfaz estática
tests/         pruebas backend y frontend
pyproject.toml dependencias y configuración pytest
uv.lock        resolución fijada de dependencias
```

## Requisitos y ejecución local

Requiere Python 3.12, uv y Node.js para ejecutar la prueba de frontend. Desde
esta carpeta, sincroniza el entorno con el archivo de bloqueo:

```powershell
uv sync
```

Abre dos terminales en la raíz de QUANTLAB.

Terminal 1 — API:

```powershell
uv run uvicorn backend.api:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2 — interfaz:

```powershell
uv run python -m http.server 5500 --bind localhost --directory frontend
```

Abre `http://localhost:5500`. CORS está restringido a ese origen. Para las
rutas y formatos de respuesta, consulta [`docs/api.md`](docs/api.md).

## Pruebas

Suite backend:

```powershell
uv run pytest -v
```

Prueba de frontend y comprobación sintáctica:

```powershell
node --test tests/frontend_409.test.cjs
node --check frontend/app.js
```

Las pruebas backend utilizan datos sintéticos controlados y no necesitan
descargar datos de mercado.

## Limitaciones del MVP

- Los escenarios experimentales usan datos sintéticos y no representan
  rentabilidades históricas reales.
- SPY y QQQ están habilitados para análisis descriptivo, pero su simulación
  histórica continúa bloqueada mientras no se procesen y reconcilien sus
  eventos corporativos.
- La conciliación de dividendos reales permanece pendiente, incluida una
  discrepancia comunicada para SPY; véase [`docs/data_contract.md`](docs/data_contract.md).
- IWM, TLT y GLD no tienen datos locales validados para las funcionalidades
  que requieren esos datos.
- No hay persistencia SQLite ni historial persistente de experimentos.
- El MVP no modela impuestos, retenciones, spread, deslizamiento, liquidez ni
  costos de custodia.

La variación descriptiva de `Close` no incluye distribuciones y no debe
interpretarse como rentabilidad total. Los resultados pasados tampoco
garantizan resultados futuros.


## Qué decidí yo

Separar el análisis histórico de la comparación experimental. Quería que QUANTLAB permitiera explorar el comportamiento de activos financieros y, por otro lado, probar estrategias de inversión. Al principio podía parecer que ambas cosas eran similares, pero tienen objetivos diferentes. El análisis histórico utiliza datos de mercado, mientras que la comparación experimental utiliza escenarios sintéticos generados por la aplicación. Por eso decidí mantenerlos separados y mostrar claramente qué tipo de datos se está utilizando en cada caso.

Usar Python para la lógica y JavaScript para la interfaz. Elegí FastAPI para el backend porque me permite construir una API con una estructura clara y aprovechar Python para trabajar con los datos, implementar las estrategias y calcular las métricas. Para el frontend utilicé HTML, CSS y JavaScript, sin incorporar un framework adicional. De esta manera pude concentrarme en la funcionalidad de la aplicación sin añadir complejidad innecesaria.

Mantener una API entre el frontend y el backend. La interfaz no accede directamente a los archivos históricos ni calcula por su cuenta qué activos están habilitados. Consulta los endpoints del backend, que se encargan de validar las solicitudes y devolver la información correspondiente. Esto también permite mantener las reglas de disponibilidad en un solo lugar.

Empezar con dos estrategias conocidas. Para la comparación experimental elegí Buy & Hold y el cruce de medias móviles simples (SMA). Mi objetivo inicial no era construir un sistema que encontrara automáticamente la mejor estrategia, sino una aplicación que permitiera configurar parámetros, ejecutar ambas alternativas y comparar sus resultados. Por eso dejé el aprendizaje por refuerzo y otras estrategias para una etapa posterior.

Separar los datos históricos de los sintéticos. Para experimentar con diferentes comportamientos del mercado implementé tres escenarios: tendencia alcista, mercado lateral y alta volatilidad. Estos escenarios permiten probar la aplicación sin depender de que todos los activos tengan datos históricos habilitados. También evitan presentar los resultados experimentales como si fueran rentabilidades reales del mercado.

No habilitar el backtesting histórico mientras haya problemas pendientes con los datos. Aunque tengo archivos históricos de SPY y QQQ, decidí mantener bloqueadas las simulaciones hasta resolver la conciliación de sus eventos corporativos. Por ahora puedo consultar estadísticas descriptivas y visualizar los precios de cierre, pero no presentar los resultados de una estrategia como si estuvieran completamente validados.

## Cómo organicé el proyecto

Separé el código por responsabilidades para que cada parte tuviera una función concreta.

backend/: contiene la API, la carga de datos, las estrategias, las métricas y la lógica de las operaciones.
frontend/: contiene la interfaz, los formularios, los gráficos y la interacción con la API.
tests/: reúne las pruebas automatizadas del backend y del frontend.
docs/: contiene la especificación, el plan de trabajo, el contrato de datos y la documentación de la API.
data/: almacena los datos históricos locales y sus metadatos.

Esta organización me permite trabajar en una parte sin tener que modificar toda la aplicación. Por ejemplo, puedo cambiar la presentación de un gráfico sin alterar las reglas con las que se ejecutan las estrategias.

También separé el análisis descriptivo de la comparación de estrategias. Las estadísticas de precios no deben confundirse con las métricas obtenidas al simular una inversión, así que cada funcionalidad tiene su propio flujo de consulta y presentación.

## Cómo trabajé con la IA

Antes de implementar cada funcionalidad, intenté definir qué debía hacer, qué archivos podían intervenir y qué condiciones tenía que respetar. Utilicé ChatGPT para discutir decisiones de arquitectura, entender conceptos y preparar instrucciones para Codex. Después utilicé Codex para inspeccionar el código, implementar los cambios y ejecutar las pruebas correspondientes.

No trabajé con un único prompt para construir toda la aplicación. Fui avanzando por partes: primero la lógica de las estrategias y el manejo del portafolio, después la API, el catálogo de activos, las comparaciones experimentales y finalmente las visualizaciones del frontend.

Cuando aparecía un problema, procuraba identificar su causa antes de pedir otro cambio. Por ejemplo, cuando una compra fallaba por una diferencia muy pequeña entre el efectivo disponible y el costo calculado, revisamos las operaciones involucradas y ajustamos el cálculo de las unidades sin eliminar la validación del ledger.

También fui limitando el alcance de cada iteración. Cuando decidí añadir el gráfico histórico, pedí que se implementara sin modificar los archivos de datos, las estrategias ni el bloqueo del backtesting. Así pude incorporar una funcionalidad nueva sin tener que reconstruir lo que ya funcionaba.

Las pruebas automatizadas fueron importantes durante este proceso. En lugar de depender exclusivamente de abrir la aplicación y probarla manualmente, incorporé pruebas para la API, las estrategias, las métricas, el manejo de operaciones y las respuestas del frontend. Las pruebas no sustituyen todas las comprobaciones manuales, pero permiten detectar regresiones cuando se modifica el código.

## Qué problemas y decisiones fueron apareciendo

Las estrategias podían producir resultados idénticos. Al comparar Buy & Hold y SMA en el escenario alcista, ambas mostraban las mismas curvas y rentabilidades. Investigamos el comportamiento y encontramos que compraban en la misma apertura y mantenían la posición hasta el final. En ese escenario, los resultados idénticos tenían una explicación en las decisiones de las estrategias, por lo que no era necesario modificar las métricas para forzar diferencias.

La comparación experimental necesitaba una identificación más clara. Inicialmente, el ETF seleccionado podía generar confusión al cambiar de modo. Ajusté la interfaz para mantener visible el activo de referencia y distinguirlo de la fuente de datos sintéticos. Así, seleccionar QQQ en el modo experimental no significa que la simulación utilice sus precios históricos.

El análisis histórico necesitaba una visualización propia. Las estadísticas descriptivas permitían consultar los precios iniciales y finales, la variación, la volatilidad y el drawdown, pero faltaba una forma directa de observar la evolución temporal. Por eso añadí un endpoint para consultar las series de precios y un gráfico independiente del gráfico de patrimonio de las estrategias.

Los datos históricos no estaban listos para simular inversiones. Durante la revisión de SPY y QQQ aparecieron eventos corporativos que todavía necesitaban conciliación. En vez de habilitar el backtesting solo porque los archivos estuvieran disponibles, mantuve la restricción y limité su uso al análisis descriptivo. Esta decisión también quedó documentada para evitar confundir las capacidades actuales con las que podrían incorporarse en el futuro.

La interfaz necesitaba diferenciar mejor sus dos modos. Fui ajustando los indicadores, los selectores y los mensajes para que el usuario pudiera identificar el activo, el escenario y la fuente de datos sin tener que conocer la implementación interna. También añadí estados para solicitudes rechazadas y errores de conexión.

## Qué quedó implementado y qué falta

El MVP permite consultar el catálogo de activos, analizar descriptivamente SPY y QQQ, visualizar sus precios de cierre y ejecutar comparaciones experimentales entre Buy & Hold y SMA en tres escenarios sintéticos. La interfaz presenta métricas, curvas de patrimonio y operaciones, y el backend ofrece endpoints para las funcionalidades disponibles.

No implementé todavía el historial persistente de experimentos ni la integración de aprendizaje por refuerzo. Tampoco habilité el backtesting histórico de SPY y QQQ, porque sigue pendiente la conciliación de eventos corporativos. IWM, TLT y GLD permanecen en el catálogo, pero no cuentan con datos locales validados para las funcionalidades que los requieren.

Considero que estas limitaciones forman parte del alcance actual y deben quedar explícitas. El objetivo de esta versión fue construir una aplicación funcional, con una separación clara entre componentes, una interfaz que permita explorar los resultados y pruebas que ayuden a mantener el comportamiento esperado.