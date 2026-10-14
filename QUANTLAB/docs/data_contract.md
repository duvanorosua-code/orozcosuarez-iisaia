# QUANTLAB — Contrato de datos del MVP

Este documento fija las decisiones y validaciones del MVP para adquirir y tratar datos históricos de SPY con yfinance antes de implementar el motor financiero. Los puntos que dependen de la respuesta real de Yahoo Finance o del entorno permanecen pendientes hasta superar los criterios de aceptación de la sección D.

## A. Decisiones recomendadas

### Versión y adquisición

La versión propuesta para fijar en el MVP es **`yfinance==1.7.0`**, identificada como la versión más reciente en la página oficial de releases consultada al preparar este contrato. La compatibilidad con la versión de Python y las dependencias del entorno QUANTLAB sigue pendiente; no se afirma que esté instalada ni que ya se haya validado en el proyecto. Antes de adoptarla, se comprobarán la compatibilidad del entorno y la API del tag `1.7.0`.

La adquisición será de SPY, frecuencia diaria, sesiones regulares y fechas de sesión de la bolsa. Se especificarán explícitamente estos parámetros:

- `interval="1d"`
- `auto_adjust=False`
- `actions=True`
- `back_adjust=False`
- `repair=False`
- `keepna=True`
- `prepost=False`
- `rounding=False`
- `progress=False`
- `multi_level_index=False`

`start` es inclusivo y `end` exclusivo según la documentación consultada. Ambos valores se registrarán. Se solicitarán suficientes datos previos para disponer de 50 sesiones válidas de calentamiento SMA50. Se comprobará el número de sesiones efectivamente recibido; una ventana de fechas calendario por sí sola no demuestra que haya 50 observaciones válidas.

El esquema de columnas se normalizará y validará al recibir la respuesta. No se confiará en valores predeterminados de la biblioteca. La descarga original aceptada se conservará como instantánea inmutable para el experimento, junto con metadatos y un hash SHA-256.

### Precios y splits

La base esperada, aún sujeta a verificación con el dataset real, es que Yahoo entrega OHLC ajustado por splits. `auto_adjust=False` significa que yfinance no aplica su ajuste automático a OHLC; **no significa** que las barras sean precios históricos sin ajuste por splits. La descripción de Yahoo yfinance y su lógica de reparación indican que pueden existir excepciones o errores.

No se aplicarán ajustes adicionales automáticamente a OHLC, unidades, volumen ni eventos. Antes de simular, se comprobará que `Open`, `High`, `Low`, `Close`, unidades del activo y eventos corporativos puedan reconciliarse en una base común. Si no se puede establecer una base coherente, el dataset queda bloqueado para simulación. En particular, si aparece un split y no se confirma la escala relativa de precios, unidades y dividendos, se rechazará el dataset hasta resolverlo.

El valor `Adj Close` se conservará como dato de referencia, pero no se usará para ejecutar órdenes ni valorar el ledger cuando los dividendos se contabilicen por separado. Las señales SMA y la valoración usarán `Close`; la ejecución usará `Open`.

### Dividendos

Cada registro de dividendo tendrá estos campos:

- `ex_date`: fecha ex-dividendo que determina el derecho.
- `payment_date`: fecha de pago confirmada; puede quedar sin valor mientras no se verifique.
- `amount_per_unit`: importe por unidad con precisión decimal.
- `currency`: moneda del importe.
- `source_reference`: fuente primaria y referencia del evento.
- `verified_at`: fecha de verificación y, si aplica, observaciones de la validación.

El importe, moneda y base por unidad se comprobarán contra una fuente oficial del fondo y se reconciliarán con la escala de unidades de OHLC. La serie de yfinance por sí sola no se considerará prueba suficiente de esos términos.

En la ex-date se reconocerá un derecho de cobro por las unidades con derecho, separado del efectivo disponible. El derecho no será gastable. Solo se trasladará a efectivo disponible en la fecha de pago cuando esta se haya verificado. Si no se puede verificar, seguirá como dividendo por cobrar, incluso al cierre de la simulación. El traslado de cuenta por cobrar a efectivo no creará patrimonio adicional.

### Señales, período evaluado y operaciones

La SMA20 y SMA50 se calcularán con cierres disponibles hasta la sesión en curso. Una señal determinada al cierre de la sesión `t` solo podrá ejecutarse en la apertura de la siguiente sesión bursátil válida. Ninguna señal usará el `Open` de la sesión en la que se calcula.

Las 50 sesiones de calentamiento preceden al período medido y no forman parte de las métricas ni de las curvas comparadas. El inicio evaluado se define por la primera apertura común disponible para ambas estrategias. Buy and Hold y SMA empiezan con el mismo capital en esa apertura. Se usarán unidades fraccionarias en ambas para hacer comparable la inversión del capital, aplicando la misma regla y costos.

La señal del último cierre del período no se ejecutará si no existe una apertura posterior dentro del rango. Las posiciones permanecerán abiertas y se valorarán al cierre de la última sesión; no se generará liquidación artificial.

### Costos y patrimonio

Se aplicará a cada compra y venta un costo del **0,1 % del nocional**. Ambas estrategias estarán sujetas a la misma tasa y regla de cálculo. El ledger impedirá efectivo disponible negativo, posiciones cortas y apalancamiento.

El patrimonio diario al cierre será:

`E_t = efectivo_disponible_t + unidades_t × Close_t + dividendos_por_cobrar_t`

Los dividendos por cobrar se incluyen por su importe nominal confirmado y se mantienen separados del efectivo. Al pagarse, se reduce el derecho y aumenta el efectivo por el mismo importe, de modo que no se contabilice dos veces.

### Métricas y convenciones

Sea `E_0` el capital inicial aportado y `E_t` el patrimonio diario en las fechas de valoración. Sea `N` el número de intervalos de valoración desde el capital inicial hasta el cierre final. Se usa el factor convencional de 252 sesiones por año.

- **Retorno acumulado:** `E_T / E_0 - 1`.
- **Retorno del intervalo diario:** `r_t = E_t / E_(t-1) - 1`. El primer intervalo se calcula desde el capital inicial hasta la primera valoración diaria.
- **Retorno anualizado:** `(E_T / E_0)^(252 / N) - 1`. Se usa también en períodos que no duran exactamente un año; es una anualización según la convención de 252 sesiones, no una observación real de un año. Requiere `E_0 > 0`, `E_T > 0` y `N > 0`.
- **Volatilidad anualizada:** desviación estándar muestral (`ddof=1`) de los retornos diarios válidos multiplicada por `sqrt(252)`. No es calculable con menos de dos retornos válidos.
- **Maximum drawdown:** máximo de `1 - E_t / max(E_s)` para `s ≤ t`, incluyendo el capital inicial `E_0` como primer máximo. Se expresa como fracción positiva; por ejemplo, `0.20` equivale a 20 %.

Cuando una serie no cumple los datos mínimos o las condiciones matemáticas de una métrica, esta se marcará como no calculable, con motivo explícito; no se sustituirá por cero.

Ambas estrategias compartirán capital inicial, tasa y reglas de costos, período evaluado, fechas de valoración, base de precios y unidades, tratamiento de dividendos y convención de métricas. La valoración final se hará en la misma fecha para ambas.

## B. Hechos documentados

- La documentación oficial de `yfinance.download` describe `auto_adjust` como el ajuste automático de OHLC y `actions` como la descarga de dividendos y splits. También documenta `start` inclusivo y `end` exclusivo.
- En la consulta realizada para preparar este contrato, la página oficial de releases de yfinance marcaba `1.7.0` como `Latest`. El código fuente del tag `1.7.0` permite contrastar la firma de descarga usada como referencia. Esto no valida compatibilidad con el entorno QUANTLAB.
- Yahoo Finance describe `Close` como ajustado por splits, y `Adj Close` como ajustado por splits y dividendos u otras distribuciones.
- La documentación de reparación de yfinance describe casos de ajuste de split faltante, ajuste de dividendos, datos faltantes y errores de precios. `repair=True` intenta reparar determinados casos y puede cambiar datos; el contrato propone `repair=False` y validación explícita.
- Investor.gov distingue ex-date y fecha pagadera y explica que comprar en la ex-date o después no da derecho al próximo dividendo.

Fuentes oficiales consultadas:

- [Release de yfinance 1.7.0](https://github.com/ranaroussi/yfinance/releases/tag/1.7.0)
- [Código de `download` en el tag 1.7.0](https://github.com/ranaroussi/yfinance/blob/1.7.0/yfinance/multi.py)
- [Referencia oficial de `yfinance.download`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html)
- [Historial de SPY en Yahoo Finance](https://finance.yahoo.com/quote/SPY/history/)
- [Guía oficial de reparación de precios de yfinance](https://ranaroussi.github.io/yfinance/advanced/price_repair.html)
- [Investor.gov: ex-date y derechos de dividendos](https://www.investor.gov/introduction-investing/investing-basics/glossary/ex-dividend-dates-when-are-you-entitled-stock-and-cash-dividends)

## C. Hipótesis pendientes de validación

1. La compatibilidad de `yfinance==1.7.0` con la versión de Python y las dependencias que QUANTLAB vaya a fijar. La versión no se considera aprobada para el entorno hasta verificarlo.
2. Que las barras OHLC de SPY para el rango real estén ajustadas por splits de forma correcta y uniforme.
3. Que las fechas y ratios de `Stock Splits`, la escala de precios y la escala de unidades puedan reconciliarse.
4. Que el importe de `Dividends` esté en la moneda y base por unidad esperadas, compatibles con los precios y las unidades del ledger.
5. Que cada fecha de pago y término de distribución pueda verificarse mediante una fuente primaria del fondo o de mercado.
6. Que fechas, zona horaria y calendario de sesiones devueltos sean consistentes con las sesiones de mercado del rango seleccionado.
7. Que la respuesta histórica de Yahoo no cambie en descargas futuras. El CSV preservado y su hash identifican la instantánea usada, pero no aseguran que una descarga nueva sea idéntica.

No se considerará validada ninguna de estas hipótesis por la sola descripción de la API. Se deben resolver con pruebas contra la versión fijada y el conjunto real propuesto antes de habilitar simulaciones.

## D. Criterios de aceptación

El conjunto solo puede usarse en una simulación si supera todos los controles aplicables. No se permiten ajustes automáticos adicionales para hacer que un control pase.

### Esquema y tipos

- Las columnas requeridas de precio son `Open`, `High`, `Low` y `Close`; se conserva `Adj Close` si está presente. Se requieren `Volume`, `Dividends` y `Stock Splits` para validar el esquema de acciones solicitado.
- El índice representa fechas de sesión únicas en una convención de zona horaria documentada. Se registran moneda y zona horaria de mercado.
- Precios e importes son numéricos, finitos y se conservan con precisión decimal suficiente; volumen es numérico entero no negativo. Los campos de acción son numéricos y no negativos.
- Se rechazan columnas ambiguas, nombres no normalizados, niveles múltiples inesperados o tipos que no puedan convertirse sin pérdida no documentada.

### Fechas, sesiones y faltantes

- Se rechaza cualquier fecha duplicada o índice fuera de orden.
- Se contrasta el rango con un calendario oficial de sesiones. Fines de semana y festivos no cuentan como faltantes.
- Una sesión esperada sin barra OHLC completa dentro del período evaluado bloquea el conjunto. No se interpolan precios ni se arrastra el cierre previo.
- Se confirma que hay al menos 50 cierres válidos anteriores al inicio medido para el calentamiento SMA50.

### Validación OHLC

Para cada sesión evaluada:

- todos los precios OHLC son finitos y mayores que cero;
- `Low ≤ min(Open, Close)`;
- `High ≥ max(Open, Close)`;
- `Low ≤ High`.

Una fila NaN o cualquier relación inválida bloquea el conjunto. Las diferencias entre `Close` y `Adj Close` se interpretan como una diferencia de ajuste que debe documentarse, no se corrigen automáticamente.

### Pruebas de aceptación de splits

- Para cada split real dentro del rango, contrastar fecha y ratio con una fuente primaria y verificar la escala de OHLC antes y después del evento.
- Verificar que unidades y dividendos por unidad puedan expresarse en la misma base que los precios empleados en el ledger.
- Usar un fixture sintético 2:1 con una versión no ajustada y otra ya ajustada de los precios. La prueba debe identificar la base entregada y confirmar que no se aplica el ratio dos veces ni se crea PnL artificial.
- El fixture debe demostrar que el sistema bloquea una serie con ratios o bases incongruentes. No debe “repararla” durante la simulación.
- Cualquier split real cuya escala no pueda reconciliarse bloquea el dataset.

### Pruebas de aceptación de dividendos

- Para cada distribución real, comparar ex-date, fecha de pago, importe por unidad y moneda con documentación primaria del fondo o fuente de mercado aceptada.
- Comprobar la base por unidad y su compatibilidad con las unidades del activo usadas en el ledger.
- En fixture, una posición elegible genera derecho en ex-date; vender después de esa fecha no elimina ese derecho; comprar en o después de ex-date no genera el derecho de ese evento.
- Antes de la fecha de pago verificada, el monto permanece en dividendos por cobrar y no puede financiar operaciones. En fecha de pago, se traslada de cuenta por cobrar a efectivo sin cambiar el patrimonio total.
- Importe, moneda, base o fecha no reconciliados bloquean la simulación con esos datos. Una fecha de pago no verificada nunca se convierte en efectivo disponible.

### Prevención de look-ahead

- Un fixture con cruce SMA al cierre de `t` debe producir una operación solo en la apertura de la siguiente sesión disponible.
- Una señal de `t` se calcula solo con datos hasta el cierre de `t`; ningún precio posterior influye en ella.
- Una prueba de perturbación cambia precios posteriores a `t` y confirma que señales y operaciones previas a esos cambios no se alteran.
- No se ejecutan órdenes en la apertura de la misma sesión cuyo cierre produjo la señal.

### Costos, ledger y valoración final

- Buy and Hold y SMA usan el mismo capital inicial, primera apertura común, comisión de 0,1 % del nocional por compra/venta, regla de unidades fraccionarias, período evaluado y fechas de valoración.
- Fixtures verifican que cada compra y venta descuente el costo correcto, que no haya efectivo negativo, posiciones cortas ni apalancamiento y que efectivo, unidades, costos y derechos reconcilien.
- En cada fecha: `patrimonio = efectivo disponible + unidades × Close + dividendos por cobrar`.
- Al pagarse un dividendo, el patrimonio no aumenta por el simple traslado de cuenta por cobrar a efectivo.
- La última fecha valorada es idéntica para ambas estrategias. Las posiciones permanecen abiertas y una señal del último cierre no se ejecuta si no existe una apertura posterior en el rango.
- Fixtures de equity conocido verifican retorno acumulado, retorno anualizado con 252/N, volatilidad muestral anualizada y maximum drawdown. Las métricas sin observaciones suficientes se marcan no calculables, no cero.

## E. Limitaciones del MVP

- Yahoo Finance/yfinance es una fuente externa; la documentación describe funciones y reparaciones, no garantiza exactitud integral, estabilidad histórica ni inmutabilidad de los datos.
- La aceptación de fixtures sintéticos comprueba reglas contables y de detección, pero no valida por sí sola cada dato real de SPY.
- Hasta que la compatibilidad de `yfinance==1.7.0` se verifique en el entorno, la versión propuesta es una decisión pendiente de validación técnica.
- Los dividendos con fecha de pago no verificada permanecen como derecho no gastable; el simulador no podrá reinvertirlos.
- La anualización con 252 sesiones es una convención de comparación; en períodos cortos las métricas anualizadas pueden ser inestables y no representan un año observado.
- El MVP no modela impuestos, retenciones, deslizamiento, spread, liquidez, costos de custodia ni reglas particulares de brokers.
- El uso de unidades fraccionarias es una simplificación para comparar estrategias con el mismo capital y no representa las restricciones de todos los intermediarios.