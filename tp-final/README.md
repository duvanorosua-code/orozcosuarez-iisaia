# QUANTLAB

QUANTLAB es un laboratorio web para explorar estrategias de inversión y comparar su comportamiento. La idea surgió de querer construir una aplicación en la que se pudieran visualizar datos de mercado, configurar estrategias y entender cómo cambian los resultados al modificar algunos parámetros.

Para el MVP me concentré en dos funcionalidades: el análisis descriptivo de precios históricos de ETF y la comparación experimental entre las estrategias Buy & Hold y cruce de medias móviles (SMA).

No intenté construir una plataforma de inversión completa. Quería tener una aplicación funcional, con una interfaz que permitiera interactuar con los datos y un backend que se encargara de procesarlos y ejecutar las estrategias.

## Qué decidí

**Separar el análisis histórico de la comparación experimental.** Esta fue una de las decisiones más importantes del proyecto. Para el análisis histórico utilizo datos de SPY y QQQ descargados de Yahoo Finance y almacenados localmente. En cambio, para experimentar con las estrategias genero datos sintéticos desde Python. Así puedo probar diferentes escenarios sin presentar los resultados artificiales como si fueran rendimientos históricos reales.

**Empezar con HTML, CSS y JavaScript.** Para el frontend preferí trabajar con las tecnologías web directamente, sin incorporar un framework adicional. Esto me permitió concentrarme en la interfaz, los formularios, los gráficos y la comunicación con el backend, sin añadir un proceso de compilación.

**Usar FastAPI para el backend.** Elegí Python porque es el lenguaje que utilizo para trabajar con datos y desarrollar modelos. FastAPI me permite exponer las funcionalidades mediante una API y mantener separada la lógica de procesamiento de la interfaz.

**Conservar los datos históricos en archivos CSV.** No incorporé una base de datos en esta primera versión. Los archivos CSV son suficientes para conservar los precios que utilizo en el análisis descriptivo, mientras que los metadatos en JSON permiten registrar información de las descargas y comprobar la integridad de los archivos.

**No habilitar todavía el backtesting histórico.** Aunque ya tengo datos históricos disponibles, decidí mantener bloqueada la ejecución de estrategias sobre esos datos mientras haya eventos corporativos pendientes de conciliación. Para demostrar el funcionamiento de las estrategias utilizo el modo experimental.

**Mantener el alcance del MVP controlado.** Preferí completar el flujo principal de la aplicación antes de incorporar funcionalidades como el historial persistente de experimentos o una base de datos SQLite.

## Cómo está construido

El proyecto está dividido en dos partes principales.

El frontend contiene los formularios, las tarjetas de resultados, los gráficos y las tablas de operaciones. Desde allí se selecciona el modo de análisis, se consultan los activos disponibles y se ejecutan las comparaciones experimentales.

El backend está desarrollado con FastAPI. Recibe las solicitudes del frontend, consulta el catálogo de activos, carga los datos históricos cuando corresponde y ejecuta las funciones de análisis y comparación.

Dentro del backend separé las responsabilidades para no concentrar toda la lógica en un único archivo:

- `data_loader.py` se encarga de descargar, guardar y validar los datos históricos.
- `dataset_catalog.py` define los activos disponibles y las capacidades habilitadas para cada uno.
- `metrics.py` calcula las métricas de desempeño.
- `portfolio.py` administra el efectivo, las posiciones y las operaciones.
- `strategies.py` implementa Buy & Hold y el cruce de medias móviles.
- `comparison.py` coordina la ejecución de ambas estrategias bajo los mismos parámetros.
- `synthetic_data.py` genera los escenarios experimentales.

También separé los esquemas de la API, la interfaz web y las pruebas automatizadas.

La estructura me permitió modificar funcionalidades concretas sin tener que reescribir toda la aplicación cada vez que aparecía un problema.

## Cómo funciona la aplicación

### Análisis histórico

La aplicación permite seleccionar SPY y QQQ, consultar sus estadísticas descriptivas y visualizar la evolución histórica del precio de cierre.

Los datos se obtuvieron de Yahoo Finance y se guardaron localmente para poder trabajar con un conjunto estable durante el desarrollo.

El análisis muestra el número de sesiones, los precios inicial y final, la variación del precio, la volatilidad y el drawdown. También permite seleccionar un período para visualizar la serie histórica.

Estas estadísticas describen el comportamiento del precio de cierre. No deben interpretarse como la rentabilidad total de una inversión, porque no incorporan necesariamente todos los efectos de los dividendos y otros eventos corporativos.

Los activos IWM, TLT y GLD aparecen en el catálogo, pero todavía no tienen datos históricos locales validados para habilitar el análisis correspondiente.

### Comparación experimental

En este modo se pueden seleccionar tres escenarios sintéticos:

- Tendencia alcista.
- Mercado lateral.
- Alta volatilidad.

También se puede configurar el capital inicial, la comisión, el número de sesiones y las ventanas de las medias móviles.

La aplicación ejecuta Buy & Hold y SMA sobre el mismo escenario y presenta las métricas, las curvas de patrimonio y las operaciones generadas por cada estrategia.

El selector de ETF permanece visible en la interfaz, pero en este modo sirve como referencia: **la comparación experimental utiliza datos sintéticos y no los precios históricos del ETF seleccionado**.

Esto permite demostrar el funcionamiento del motor de estrategias sin confundir una simulación artificial con un backtest sobre el mercado real.

## Qué tuve que resolver

### El problema del efectivo negativo

Durante las pruebas de la comparación experimental apareció un error que impedía completar algunas ejecuciones.

La causa era una diferencia extremadamente pequeña de precisión numérica. Al calcular cuántas unidades comprar, el resultado parecía caber en el efectivo disponible, pero al calcular nuevamente el costo y la comisión se producía una diferencia mínima que hacía que la compra superara el saldo disponible.

El problema no estaba en la señal de la estrategia, sino en cómo se calculaba la cantidad que se podía comprar.

Ajusté el cálculo de las unidades para comprobar el costo con las mismas operaciones que utiliza el libro de operaciones. El ledger conserva sus validaciones y sigue impidiendo que una compra genere efectivo negativo.

Después añadí pruebas de regresión para verificar que las estrategias pudieran ejecutarse con los parámetros utilizados en los tres escenarios.

### Las dos estrategias daban exactamente el mismo resultado

En el escenario sintético de tendencia alcista, Buy & Hold y SMA mostraban las mismas métricas y las curvas se superponían.

Al revisar las operaciones, encontré que ambas estrategias compraban en la misma apertura y mantenían la misma posición hasta el final. Por eso sus resultados coincidían.

No era un error de visualización. Se debía al comportamiento de la serie sintética y al momento en que se generaba la señal SMA.

Conservé la lógica de las estrategias y utilicé el caso para comprobar que el resultado mostrado por la interfaz coincidiera con las operaciones ejecutadas por el backend.

### El ETF seleccionado no era el que generaba los resultados experimentales

Al cambiar del análisis histórico a la comparación experimental, la interfaz seguía mostrando el ticker del ETF seleccionado. Esto podía hacer pensar que la comparación se estaba realizando con los precios de ese activo.

Para evitar esa confusión, ajusté la interfaz para distinguir la referencia del ETF de la fuente de datos utilizada en el experimento. También añadí una explicación de que los escenarios son sintéticos e independientes de los precios históricos.

Aproveché el cambio para eliminar las alertas amarillas que aparecían en los resultados experimentales y sustituirlas por una nota más discreta.

### La API y el frontend debían manejar los errores

También trabajé en el comportamiento de la aplicación cuando una solicitud no puede completarse.

El frontend debe distinguir entre parámetros inválidos, activos que no están disponibles, comparaciones bloqueadas y problemas de conexión. En esos casos no debe presentar resultados anteriores como si correspondieran a la solicitud actual.

Para comprobar estos comportamientos incorporé pruebas de la API y del frontend.

## Los datos históricos y sus limitaciones

Uno de los aprendizajes del proyecto fue que disponer de datos históricos no significa que estén listos para evaluar una estrategia de inversión.

Los archivos de SPY y QQQ contienen precios y eventos corporativos. Antes de utilizar esos datos para un backtest hay que comprobar que los eventos estén correctamente identificados y que su tratamiento sea coherente con el cálculo del patrimonio.

Durante la revisión encontré aspectos pendientes en la conciliación de dividendos. Por eso mantuve habilitadas las estadísticas descriptivas y los gráficos de precios, pero bloqueé las comparaciones históricas.

Esta separación es intencional. Prefiero mostrar una limitación explícita antes que presentar resultados que puedan interpretarse como una evaluación financiera validada.

La siguiente etapa sería completar la validación de los eventos corporativos y, después, habilitar el backtesting histórico.

## Cómo trabajé con las pruebas

Al principio era importante comprobar que las funcionalidades se vieran bien en el navegador, pero eso no era suficiente para validar la lógica del proyecto.

Por eso fui incorporando pruebas automatizadas para las métricas, el libro de operaciones, las estrategias, la comparación, la carga de datos, el catálogo y los endpoints de la API.

También añadí pruebas para algunos problemas que aparecieron durante el desarrollo, como la precisión de las compras y el manejo de solicitudes experimentales.

La idea fue comprobar tanto los resultados esperados como los casos en los que la aplicación debe rechazar una operación o devolver un error controlado.

## Qué queda pendiente

El MVP permite consultar estadísticas históricas de SPY y QQQ, visualizar sus precios de cierre y comparar las dos estrategias sobre datos sintéticos.

Sin embargo, todavía hay funcionalidades que no forman parte de esta versión:

- Habilitar el backtesting histórico después de completar la conciliación de los eventos corporativos.
- Incorporar y validar datos históricos de IWM, TLT y GLD.
- Guardar los experimentos para que el usuario pueda consultar comparaciones anteriores.
- Evaluar el uso de SQLite para persistir parámetros, métricas y operaciones.
- Incorporar nuevas estrategias y escenarios de experimentación.

No considero que estas limitaciones impidan presentar el MVP. La aplicación ya permite recorrer el flujo principal, ejecutar comparaciones experimentales y visualizar los resultados, dejando explícito qué funcionalidades están disponibles y cuáles requieren trabajo adicional.

## Cómo ejecutar el proyecto

### Requisitos

- Python 3.12.
- `uv` para gestionar el entorno y las dependencias.
- Node.js para ejecutar las pruebas del frontend.
- Conexión a internet para descargar dependencias cuando sea necesario.

Los comandos deben ejecutarse desde la carpeta `tp-final`.

### Iniciar el backend

```powershell
uv sync
uv run uvicorn backend.api:app --reload --host 127.0.0.1 --port 8000
```

### Iniciar el frontend

En otra terminal:

```powershell
uv run python -m http.server 5500 --bind localhost --directory frontend
```

Después, abre en el navegador:

```text
http://localhost:5500
```

### Ejecutar las pruebas

Pruebas del backend:

```powershell
uv run pytest -v
```

Pruebas del frontend:

```powershell
node --test tests/frontend_409.test.cjs
```

Comprobación de sintaxis de JavaScript:

```powershell
node --check frontend/app.js
```

## Tecnologías utilizadas

- **Python:** procesamiento de datos, métricas y estrategias.
- **FastAPI:** API del backend.
- **HTML, CSS y JavaScript:** interfaz web.
- **Canvas:** representación de las series y curvas en los gráficos.
- **Pandas y NumPy:** herramientas para el trabajo con datos.
- **pytest:** pruebas automatizadas del backend.
- **Node.js:** ejecución de las pruebas del frontend.
- **uv:** gestión del entorno y las dependencias.
- **Yahoo Finance:** fuente de los datos históricos.
