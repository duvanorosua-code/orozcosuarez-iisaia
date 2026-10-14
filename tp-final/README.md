# QUANTLAB — Laboratorio de estrategias de inversión

QUANTLAB es el trabajo final que desarrollé para la materia de Desarrollo de Software Asistido con IA. Es una aplicación web para explorar precios históricos de ETF y comparar estrategias de inversión en escenarios experimentales.

La idea inicial fue construir una herramienta que permitiera entender, de una forma visual y práctica, cómo se comportan dos estrategias conocidas: **Buy & Hold** y el cruce de medias móviles simples (**SMA**). Quería que el usuario pudiera modificar algunos parámetros, ejecutar una comparación y revisar tanto las métricas como las operaciones que explican el resultado.

El alcance se mantuvo como un MVP. La aplicación tiene un modo descriptivo que trabaja con datos históricos de SPY y QQQ y un modo experimental que genera escenarios sintéticos para probar las estrategias. Esta separación es importante: los resultados del modo experimental no son rendimientos históricos reales.

## 1. Qué quise construir

El objetivo no era desarrollar una plataforma de trading ni recomendar inversiones. Quería crear un laboratorio pequeño donde se pudiera recorrer el flujo completo de una aplicación web: seleccionar opciones en el frontend, enviar una solicitud a una API, procesar datos en Python y presentar los resultados de forma comprensible.

El proyecto se organiza alrededor de dos modos:

- **Análisis histórico:** consulta estadísticas descriptivas y visualiza el precio de cierre de SPY y QQQ para un período seleccionado.
- **Comparación experimental:** ejecuta Buy & Hold y SMA sobre un mismo escenario sintético y permite comparar métricas, curvas de patrimonio y operaciones.

La aplicación no conserva un historial persistente de experimentos. Los resultados se calculan durante la ejecución y se devuelven al frontend.

## 2. Decisiones de diseño

### Separar los datos históricos de los escenarios sintéticos

Esta fue una de las decisiones más importantes. Para el análisis descriptivo utilizo archivos CSV con datos descargados de Yahoo Finance. Para las comparaciones experimentales, en cambio, el backend genera series sintéticas. Así puedo probar las estrategias en distintos contextos sin presentar una simulación como si fuera una inversión real.

### Usar tecnologías web sin añadir un framework de frontend

El frontend está hecho con HTML, CSS y JavaScript. Preferí trabajar con estas tecnologías directamente para entender cómo se conectan los formularios, los eventos, los gráficos y las solicitudes a la API, sin sumar un framework adicional al alcance del trabajo.

### Mantener la lógica financiera en Python

El backend usa FastAPI y módulos de Python para separar la API de las métricas, las estrategias, la gestión de la cartera y la generación de escenarios. De esta manera, la interfaz se ocupa de la interacción con el usuario y el backend de los cálculos.

### No incorporar una base de datos en el MVP

Los datos históricos se conservan localmente en CSV y la información asociada a los datasets se registra en metadatos JSON. No incorporé SQLite ni persistencia de comparaciones porque no eran necesarias para completar el flujo principal. Guardar experimentos y consultarlos después queda como una posible mejora.

### Bloquear el backtesting histórico mientras haya eventos pendientes

Aunque la aplicación permite consultar y visualizar los precios históricos de SPY y QQQ, no habilité las comparaciones de estrategias sobre esos datos. Durante la revisión encontré aspectos de dividendos que todavía necesitan conciliación. Preferí bloquear esa capacidad antes que mostrar resultados que pudieran interpretarse como un backtest financiero validado.

## 3. Arquitectura general

La aplicación tiene dos componentes principales:

1. **Frontend:** presenta los controles, consulta los activos disponibles, envía solicitudes al backend y muestra tablas, métricas y gráficos.
2. **Backend:** expone una API con FastAPI, carga y valida los datos cuando corresponde, genera escenarios experimentales, ejecuta estrategias y calcula resultados.

El intercambio entre ambos se realiza mediante solicitudes HTTP y respuestas JSON. El backend no depende de que el usuario interactúe directamente con los módulos internos: el frontend utiliza los endpoints de la API.

### Módulos principales del backend

- `data_loader.py`: descarga, guarda y valida datos históricos.
- `dataset_catalog.py`: define los datasets conocidos y las capacidades habilitadas para cada uno.
- `synthetic_data.py`: genera los escenarios sintéticos utilizados en los experimentos.
- `metrics.py`: calcula las métricas de desempeño.
- `portfolio.py`: administra el efectivo, las posiciones y las operaciones de la cartera.
- `strategies.py`: implementa Buy & Hold y el cruce de medias móviles.
- `comparison.py`: coordina la ejecución de estrategias bajo los mismos parámetros.
- `api_schemas.py` y `api.py`: definen los esquemas de entrada y salida y los endpoints de FastAPI.

El frontend se encuentra separado del backend y utiliza JavaScript para comunicarse con la API. Los gráficos se dibujan con Canvas.

## 4. Funcionalidades implementadas

### 4.1 Análisis histórico

El usuario puede seleccionar SPY o QQQ, establecer un rango de fechas y consultar información descriptiva del precio de cierre. La interfaz muestra el número de sesiones, los valores inicial y final, la variación del precio, la volatilidad y el drawdown, además de un gráfico de la serie.

Es importante distinguir estas estadísticas de la rentabilidad total de una inversión. El análisis mostrado se basa en el precio de cierre y no representa por sí solo una rentabilidad total que incluya correctamente todos los dividendos y eventos corporativos.

Los archivos históricos se mantienen localmente y no se suben al repositorio. Esto evita versionar los CSV de datos brutos. La aplicación comprueba la disponibilidad e integridad de los datasets antes de habilitar sus capacidades.

### 4.2 Comparación experimental

El modo experimental ofrece tres escenarios:

- Tendencia alcista.
- Mercado lateral.
- Alta volatilidad.

El usuario puede configurar el número de sesiones, el capital inicial, la comisión y las ventanas de las medias móviles. Luego, la aplicación ejecuta Buy & Hold y SMA sobre el mismo escenario y presenta las métricas, las curvas de patrimonio y las operaciones realizadas.

El selector de ETF permanece disponible como referencia visual, pero no cambia la serie sintética utilizada por el experimento. Por eso la interfaz aclara que la fuente de los resultados es sintética.

### 4.3 Estrategias y reglas de simulación

Buy & Hold sirve como referencia sencilla: compra y mantiene la posición. La estrategia SMA utiliza el cruce de medias móviles para generar señales. La señal se calcula con la información disponible al cierre de una sesión y la ejecución se realiza en la apertura siguiente, para evitar utilizar información futura al simular una operación.

La simulación contempla comisiones y valida el efectivo disponible antes de completar compras. El alcance actual no incluye posiciones cortas ni apalancamiento.

### 4.4 API

Entre los endpoints principales se encuentran:

- `GET /api/v1/datasets`: consulta el catálogo de datasets.
- `GET /api/v1/datasets/{dataset_id}`: consulta la información de un dataset.
- `GET /api/v1/datasets/{dataset_id}/summary`: devuelve el resumen descriptivo.
- `GET /api/v1/datasets/{dataset_id}/series`: devuelve la serie de precios para el rango solicitado.
- `POST /api/v1/comparisons`: solicita una comparación experimental; el backtesting histórico se bloquea cuando el dataset tiene eventos pendientes de procesar.

La API utiliza validaciones para rechazar solicitudes que no correspondan con las capacidades disponibles o que contengan parámetros inválidos.

## 5. Problemas que aparecieron durante el desarrollo

### 5.1 Una compra podía superar el efectivo disponible por una diferencia mínima

Durante las pruebas experimentales apareció un error en el que una compra podía ser rechazada porque el efectivo disponible quedaba ligeramente negativo. La diferencia era muy pequeña y estaba relacionada con la precisión numérica: el cálculo inicial de unidades parecía válido, pero el costo y la comisión se volvían a calcular al registrar la operación.

Ajusté el cálculo de las unidades para comprobar el costo con las mismas reglas que utiliza el libro de operaciones. Después añadí pruebas para comprobar que las estrategias se ejecutaran correctamente y que el efectivo no quedara por debajo de cero.

### 5.2 Buy & Hold y SMA producían el mismo resultado en tendencia alcista

En una de las pruebas, las curvas de las dos estrategias se superponían y las métricas coincidían. Al revisar las operaciones, encontré que ambas compraban en la misma apertura y mantenían la posición hasta el final. Por eso el resultado era el mismo.

No era necesariamente un problema del gráfico: en ese escenario sintético, las señales terminaban generando la misma operación. Conservé el comportamiento de las estrategias y utilicé las operaciones registradas para verificar que los resultados de la interfaz correspondieran con lo calculado en el backend.

### 5.3 El ticker podía confundirse con la fuente de los datos experimentales

Como el selector de ETF también aparece en el modo experimental, podía parecer que los resultados correspondían a los precios históricos del ticker elegido. Ajusté la interfaz para diferenciar el ETF seleccionado como referencia de la fuente sintética que utiliza la comparación.

También reemplacé avisos visuales demasiado llamativos por una nota más discreta que explica el origen de los datos experimentales.

### 5.4 Los datos históricos no estaban listos para un backtest

La revisión de los datos mostró que no bastaba con disponer de precios para considerar validada una simulación histórica. Los dividendos y otros eventos corporativos deben estar conciliados para que el cálculo del patrimonio sea coherente.

Por ese motivo dejé disponible el análisis descriptivo de SPY y QQQ, pero bloqueé el backtesting histórico hasta completar la revisión pendiente.

## 6. Datos y limitaciones conocidas

Los datos históricos de SPY y QQQ provienen de Yahoo Finance y están guardados localmente en CSV. Los archivos brutos y sus metadatos locales no se versionan en Git. La aplicación utiliza el catálogo y las comprobaciones de integridad para determinar qué capacidades puede ofrecer.

En esta versión:

- SPY y QQQ permiten análisis descriptivo y visualización de precios.
- El backtesting histórico de SPY y QQQ permanece bloqueado hasta conciliar los eventos corporativos pendientes.
- IWM, TLT y GLD aparecen en el catálogo, pero todavía no cuentan con datos locales validados para habilitar el análisis correspondiente.
- Los experimentos se ejecutan con datos sintéticos, no con precios históricos del ETF seleccionado.
- No existe persistencia de experimentos ni una base de datos SQLite.

Estas limitaciones forman parte del alcance actual y se muestran para evitar que el usuario interprete resultados experimentales como evidencia de rendimiento real.

## 7. Pruebas y validación

Además de revisar la aplicación en el navegador, incorporé pruebas automatizadas para validar la lógica del backend y los comportamientos principales del frontend. Las pruebas cubren las métricas, la cartera, las estrategias, las comparaciones, el catálogo de datasets, la carga de datos y la API.

También utilicé pruebas de regresión para verificar correcciones de problemas encontrados durante el desarrollo. La comprobación de sintaxis de JavaScript permite detectar errores antes de abrir la aplicación en el navegador.

Comandos utilizados para validar el proyecto:

```powershell
uv run pytest -v
```

```powershell
node --test tests/frontend_409.test.cjs
```

```powershell
node --check frontend/app.js
```

## 8. Estructura del proyecto

La carpeta `tp-final` contiene el backend, el frontend, las pruebas, la documentación y la configuración del proyecto. A nivel general, la organización es la siguiente:

```text
tp-final/
├── backend/          # API, carga de datos, estrategias y métricas
├── frontend/         # HTML, CSS y JavaScript de la aplicación
├── tests/            # Pruebas automatizadas
├── docs/             # Especificación, plan y documentación de la API
├── data/
│   └── raw/           # Datos históricos locales; no se versionan
├── pyproject.toml    # Configuración del proyecto y dependencias
├── uv.lock           # Versiones resueltas de dependencias
└── README.md         # Documentación principal
```

La estructura puede incluir otros archivos auxiliares de configuración y documentación.

## 9. Cómo ejecutar QUANTLAB en Windows

### Requisitos

- Python 3.12.
- `uv` instalado.
- Node.js instalado para ejecutar las pruebas del frontend.
- Conexión a internet para descargar dependencias cuando sea necesario y obtener datos históricos si se ejecuta el flujo de descarga.

Los siguientes comandos deben ejecutarse desde la carpeta `tp-final`, no desde la raíz del repositorio que contiene el trabajo.

### 9.1 Instalar las dependencias

```powershell
uv sync
```

### 9.2 Iniciar el backend

Abre una terminal de VS Code ubicada en `tp-final` y ejecuta:

```powershell
uv run uvicorn backend.api:app --reload --host 127.0.0.1 --port 8000
```

Deja esta terminal abierta mientras utilizas la aplicación.

### 9.3 Iniciar el frontend

Abre una segunda terminal, también ubicada en `tp-final`, y ejecuta:

```powershell
uv run python -m http.server 5500 --bind localhost --directory frontend
```

Después abre en el navegador:

```text
http://localhost:5500
```

El backend y el frontend se ejecutan en terminales separadas. Si se cierran, hay que volver a iniciar los procesos para utilizar la aplicación.

## 10. Flujo de uso sugerido

1. Iniciar el backend y el servidor del frontend siguiendo los pasos anteriores.
2. Abrir `http://localhost:5500` en el navegador.
3. Entrar en el modo de análisis histórico y seleccionar SPY o QQQ para revisar sus precios y estadísticas descriptivas.
4. Cambiar al modo de comparación experimental.
5. Seleccionar uno de los escenarios sintéticos y configurar los parámetros disponibles.
6. Ejecutar la comparación y revisar las métricas, las curvas de patrimonio y las operaciones de ambas estrategias.
7. Tener presente que los resultados del modo experimental corresponden a datos sintéticos y no representan una predicción ni una rentabilidad histórica real.

## 11. Trabajo asistido por IA

Utilicé Codex como apoyo durante el desarrollo, especialmente para organizar cambios por módulos, implementar funcionalidades, corregir errores y generar pruebas. El trabajo no consistió solamente en pedir que se escribiera código: fue necesario revisar los cambios, ejecutar la aplicación, reproducir errores y comprobar que las correcciones no afectaran funcionalidades existentes.

La separación entre especificación, plan, API, backend, frontend y pruebas ayudó a mantener el alcance controlado. Cuando apareció un problema —por ejemplo, el cálculo de efectivo o la confusión entre datos sintéticos e históricos— el proceso consistió en identificar el comportamiento, corregirlo y volver a ejecutar las pruebas relevantes.

La IA fue una herramienta de apoyo, pero las decisiones de alcance y las validaciones del resultado siguieron siendo necesarias durante el desarrollo.

## 12. Qué queda pendiente

Las mejoras que podrían abordarse en una siguiente versión son:

- Completar la conciliación de dividendos y otros eventos corporativos para evaluar la habilitación del backtesting histórico.
- Incorporar y validar datos históricos locales para IWM, TLT y GLD.
- Permitir guardar experimentos y consultar resultados anteriores.
- Evaluar SQLite u otra solución de persistencia si se incorpora un historial de comparaciones.
- Añadir estrategias y escenarios experimentales adicionales.
- Ampliar las pruebas y la documentación conforme crezcan las funcionalidades.

El objetivo de esta versión fue completar un MVP funcional y documentar con claridad qué hace, cómo se ejecuta y qué limitaciones tiene. La prioridad para una siguiente etapa sería validar mejor los datos históricos antes de ampliar las capacidades financieras.

## Tecnologías utilizadas

- **Python 3.12:** lógica de procesamiento, estrategias y métricas.
- **FastAPI:** API del backend.
- **HTML, CSS y JavaScript:** interfaz web.
- **Canvas:** gráficos de las series y curvas de patrimonio.
- **uv:** gestión del entorno y las dependencias.
- **pytest:** pruebas automatizadas del backend.
- **Node.js:** ejecución de pruebas del frontend y validación de sintaxis.
- **Yahoo Finance:** fuente de los datos históricos.

---

**Nota:** QUANTLAB es un proyecto académico de experimentación. Los resultados sintéticos sirven para comparar el comportamiento de las estrategias bajo supuestos controlados y no deben interpretarse como recomendaciones de inversión ni como garantías de rendimiento.
