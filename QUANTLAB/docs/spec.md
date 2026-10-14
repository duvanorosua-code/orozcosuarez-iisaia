# QUANTLAB — Especificación inicial

## 1. Descripción

QUANTLAB es una aplicación web que permite simular y comparar
estrategias de inversión utilizando datos históricos de activos
financieros.

## 2. Objetivo

Facilitar la experimentación con estrategias de inversión
mediante la comparación de rentabilidad y riesgo bajo condiciones
equivalentes.

## 3. Alcance del MVP

- Analizar un activo financiero inicialmente: SPY.
- Utilizar datos históricos almacenados localmente.
- Configurar capital inicial y período de análisis.
- Comparar Buy and Hold con una estrategia de cruce de medias móviles.
- Calcular métricas de rentabilidad y riesgo.
- Mostrar la evolución del capital.
- Guardar y consultar experimentos.

## 4. Tecnologías propuestas

- Frontend: HTML, CSS y JavaScript.
- Backend: Python y FastAPI.
- Procesamiento: pandas y NumPy.
- Persistencia: SQLite.
- Pruebas: pytest.
- Control de versiones: Git y GitHub.

## 5. Restricciones

- No se ejecutarán operaciones financieras reales.
- Los resultados históricos no garantizan resultados futuros.
- El sistema debe evitar el uso de información futura
  al generar señales de inversión.
- Los supuestos de costos y tratamiento de precios deben
  documentarse.

## 6. Criterios iniciales de aceptación

- El sistema puede cargar los datos históricos.
- Los datos se validan antes de ejecutar una simulación.
- Ambas estrategias pueden ejecutarse sobre el mismo período.
- Las métricas se calculan de forma consistente.
- Los resultados pueden visualizarse y guardarse.
- Las funcionalidades principales tienen pruebas.