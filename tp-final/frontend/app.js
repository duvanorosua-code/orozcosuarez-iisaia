(() => {
  "use strict";

  const API_URL = "http://127.0.0.1:8000/api/v1/comparisons";
  const EXPERIMENTAL_API_URL = "http://127.0.0.1:8000/api/v1/experimental/comparisons";
  const API_BASE_URL = "http://127.0.0.1:8000/api/v1";
  const DATASETS_API_URL = `${API_BASE_URL}/datasets`;
  const form = document.querySelector("#comparison-form");
  const submitButton = document.querySelector("#run-button");
  const buttonLabel = submitButton.querySelector(".button-label");
  const formError = document.querySelector("#form-error");
  const statusTitle = document.querySelector("#status-title");
  const statusMessage = document.querySelector("#status-message");
  const statusTag = document.querySelector("#status-tag");
  const connectionIndicator = document.querySelector("#connection-indicator");
  const errorPanel = document.querySelector("#error-panel");
  const errorTitle = document.querySelector("#error-title");
  const errorMessage = document.querySelector("#error-message");
  const analysisPanel = document.querySelector("#dataset-analysis");
  const analysisTitle = document.querySelector("#analysis-title");
  const analysisMessage = document.querySelector("#analysis-message");
  const analysisDetails = document.querySelector("#analysis-details");
  const warningPanel = document.querySelector("#warning-panel");
  const warningList = document.querySelector("#warning-list");
  const emptyState = document.querySelector("#empty-state");
  const results = document.querySelector("#results");
  const chart = document.querySelector("#equity-chart");
  const tradesBody = document.querySelector("#trades-body");
  const noTrades = document.querySelector("#no-trades");
  const tradeCount = document.querySelector("#trade-count");
  const metricNote = document.querySelector("#metric-note");
  const strategyButtons = [...document.querySelectorAll("[data-focus]")];
  const datasetSelect = document.querySelector("#dataset-id");
  const datasetInstrument = document.querySelector("#dataset-instrument");
  const datasetExposure = document.querySelector("#dataset-exposure");
  const datasetStatus = document.querySelector("#dataset-validation-status");
  const datasetPeriod = document.querySelector("#dataset-available-period");
  const datasetCapabilities = document.querySelector("#dataset-capabilities");
  const datasetValidationNote = document.querySelector("#dataset-validation-note");
  const modeSelect = document.querySelector("#analysis-mode");
  const scenarioSelect = document.querySelector("#synthetic-scenario");
  const sourceIndicatorMain = document.querySelector("#source-indicator-main");
  const sourceIndicatorDetail = document.querySelector("#source-indicator-detail");
  const sourceIndicatorScenario = document.querySelector("#source-indicator-scenario");
  const datasetSelectLabel = document.querySelector("#dataset-select-label");
  const modeIndicatorLabel = document.querySelector("#mode-indicator-label");
  const historicalSummary = document.querySelector("#historical-summary");
  const historicalPriceCanvas = document.querySelector("#historical-price-chart");
  const historicalPriceStatus = document.querySelector("#historical-price-status");
  const historicalPricePeriod = document.querySelector("#historical-price-period");
  const summaryTitle = document.querySelector("#historical-summary-title");
  const resultsSourceNote = document.querySelector("#results-source-note");
  const summaryValues = document.querySelector("#summary-values");
  const summaryStatus = document.querySelector("#summary-status");
  const summaryError = document.querySelector("#summary-error");
  const summaryPeriodNote = document.querySelector("#summary-period-note");
  const summaryUnavailable = document.querySelector("#summary-unavailable");

  let pending = false;
  let currentComparison = null;
  let currentFocus = "both";
  let summaryRequestId = 0;
  let priceSeriesRequestId = 0;
  let currentPriceSeries = null;
  let datasetCatalog = new Map();
  let catalogReady = false;

  const formatNumber = new Intl.NumberFormat("es-CO", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  const formatCurrency = new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  const formatPercent = new Intl.NumberFormat("es-CO", {
    style: "percent",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  function clearSummary() {
    summaryValues.hidden = true;
    summaryError.hidden = true;
    summaryError.textContent = "";
    summaryPeriodNote.hidden = true;
    summaryPeriodNote.textContent = "";
    summaryUnavailable.hidden = true;
    summaryUnavailable.textContent = "";
    ["#summary-sessions", "#summary-dates", "#summary-prices", "#summary-change", "#summary-volatility", "#summary-drawdown", "#summary-events"].forEach((selector) => {
      document.querySelector(selector).textContent = "—";
    });
  }

  function clearHistoricalPriceChart(message = "") {
    currentPriceSeries = null;
    historicalPriceCanvas.hidden = true;
    const context = historicalPriceCanvas.getContext("2d");
    if (context) context.clearRect(0, 0, historicalPriceCanvas.width, historicalPriceCanvas.height);
    historicalPriceStatus.textContent = message;
  }

  function validCatalogItem(item) {
    return item && typeof item.dataset_id === "string" && typeof item.ticker === "string" &&
      typeof item.name === "string" && typeof item.asset_type === "string" &&
      typeof item.exposure === "string" &&
      typeof item.currency === "string" &&
      ["pending_validation", "descriptive_only", "historical_simulation"].includes(item.validation_status) &&
      item.capabilities && typeof item.capabilities.descriptive_analysis === "boolean" &&
      typeof item.capabilities.historical_simulation === "boolean" &&
      typeof item.validation_note === "string" &&
      (item.sha256 === null || /^[a-f0-9]{64}$/.test(item.sha256)) &&
      (item.available_start === null || typeof item.available_start === "string") &&
      (item.available_end === null || typeof item.available_end === "string");
  }

  function statusLabel(status) {
    return {
      pending_validation: "Pendiente de validación",
      descriptive_only: "Apto para análisis descriptivo",
      historical_simulation: "Apto para simulación histórica",
    }[status] || "Estado desconocido";
  }

  function updateDatasetDetails() {
    const item = datasetCatalog.get(datasetSelect.value);
    updateSourceIndicator();
    summaryTitle.textContent = item ? `Análisis descriptivo de ${item.ticker}` : "Análisis descriptivo";
    if (!item) {
      datasetStatus.textContent = catalogReady ? "Dataset no registrado" : "Consultando catálogo…";
      datasetPeriod.textContent = "—";
      datasetInstrument.textContent = "—";
      datasetExposure.textContent = "—";
      datasetCapabilities.textContent = "—";
      datasetValidationNote.textContent = "";
      return;
    }
    datasetInstrument.textContent = `${item.ticker} · ${item.name}`;
    datasetExposure.textContent = item.exposure;
    datasetStatus.textContent = statusLabel(item.validation_status);
    datasetPeriod.textContent = item.available_start && item.available_end
      ? `${item.available_start} → ${item.available_end}`
      : "Aún no disponible";
    const enabled = [];
    if (item.capabilities.descriptive_analysis) enabled.push("análisis descriptivo");
    if (item.capabilities.historical_simulation) enabled.push("simulación histórica");
    datasetCapabilities.textContent = enabled.length ? enabled.join(" · ") : "Ninguna";
    datasetValidationNote.textContent = item.validation_note;
  }

  function updateSourceIndicator() {
    const item = datasetCatalog.get(datasetSelect.value);
    if (modeSelect.value === "experimental") {
      const scenarios = {
        uptrend: "Tendencia alcista",
        sideways: "Mercado lateral",
        high_volatility: "Alta volatilidad",
      };
      sourceIndicatorMain.textContent = item ? `ETF de referencia · ${item.ticker}` : "ETF de referencia";
      sourceIndicatorDetail.textContent = "Datos sintéticos";
      sourceIndicatorScenario.textContent = scenarios[scenarioSelect.value] || "Escenario no seleccionado";
      sourceIndicatorScenario.hidden = false;
      datasetSelectLabel.textContent = "ETF de referencia";
      return;
    }
    sourceIndicatorMain.textContent = item ? item.ticker : "Datos históricos";
    sourceIndicatorDetail.textContent = "Datos históricos locales";
    sourceIndicatorScenario.textContent = "";
    sourceIndicatorScenario.hidden = true;
    datasetSelectLabel.textContent = "ETF";
  }

  async function loadDatasetCatalog() {
    datasetSelect.disabled = true;
    try {
      const response = await fetch(DATASETS_API_URL, { method: "GET", headers: { Accept: "application/json" } });
      let body;
      try { body = await response.json(); } catch { body = {}; }
      if (!response.ok) throw new Error(`No se pudo cargar el catálogo (HTTP ${response.status}).`);
      if (!Array.isArray(body.datasets) || !body.datasets.length || !body.datasets.every(validCatalogItem)) {
        throw new Error("La respuesta del catálogo no coincide con el contrato esperado.");
      }
      datasetCatalog = new Map(body.datasets.map((item) => [item.dataset_id, item]));
      datasetSelect.replaceChildren();
      body.datasets.forEach((item) => {
        const option = document.createElement("option");
        option.value = item.dataset_id;
        option.textContent = `${item.ticker} · ${item.name}`;
        datasetSelect.append(option);
      });
      datasetSelect.value = datasetCatalog.has("spy-2020-2025") ? "spy-2020-2025" : body.datasets[0].dataset_id;
      catalogReady = true;
      datasetSelect.disabled = false;
      updateDatasetDetails();
      if (modeSelect.value !== "experimental") {
        await Promise.all([loadDatasetSummary(), loadHistoricalPriceSeries()]);
      }
    } catch (error) {
      datasetCatalog = new Map();
      catalogReady = false;
      datasetSelect.replaceChildren();
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "Catálogo no disponible";
      datasetSelect.append(option);
      datasetSelect.value = "";
      datasetSelect.disabled = true;
      updateDatasetDetails();
      clearSummary();
      historicalPricePeriod.disabled = true;
      clearHistoricalPriceChart("No se pudo cargar el catálogo de activos.");
      summaryError.textContent = error instanceof TypeError
        ? "No se pudo conectar con el backend para cargar los activos disponibles."
        : error.message;
      summaryError.hidden = false;
      summaryStatus.textContent = "Catálogo no disponible";
    }
  }

  function subtractCalendarMonths(isoDate, months) {
    const date = new Date(`${isoDate}T00:00:00Z`);
    const day = date.getUTCDate();
    date.setUTCDate(1);
    date.setUTCMonth(date.getUTCMonth() - months);
    const lastDay = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 0)).getUTCDate();
    date.setUTCDate(Math.min(day, lastDay));
    return date.toISOString().slice(0, 10);
  }

  async function loadHistoricalPriceSeries() {
    const requestId = ++priceSeriesRequestId;
    const datasetId = datasetSelect.value;
    clearHistoricalPriceChart("Cargando precios históricos de cierre…");
    const item = datasetCatalog.get(datasetId);
    if (!item || !item.capabilities.descriptive_analysis || !item.available_start || !item.available_end) {
      historicalPricePeriod.disabled = true;
      clearHistoricalPriceChart(item?.validation_note || "Este activo no tiene una serie histórica descriptiva disponible.");
      return;
    }
    historicalPricePeriod.disabled = false;

    const months = { "3m": 3, "6m": 6, "1y": 12 }[historicalPricePeriod.value];
    const startDate = months
      ? [subtractCalendarMonths(item.available_end, months), item.available_start].sort().at(-1)
      : item.available_start;
    const endDate = item.available_end;
    const query = new URLSearchParams({ start_date: startDate, end_date: endDate });

    try {
      const response = await fetch(
        `${API_BASE_URL}/datasets/${encodeURIComponent(datasetId)}/series?${query}`,
        { method: "GET", headers: { Accept: "application/json" } },
      );
      let body;
      try { body = await response.json(); } catch { body = {}; }
      if (requestId !== priceSeriesRequestId) return;
      if (!response.ok) {
        const detail = explainDetail(body.detail);
        if (response.status === 422 && detail.includes("no available sessions")) {
          clearHistoricalPriceChart("No hay observaciones de cierre en el período seleccionado.");
          return;
        }
        throw new Error(response.status === 404
          ? `La serie histórica del activo no está disponible. ${detail}`.trim()
          : `No se pudo cargar la serie histórica (HTTP ${response.status}). ${detail}`.trim());
      }
      const points = body.points;
      const valid = body.dataset_id === datasetId && body.ticker === item.ticker &&
        typeof body.sha256 === "string" && /^[a-f0-9]{64}$/.test(body.sha256) &&
        Number.isInteger(body.session_count) && Array.isArray(points) && body.session_count === points.length &&
        body.first_date === points[0]?.date && body.last_date === points.at(-1)?.date &&
        points.every((point, index) =>
          point && typeof point.date === "string" && Number.isFinite(point.close) && point.close > 0 &&
          (index === 0 || points[index - 1].date < point.date)
        );
      if (!valid) throw new Error("La respuesta de la serie no coincide con el contrato esperado.");
      if (points.length < 2) {
        clearHistoricalPriceChart("No hay suficientes observaciones para dibujar una línea; se requieren al menos dos sesiones con precio Close.");
        return;
      }
      currentPriceSeries = body;
      historicalPriceCanvas.hidden = false;
      historicalPriceStatus.textContent = `${body.ticker} · ${body.session_count} sesiones · ${body.first_date} → ${body.last_date}`;
      drawHistoricalPriceChart(body);
    } catch (error) {
      if (requestId !== priceSeriesRequestId) return;
      clearHistoricalPriceChart(error instanceof TypeError || error?.name === "TypeError"
        ? "No se pudo conectar con el backend para cargar los precios históricos. Comprueba que FastAPI esté ejecutándose."
        : error.message);
    }
  }

  function drawHistoricalPriceChart(data) {
    const context = historicalPriceCanvas.getContext("2d");
    const rect = historicalPriceCanvas.getBoundingClientRect();
    if (!context || rect.width === 0 || rect.height === 0) return;
    const ratio = Math.max(1, window.devicePixelRatio || 1);
    historicalPriceCanvas.width = Math.round(rect.width * ratio);
    historicalPriceCanvas.height = Math.round(rect.height * ratio);
    context.setTransform(ratio, 0, 0, ratio, 0, 0);

    const width = rect.width;
    const height = rect.height;
    const margin = { top: 12, right: 14, bottom: 27, left: 75 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const points = data.points;
    const values = points.map((point) => point.close);
    let low = Math.min(...values);
    let high = Math.max(...values);
    if (low === high) { low *= 0.99; high *= 1.01; }
    const padding = (high - low) * 0.08;
    low = Math.max(0, low - padding);
    high += padding;
    const xFor = (index) => margin.left + (points.length <= 1 ? 0 : index / (points.length - 1)) * plotWidth;
    const yFor = (value) => margin.top + (high - value) / (high - low) * plotHeight;

    context.clearRect(0, 0, width, height);
    context.font = "10px 'DM Sans', sans-serif";
    context.textBaseline = "middle";
    for (let tick = 0; tick <= 4; tick += 1) {
      const y = margin.top + (plotHeight * tick) / 4;
      const value = high - ((high - low) * tick) / 4;
      context.strokeStyle = "#edf0f4";
      context.lineWidth = 1;
      context.beginPath(); context.moveTo(margin.left, y); context.lineTo(width - margin.right, y); context.stroke();
      context.fillStyle = "#8995a5";
      context.textAlign = "right";
      context.fillText(formatCompactCurrency(value), margin.left - 10, y);
    }
    context.beginPath();
    points.forEach((point, index) => {
      const x = xFor(index);
      const y = yFor(point.close);
      if (index === 0) context.moveTo(x, y); else context.lineTo(x, y);
    });
    context.strokeStyle = "#3378e5";
    context.lineWidth = 2;
    context.lineJoin = "round";
    context.lineCap = "round";
    context.stroke();
    context.fillStyle = "#8995a5";
    context.textAlign = "left";
    context.fillText(points[0].date, margin.left, height - 11);
    context.textAlign = "right";
    context.fillText(points.at(-1).date, width - margin.right, height - 11);
  }

  function validSummary(data) {
    const finite = (value) => typeof value === "number" && Number.isFinite(value);
    const optionalFinite = (value) => value === null || finite(value);
    return data && typeof data.dataset_id === "string" && typeof data.ticker === "string" &&
      typeof data.name === "string" && typeof data.period_note === "string" &&
      typeof data.sha256 === "string" && Number.isInteger(data.session_count) && data.session_count >= 1 &&
      typeof data.first_date === "string" && typeof data.last_date === "string" &&
      [data.initial_close, data.final_close].every(finite) &&
      [data.price_change, data.annualized_volatility, data.maximum_drawdown].every(optionalFinite) &&
      data.unavailable_reasons && typeof data.unavailable_reasons === "object" && !Array.isArray(data.unavailable_reasons) &&
      Number.isInteger(data.dividend_events) && Number.isInteger(data.split_events) &&
      data.price_basis === "Close" && data.includes_distributions === false && data.is_strategy_result === false &&
      typeof data.interpretation === "string";
  }

  async function loadDatasetSummary() {
    const requestId = ++summaryRequestId;
    const datasetId = datasetSelect.value;
    clearSummary();
    const catalogItem = datasetCatalog.get(datasetId);
    if (!catalogItem) {
      summaryStatus.textContent = "Selecciona un dataset del catálogo.";
      return;
    }
    if (!catalogItem.capabilities.descriptive_analysis) {
      summaryStatus.textContent = "Análisis no disponible";
      summaryError.textContent = catalogItem.validation_note || "Este dataset está pendiente de validación.";
      summaryError.hidden = false;
      return;
    }
    summaryStatus.textContent = "Consultando estadísticas del dataset…";
    try {
      const query = new URLSearchParams();
      const requestedStart = document.querySelector("#evaluation-start").value;
      const requestedEnd = document.querySelector("#evaluation-end").value;
      if (requestedStart) query.set("start_date", requestedStart);
      if (requestedEnd) query.set("end_date", requestedEnd);
      const queryString = query.toString();
      const response = await fetch(`${API_BASE_URL}/datasets/${encodeURIComponent(datasetId)}/summary${queryString ? `?${queryString}` : ""}`, {
        method: "GET",
        headers: { Accept: "application/json" },
      });
      let body;
      try { body = await response.json(); } catch { body = {}; }
      if (requestId !== summaryRequestId) return;
      if (!response.ok) {
        const detail = explainDetail(body.detail);
        summaryError.textContent = response.status === 404
          ? `El dataset seleccionado no está disponible. ${detail}`.trim()
          : `No se pudieron cargar las estadísticas históricas (HTTP ${response.status}). ${detail}`.trim();
        summaryError.hidden = false;
        summaryStatus.textContent = "Resumen no disponible";
        return;
      }
      if (!validSummary(body) || body.dataset_id !== datasetId) {
        throw new Error("La respuesta del resumen no coincide con el contrato esperado.");
      }
      document.querySelector("#summary-sessions").textContent = formatNumber.format(body.session_count);
      document.querySelector("#summary-dates").textContent = `${body.first_date} → ${body.last_date}`;
      document.querySelector("#summary-prices").textContent = `${formatCurrency.format(body.initial_close)} → ${formatCurrency.format(body.final_close)}`;
      const displayMetric = (value) => value === null ? "No calculable" : formatPercent.format(value);
      document.querySelector("#summary-change").textContent = displayMetric(body.price_change);
      document.querySelector("#summary-volatility").textContent = displayMetric(body.annualized_volatility);
      document.querySelector("#summary-drawdown").textContent = displayMetric(body.maximum_drawdown);
      document.querySelector("#summary-events").textContent = `${body.dividend_events} · ${body.split_events}`;
      summaryPeriodNote.textContent = body.period_note;
      summaryPeriodNote.hidden = false;
      const unavailable = Object.entries(body.unavailable_reasons);
      if (unavailable.length) {
        summaryUnavailable.textContent = unavailable.map(([metric, reason]) => `${metric}: ${reason}`).join(" ");
        summaryUnavailable.hidden = false;
      }
      summaryValues.hidden = false;
      summaryStatus.textContent = `${body.ticker} · ${body.name} · precio Close`;
    } catch (error) {
      if (requestId !== summaryRequestId) return;
      clearSummary();
      summaryError.textContent = error instanceof TypeError
        ? "No se pudo conectar con el backend para consultar el análisis histórico. Comprueba que FastAPI esté ejecutándose."
        : error.message;
      summaryError.hidden = false;
      summaryStatus.textContent = "Resumen no disponible";
    }
  }

  function clearResults() {
    currentComparison = null;
    results.hidden = true;
    emptyState.hidden = false;
    errorPanel.hidden = true;
    analysisPanel.hidden = true;
    analysisDetails.replaceChildren();
    resultsSourceNote.hidden = true;
    resultsSourceNote.textContent = "";
    warningPanel.hidden = true;
    warningList.replaceChildren();
    tradesBody.replaceChildren();
    noTrades.hidden = true;
    tradeCount.textContent = "0";
    metricNote.hidden = true;
    document.querySelectorAll("[data-metric]").forEach((node) => {
      node.textContent = "—";
      node.removeAttribute("title");
    });
    clearChart();
  }

  function clearChart() {
    const context = chart.getContext("2d");
    if (context) context.clearRect(0, 0, chart.width, chart.height);
    document.querySelector("#chart-start").textContent = "—";
    document.querySelector("#chart-end").textContent = "—";
  }

  function setStatus(state, title, message, tag) {
    statusTitle.textContent = title;
    statusMessage.textContent = message;
    statusTag.textContent = tag;
    statusTag.className = `status-tag${state === "error" ? " is-error" : ""}${state === "success" ? " is-success" : ""}`;
    connectionIndicator.className = `connection-indicator ${state}`;
  }

  function setPending(value) {
    pending = value;
    submitButton.disabled = value;
    submitButton.setAttribute("aria-busy", String(value));
    buttonLabel.innerHTML = value
      ? '<span class="button-spinner" aria-hidden="true"></span>Consultando estrategias…'
      : "Ejecutar comparación";
    if (!value) submitButton.querySelector(".button-arrow").textContent = "→";
    else submitButton.querySelector(".button-arrow").textContent = "";
  }

  function readPayload() {
    const values = new FormData(form);
    const mode = values.get("analysis_mode") || "historical";
    const initialCapital = Number(values.get("initial_capital"));
    const commissionPercent = Number(values.get("transaction_cost_rate"));
    const shortWindow = Number(values.get("short_window"));
    const longWindow = Number(values.get("long_window"));

    if (!Number.isFinite(initialCapital) || initialCapital <= 0) {
      throw new Error("El capital inicial debe ser un número mayor que cero.");
    }
    if (!Number.isFinite(commissionPercent) || commissionPercent < 0 || commissionPercent >= 100) {
      throw new Error("La comisión debe ser un porcentaje entre 0 y menos de 100.");
    }
    if (!Number.isInteger(shortWindow) || !Number.isInteger(longWindow) || shortWindow <= 0 || longWindow <= 0 || shortWindow >= longWindow) {
      throw new Error("Las ventanas SMA deben ser enteros positivos y la ventana corta debe ser menor que la larga.");
    }
    if (mode === "experimental") {
      const sessionCount = Number(values.get("session_count"));
      const scenario = values.get("scenario");
      if (!Number.isInteger(sessionCount) || sessionCount < 2 || sessionCount > 2000) {
        throw new Error("El número de sesiones debe ser un entero entre 2 y 2000.");
      }
      if (!["uptrend", "sideways", "high_volatility"].includes(scenario)) {
        throw new Error("Selecciona uno de los escenarios sintéticos disponibles.");
      }
      return {
        mode,
        body: {
          scenario,
          initial_capital: initialCapital,
          session_count: sessionCount,
          transaction_cost_rate: commissionPercent / 100,
          short_window: shortWindow,
          long_window: longWindow,
        },
      };
    }

    const evaluationStart = values.get("evaluation_start");
    const evaluationEnd = values.get("evaluation_end");
    if (!evaluationStart || !evaluationEnd || evaluationEnd < evaluationStart) {
      throw new Error("Selecciona fechas válidas; la fecha final debe ser igual o posterior a la inicial.");
    }

    return {
      mode,
      body: {
        dataset_id: values.get("dataset_id"),
        initial_capital: initialCapital,
        evaluation_start: evaluationStart,
        evaluation_end: evaluationEnd,
        transaction_cost_rate: commissionPercent / 100,
        short_window: shortWindow,
        long_window: longWindow,
      },
    };
  }

  function updateMode() {
    const experimental = modeSelect.value === "experimental";
    updateSourceIndicator();
    modeIndicatorLabel.textContent = experimental ? "Comparación experimental" : "Análisis histórico";
    document.querySelectorAll("[data-historical-only]").forEach((node) => { node.hidden = experimental; });
    document.querySelectorAll("[data-experimental-only]").forEach((node) => { node.hidden = !experimental; });
    datasetSelect.hidden = false;
    datasetSelect.disabled = !catalogReady;
    historicalSummary.hidden = experimental;
    document.querySelector("#historical-price-section").hidden = experimental;
    if (!experimental && catalogReady) {
      loadDatasetSummary();
      loadHistoricalPriceSeries();
    } else {
      priceSeriesRequestId += 1;
      clearHistoricalPriceChart();
    }
  }

  function showError(status, detail) {
    errorPanel.hidden = false;
    analysisPanel.hidden = true;
    errorTitle.textContent = status === 409
      ? "Simulación bloqueada por eventos corporativos"
      : status === 404
        ? "Dataset no disponible"
        : "No se pudo completar la comparación";

    if (status === 409) {
      errorMessage.textContent = "El dataset contiene dividendos o splits que el motor aún no procesa y reconcilia. No se generaron resultados. " + detail;
    } else if (status === 422) {
      errorMessage.textContent = "Revisa los parámetros, las fechas, el calentamiento SMA y la validez de los datos. " + detail;
    } else if (status === 404) {
      errorMessage.textContent = "El dataset solicitado no está registrado o no se encuentra disponible. " + detail;
    } else {
      errorMessage.textContent = detail || "La API respondió con un error.";
    }
    setStatus("error", "La solicitud fue rechazada", "No se muestran resultados de solicitudes anteriores.", `HTTP ${status}`);
  }

  function showDatasetAnalysis(detail, requestBody) {
    errorPanel.hidden = true;
    analysisPanel.hidden = false;
    analysisTitle.textContent = "Análisis del dataset";
    analysisMessage.textContent = "La comparación no se ejecutó porque el motor encontró eventos corporativos que esta versión todavía no procesa ni reconcilia. Este es un bloqueo financiero controlado, no un resultado ni un fallo inesperado.";
    analysisDetails.replaceChildren();
    const selectedDataset = document.querySelector("#dataset-id").selectedOptions?.[0]?.textContent || requestBody.dataset_id;
    const details = [
      `Dataset solicitado: ${selectedDataset} (${requestBody.dataset_id}).`,
      `Período de evaluación solicitado: ${requestBody.evaluation_start} a ${requestBody.evaluation_end} (fecha final inclusiva).`,
      `Detalle comunicado por la API: ${detail || "eventos corporativos pendientes de reconciliación"}.`,
      "Se muestran datos descriptivos de la solicitud; no se generaron curvas, métricas de rentabilidad ni operaciones.",
    ];
    details.forEach((text) => {
      const item = document.createElement("li");
      item.textContent = text;
      analysisDetails.append(item);
    });
    setStatus("warning", "Comparación bloqueada de forma controlada", "No se ejecutaron estrategias ni se produjeron resultados financieros.", "BLOQUEADA");
  }

  function explainDetail(detail) {
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map((issue) => {
        const where = Array.isArray(issue.loc) ? issue.loc.slice(1).join(" · ") : "";
        return [where, issue.msg].filter(Boolean).join(": ");
      }).join(". ");
    }
    return "";
  }

  function validComparison(data) {
    const finite = (value) => typeof value === "number" && Number.isFinite(value);
    const validStrategy = (strategy) => {
      const metrics = strategy?.metrics;
      const curve = strategy?.equity_curve;
      const executions = strategy?.executions;
      const requiredMetrics = ["cumulative_return", "annualized_return", "annualized_volatility", "maximum_drawdown", "valuation_intervals", "unavailable_reasons"];
      return Array.isArray(curve) && curve.length > 0 && curve.every((point) =>
        typeof point?.date === "string" && finite(point.equity)
      ) && Array.isArray(executions) && executions.every((trade) =>
        typeof trade?.session === "string" && [trade.units, trade.price, trade.notional, trade.fee].every(finite)
      ) && metrics && requiredMetrics.every((key) => Object.hasOwn(metrics, key)) &&
        finite(metrics.cumulative_return) &&
        (metrics.annualized_return === null || finite(metrics.annualized_return)) &&
        (metrics.annualized_volatility === null || finite(metrics.annualized_volatility)) &&
        finite(metrics.maximum_drawdown) && Number.isInteger(metrics.valuation_intervals) &&
        metrics.unavailable_reasons && typeof metrics.unavailable_reasons === "object";
    };

    return data && data.configuration && data.dataset &&
      typeof data.dataset.sha256 === "string" &&
      Array.isArray(data.evaluation_dates) && data.evaluation_dates.length > 0 &&
      data.evaluation_dates.every((value) => typeof value === "string") &&
      validStrategy(data.buy_and_hold) && validStrategy(data.sma_crossover) &&
      Array.isArray(data.warnings);
  }

  async function submitComparison(event) {
    event.preventDefault();
    if (pending) return;
    clearResults();
    formError.hidden = true;

    let requestBody;
    try {
      requestBody = readPayload();
    } catch (error) {
      formError.textContent = error.message;
      formError.hidden = false;
      setStatus("error", "Revisa la configuración", error.message, "VALIDACIÓN");
      return;
    }

    setPending(true);
    const experimental = requestBody.mode === "experimental";
    const payload = requestBody.body;
    setStatus("loading", experimental ? "Ejecutando comparación experimental" : "Ejecutando comparación", "La API está evaluando ambas estrategias con los mismos parámetros.", "PROCESANDO");

    try {
      const response = await fetch(experimental ? EXPERIMENTAL_API_URL : API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(payload),
      });
      let body;
      try {
        body = await response.json();
      } catch {
        body = {};
      }

      if (!response.ok) {
        if (response.status === 409) {
          showDatasetAnalysis(explainDetail(body.detail), payload);
        } else {
          showError(response.status, explainDetail(body.detail));
        }
        return;
      }
      if (!validComparison(body)) {
        showError(502, "La respuesta de la API no coincide con el contrato esperado. No se muestran resultados.");
        return;
      }
      if (experimental && (body.mode !== "experimental" || body.data_origin !== "synthetic" || body.dataset.ticker !== "SYNTHETIC" || typeof body.notice !== "string")) {
        showError(502, "La API no identificó la respuesta como experimental y sintética. No se muestran resultados.");
        return;
      }

      currentComparison = body;
      emptyState.hidden = true;
      results.hidden = false;
      errorPanel.hidden = true;
      resultsSourceNote.hidden = !experimental;
      resultsSourceNote.textContent = experimental
        ? "ETF de referencia visual · datos de la comparación: sintéticos."
        : "";
      renderResults(body, !experimental);
      setStatus("success", experimental ? "Comparación experimental completada" : "Comparación completada", `${body.evaluation_dates.length} sesiones valoradas · ${body.dataset.ticker} · SHA-256 ${body.dataset.sha256.slice(0, 12)}…`, experimental ? "SINTÉTICO" : "COMPLETADO");
    } catch {
      clearResults();
      errorPanel.hidden = false;
      errorTitle.textContent = "No se pudo conectar con el backend";
      errorMessage.textContent = "Comprueba que FastAPI esté ejecutándose en http://127.0.0.1:8000 y que el origen CORS sea http://localhost:5500.";
      setStatus("error", "Backend sin conexión", "No se muestran resultados de solicitudes anteriores.", "SIN CONEXIÓN");
    } finally {
      setPending(false);
    }
  }

  function renderResults(data, showWarnings = true) {
    const pair = {
      buy_and_hold: data.buy_and_hold,
      sma_crossover: data.sma_crossover,
    };
    const metricNames = ["cumulative_return", "annualized_return", "annualized_volatility", "maximum_drawdown"];
    Object.entries(pair).forEach(([strategyName, evaluation]) => {
      const finalEquity = evaluation.equity_curve.at(-1)?.equity;
      document.querySelector(`[data-final="${strategyName}"]`).textContent = Number.isFinite(finalEquity)
        ? formatCurrency.format(finalEquity)
        : "N/C";
    });
    metricNames.forEach((metricName) => {
      Object.entries(pair).forEach(([strategyName, evaluation]) => {
        const value = evaluation.metrics[metricName];
        const node = document.querySelector(`[data-metric="${metricName}"][data-strategy="${strategyName}"]`);
        node.textContent = value === null ? "N/C" : formatPercent.format(value);
        if (value === null) {
          node.title = evaluation.metrics.unavailable_reasons[metricName] || "Métrica no calculable";
        }
      });
    });

    const unavailableCount = Object.values(pair).reduce((sum, evaluation) => sum + Object.keys(evaluation.metrics.unavailable_reasons).length, 0);
    metricNote.hidden = unavailableCount === 0;
    metricNote.textContent = unavailableCount ? "N/C indica una métrica no calculable; consulta el motivo pasando el cursor sobre el valor." : "";
    renderWarnings(showWarnings ? data.warnings : []);
    renderTrades(pair);
    document.querySelector("#chart-start").textContent = data.evaluation_dates[0] || "—";
    document.querySelector("#chart-end").textContent = data.evaluation_dates.at(-1) || "—";
    applyFocus(currentFocus);
    drawChart(data);
  }

  function renderWarnings(warnings) {
    warningList.replaceChildren();
    warningPanel.hidden = !warnings.length;
    warnings.forEach((warning) => {
      const item = document.createElement("li");
      item.textContent = warning;
      warningList.append(item);
    });
  }

  function renderTrades(pair) {
    const trades = Object.entries(pair).flatMap(([strategyName, evaluation]) =>
      evaluation.executions.map((execution) => ({ ...execution, strategyName }))
    ).sort((left, right) => left.session.localeCompare(right.session) || left.strategyName.localeCompare(right.strategyName));

    tradeCount.textContent = String(trades.length);
    noTrades.hidden = trades.length !== 0;
    tradesBody.replaceChildren();
    trades.forEach((trade) => {
      const row = document.createElement("tr");
      const strategyLabel = trade.strategyName === "buy_and_hold" ? "Buy & Hold" : "SMA";
      const cells = [
        { text: trade.session },
        { text: strategyLabel, strategy: trade.strategyName },
        { text: trade.side, side: trade.side },
        { text: formatNumber.format(trade.units), numeric: true },
        { text: formatCurrency.format(trade.price), numeric: true },
        { text: formatCurrency.format(trade.fee), numeric: true },
      ];
      cells.forEach((cell) => {
        const td = document.createElement("td");
        if (cell.numeric) td.className = "numeric";
        if (cell.strategy) {
          const chip = document.createElement("span");
          chip.className = `strategy-chip${cell.strategy === "sma_crossover" ? " sma" : ""}`;
          chip.textContent = cell.text;
          td.append(chip);
        } else if (cell.side) {
          const chip = document.createElement("span");
          chip.className = `side-chip side-${cell.side}`;
          chip.textContent = cell.side === "buy" ? "Compra" : "Venta";
          td.append(chip);
        } else {
          td.textContent = cell.text;
        }
        row.append(td);
      });
      tradesBody.append(row);
    });
  }

  function applyFocus(focus) {
    currentFocus = focus;
    strategyButtons.forEach((button) => {
      const selected = button.dataset.focus === focus;
      button.classList.toggle("is-active", selected);
      button.setAttribute("aria-pressed", String(selected));
    });
    document.querySelectorAll(".metric-card").forEach((card) => {
      card.dataset.focus = focus;
    });
    if (currentComparison) drawChart(currentComparison);
  }

  function drawChart(data) {
    const context = chart.getContext("2d");
    const rect = chart.getBoundingClientRect();
    if (!context || rect.width === 0 || rect.height === 0) return;
    const ratio = Math.max(1, window.devicePixelRatio || 1);
    chart.width = Math.round(rect.width * ratio);
    chart.height = Math.round(rect.height * ratio);
    context.setTransform(ratio, 0, 0, ratio, 0, 0);

    const width = rect.width;
    const height = rect.height;
    const margin = { top: 12, right: 14, bottom: 27, left: 75 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const series = [
      { key: "buy_and_hold", color: "#3378e5", values: data.buy_and_hold.equity_curve },
      { key: "sma_crossover", color: "#16a68a", values: data.sma_crossover.equity_curve },
    ];
    const values = series.flatMap((line) => line.values.map((point) => point.equity));
    if (!values.length || !values.every(Number.isFinite)) return;
    let low = Math.min(...values);
    let high = Math.max(...values);
    if (low === high) { low *= 0.99; high *= 1.01; }
    const padding = (high - low) * 0.08;
    low = Math.max(0, low - padding);
    high += padding;
    const xFor = (index, count) => margin.left + (count <= 1 ? 0 : index / (count - 1)) * plotWidth;
    const yFor = (value) => margin.top + (high - value) / (high - low) * plotHeight;

    context.clearRect(0, 0, width, height);
    context.font = "10px 'DM Sans', sans-serif";
    context.textBaseline = "middle";
    for (let tick = 0; tick <= 4; tick += 1) {
      const y = margin.top + (plotHeight * tick) / 4;
      const value = high - ((high - low) * tick) / 4;
      context.strokeStyle = "#edf0f4";
      context.lineWidth = 1;
      context.beginPath(); context.moveTo(margin.left, y); context.lineTo(width - margin.right, y); context.stroke();
      context.fillStyle = "#8995a5";
      context.textAlign = "right";
      context.fillText(formatCompactCurrency(value), margin.left - 10, y);
    }

    series.forEach((line) => {
      if (currentFocus !== "both" && currentFocus !== line.key) return;
      const points = line.values;
      if (!points.length) return;
      context.beginPath();
      points.forEach((point, index) => {
        const x = xFor(index, points.length);
        const y = yFor(point.equity);
        if (index === 0) context.moveTo(x, y); else context.lineTo(x, y);
      });
      context.strokeStyle = line.color;
      context.lineWidth = currentFocus === "both" ? 2 : 2.7;
      context.lineJoin = "round";
      context.lineCap = "round";
      context.stroke();
    });

    const dates = data.evaluation_dates;
    const labels = [0, Math.floor((dates.length - 1) / 2), dates.length - 1].filter((value, index, array) => array.indexOf(value) === index);
    labels.forEach((index) => {
      const x = xFor(index, dates.length);
      context.fillStyle = "#8995a5";
      context.textAlign = index === 0 ? "left" : index === dates.length - 1 ? "right" : "center";
      context.fillText(dates[index] || "", x, height - 11);
    });
  }

  function formatCompactCurrency(value) {
    const absolute = Math.abs(value);
    if (absolute >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
    if (absolute >= 10_000) return `$${(value / 1_000).toFixed(0)}k`;
    return `$${formatNumber.format(value)}`;
  }

  form.addEventListener("submit", submitComparison);
  modeSelect.addEventListener("change", () => {
    clearResults();
    formError.hidden = true;
    updateMode();
    setStatus("idle", "Listo para comparar", "Configura los parámetros del modo seleccionado y ejecuta la comparación.", "EN ESPERA");
  });
  scenarioSelect.addEventListener("change", updateSourceIndicator);
  datasetSelect.addEventListener("change", () => {
    clearResults();
    updateDatasetDetails();
    updateSourceIndicator();
    if (modeSelect.value !== "experimental") {
      loadDatasetSummary();
      loadHistoricalPriceSeries();
    }
  });
  historicalPricePeriod.addEventListener("change", () => {
    if (modeSelect.value !== "experimental") loadHistoricalPriceSeries();
  });
  ["#evaluation-start", "#evaluation-end"].forEach((selector) => {
    document.querySelector(selector).addEventListener("change", () => {
      clearResults();
      if (modeSelect.value !== "experimental") loadDatasetSummary();
    });
  });
  strategyButtons.forEach((button) => {
    button.addEventListener("click", () => applyFocus(button.dataset.focus));
  });
  window.addEventListener("resize", () => {
    if (currentComparison) drawChart(currentComparison);
    if (currentPriceSeries) drawHistoricalPriceChart(currentPriceSeries);
  });
  updateMode();
  loadDatasetCatalog();
})();
