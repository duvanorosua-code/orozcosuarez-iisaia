# QUANTLAB — Estado del plan del MVP

**Estado general:** MVP funcional para análisis descriptivo de SPY/QQQ y
comparación experimental con datos sintéticos. La simulación histórica de los
dos ETF sigue bloqueada. Este plan registra la situación actual y los asuntos
pendientes; no cambia las reglas financieras aprobadas en
[`data_contract.md`](data_contract.md).

## Principios vigentes

- Especificación y contrato de datos documentan las decisiones técnicas y
  financieras.
- Fixtures sintéticos/manuales son la base de las pruebas; las pruebas no
  dependen de una descarga viva.
- Las instantáneas descargadas se identifican por archivo, hash, metadatos,
  versión de yfinance y parámetros de adquisición.
- No se habilita backtesting histórico hasta reconciliar precios, unidades y
  eventos corporativos.
- Los resultados de escenarios sintéticos se identifican y mantienen
  separados de la descripción histórica.

## Estado por etapa

| Etapa | Estado | Resultado y asuntos pendientes |
|---|---|---|
| 0. Contrato de datos | Parcial; bloquea simulación histórica | Convenciones OHLC, efectivo, dividendos, splits, costos, métricas y aceptación están documentadas. Persisten conciliaciones de eventos reales, incluida la discrepancia comunicada para SPY y eventos pendientes de QQQ. |
| 1. Estructura y entorno | Implementada | Proyecto Python con `uv`, `pyproject.toml`, `uv.lock`, frontend estático y configuración de pytest. |
| 2. Adquisición y validación | Implementada para los datos registrados | Existe cargador y persistencia local con metadatos/hash; SPY y QQQ tienen instantáneas descriptivas. La validación estructural y del calendario no resuelve por sí sola los términos de dividendos. |
| 3. Ledger y eventos | Implementada con límites | Portfolio registra efectivo, unidades, costos, operaciones fechadas y derechos/pagos sintéticos de dividendos. El procesamiento real completo de splits y distribuciones no está habilitado en las estrategias. |
| 4. Estrategias y comparación | Implementada | Buy & Hold y SMA usan calentamiento, señales al cierre y ejecución en apertura posterior. Comparador experimental y endpoints históricos conservan bloqueos corporativos. |
| 5. Métricas | Implementada | Retorno acumulado/anualizado, volatilidad anualizada y drawdown se calculan desde curvas fechadas de patrimonio según el contrato. |
| 6. API | Implementada sin persistencia | FastAPI expone catálogo, metadatos, resumen, serie Close y comparaciones histórica/experimental. SQLite e historial persistente de experimentos no están implementados. |
| 7. Interfaz | Implementada | HTML/CSS/JavaScript presenta catálogo, análisis descriptivo, gráfico histórico, formulario experimental, métricas, curvas y operaciones. |
| 8. Integración y entrega | En preparación académica | La operación manual y las pruebas se validaron. Resta mantener la documentación coherente y declarar las limitaciones; no se habilita simulación histórica mientras haya bloqueos. |

## Decisiones financieras que se conservan

- SMA calcula con cierres disponibles hasta la sesión actual; ejecuta la señal
  en la apertura de la sesión siguiente.
- El calentamiento anterior no forma parte de las curvas ni métricas evaluadas.
- Buy & Hold y SMA comparten capital, comisión, período y fechas de valoración.
- La comisión predeterminada es 0,1 % del nocional por compra o venta.
- Se impiden efectivo negativo, posiciones cortas y apalancamiento.
- La valoración al cierre incluye efectivo, unidades por `Close` y dividendos
  por cobrar; las posiciones finales no se liquidan artificialmente.
- La anualización usa 252 sesiones; la volatilidad usa desviación estándar
  muestral; las métricas no calculables se exponen con motivo, no como cero.
- No se mezcla `Adj Close` con dividendos contabilizados por separado ni se
  aplican ajustes automáticos adicionales a splits.
- Eventos corporativos no procesados o no reconciliados mantienen bloqueada
  una simulación histórica.

## Pendientes fuera del MVP presentado

1. Conciliar los términos oficiales y la base por unidad de dividendos reales
   de SPY y QQQ, y resolver la discrepancia de SPY documentada en el contrato.
2. Completar la reconciliación de splits/precios si se identifican eventos que
   afecten el rango y la escala de unidades.
3. Validar fuentes, esquema, sesiones y eventos corporativos de IWM, TLT y GLD
   antes de registrar datos o habilitar funciones históricas.
4. Diseñar y aprobar persistencia de experimentos; SQLite no forma parte del
   MVP actual.
5. Evaluar aprendizaje por refuerzo solo como una fase futura independiente;
   no existe implementación en este MVP.

Los pendientes anteriores no autorizan a omitir validaciones ni a cambiar las
fórmulas, contratos de datos o reglas de estrategias.
