# QUANTLAB — Plan de implementación del MVP

**Estado:** plan actualizado con convenciones temporales y contables aprobadas. El motor financiero queda condicionado al cierre de los bloqueos de datos corporativos en la etapa 0.

## Principios

- Especificación primero; decisiones de datos y contabilidad documentadas antes de codificar.
- Fixtures sintéticos/manuales como oráculo principal; no depender de una descarga viva para probar cálculos.
- Cada experimento referencia CSV preservado, hash/metadatos, versión de `yfinance` y parámetros exactos.
- Cada etapa se revisa contra criterios de aceptación y se guarda en un commit enfocado; no mezclar cambios fuera de QUANTLAB.

## Etapas

### 0. Cerrar contrato de datos y contabilidad corporativa

- Fijar aniversario/calendario/zona de sesión, límites temporales e intervalo evaluado de cinco años más calentamiento SMA50.
- Confirmar con versión/configuración concreta la forma de columnas y semántica de `Open`, `Close`, `Adj Close`, `Dividends` y `Stock Splits` con `auto_adjust=False`, `actions=True`.
- Determinar si OHLC ya está ajustado por splits; evitar transformar precios y unidades dos veces.
- Resolver fecha de pago de dividendos: dato verificable o receivable no gastable; documentar cualquier aproximación.
- Definir control de calidad, esquema de CSV, hash, retención y manejo de errores/advertencias.
- **Salida:** contrato de datos aprobado y ledger de eventos corporativos no ambiguo.
- **Aceptación:** bloqueos 1 y 2 de `spec.md` resueltos antes de etapa 3; los demás bloqueos quedan fijados aquí.

### 1. Esqueleto y entorno

- Crear estructura Python/web y configuración reproducible, pruebas pytest y guía de ejecución según alcance autorizado.
- Separar adquisición, señales, contabilidad, métricas y API.
- **Aceptación:** configuración ejecutable y tests base offline; commit independiente.

### 2. Adquisición, persistencia de datos y validación

- Descargar SPY diario en rango de cinco años más calentamiento suficiente; `auto_adjust=False`, `actions=True` explícitos.
- Guardar CSV inmutable y metadatos: versión de biblioteca, parámetros, hora, intervalo, campos y hash.
- Validar fechas/sesiones, duplicados, faltantes, OHLC, eventos y consistencia de los precios.
- **Aceptación:** fixtures válidos/anómalos verifican contrato; recarga conserva datos; verificación de split/dividendos documentada; pruebas no requieren red; commit de datos.

### 3. Ledger de cartera, ejecución y eventos

- Implementar posiciones, efectivo disponible y derechos de dividendos; aplicar operaciones en Open de sesión posterior a señal.
- Cobrar 0,1 % del nocional de cada compra/venta; impedir caja negativa, cortos y apalancamiento.
- Aplicar splits según base OHLC confirmada; acreditar dividendos según derecho y fecha/regla confirmada sin duplicarlos.
- Valorar a Close cada sesión y mantener posiciones abiertas al fin sin liquidación artificial.
- **Aceptación:** ejemplos manuales reconcilian efectivo, unidades, receivables, costos y equity; split no genera PnL artificial; no hay operación terminal; commit de ledger.

### 4. Estrategias y período común

- Implementar Buy and Hold y SMA20/50; calentamiento anterior al período evaluado.
- Señales solo al cierre con historia disponible; operar en la siguiente apertura.
- Iniciar ambas estrategias con mismo capital en la misma primera apertura común; aplicar a SMA el estado de la señal válida del cierre previo.
- **Aceptación:** prueba de cruce y desfase; perturbación futura/prefijo; idénticas fechas de equity y comparación; commit de estrategias.

### 5. Métricas

- Calcular métricas desde equity diario (efectivo + unidades a Close + derechos de dividendos), después de costos.
- Aplicar las fórmulas de `spec.md`, factor 252 y reglas para series/equity no calculables.
- **Aceptación:** ejemplos pequeños manuales validan seis métricas y conteo de operaciones; commit de métricas.

### 6. SQLite y API FastAPI

- Persistir parámetros, intervalos, dataset/CSV/hash, configuración de descarga, ledger, métricas y advertencias.
- Exponer ejecución de comparación y consulta de experimentos; admitir datos de prueba inyectados para integración offline.
- **Aceptación:** crear/recuperar experimento mantiene trazabilidad íntegra; commit API/persistencia.

### 7. Interfaz

- Formulario de parámetros, curvas y métricas comparadas, historial de experimentos.
- Mostrar rango, calentamiento, capital, costo ilustrativo, fuente, fecha/configuración de descarga y limitaciones.
- **Aceptación:** recorrido completo compara y vuelve a consultar experimento; commit de interfaz.

### 8. Integración y entrega

- Ejecutar suite completa sobre fixtures; realizar una descarga real solo cuando esté autorizada y registrar artefacto/configuración.
- Revisar reconciliación de ledger, criterios de temporalidad, reproducibilidad, limitaciones y documentación.
- **Aceptación:** cada criterio aplicable de `spec.md` tiene evidencia; problemas conocidos declarados; commits verificables.

## Commits orientativos

1. `docs: cerrar especificación temporal y de cartera`
2. `chore: esqueleto y entorno de pruebas`
3. `feat: descarga y validación de datos SPY`
4. `feat: ledger, dividendos, splits y costos`
5. `feat: estrategias buy-and-hold y SMA`
6. `feat: métricas de desempeño`
7. `feat: persistencia y API`
8. `feat: interfaz de comparación`
9. `docs: guía de uso y limitaciones`

Cada commit contiene solo cambios de su etapa y se crea después de revisar la evidencia correspondiente.
