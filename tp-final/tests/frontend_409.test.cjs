const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

class Element {
  constructor(text = "") {
    this.textContent = text;
    this.innerHTML = "";
    this.hidden = false;
    this.disabled = false;
    this.dataset = {};
    this.attributes = {};
    this.children = [];
    this.listeners = {};
    this.className = "";
    this.classList = { toggle() {} };
    this.selectedOptions = [{ textContent: "SPY · 2020–2024" }];
    this.width = 400;
    this.height = 250;
    this.context = {
      clearRect() { this.wasCleared = true; }, setTransform() {}, beginPath() {}, moveTo() {},
      lineTo() {}, stroke() {}, fillText() {}, wasCleared: false,
    };
  }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  setAttribute(name, value) { this.attributes[name] = value; }
  removeAttribute(name) { delete this.attributes[name]; }
  querySelector(selector) {
    this.childrenBySelector ??= {};
    this.childrenBySelector[selector] ??= new Element();
    return this.childrenBySelector[selector];
  }
  replaceChildren(...children) { this.children = children; }
  append(child) { this.children.push(child); }
  getContext() { return this.context; }
  getBoundingClientRect() { return { width: 400, height: 250 }; }
}

function makeHarness() {
  const ids = [
    "#comparison-form", "#run-button", "#form-error", "#status-title", "#status-message",
    "#status-tag", "#connection-indicator", "#error-panel", "#error-title", "#error-message",
    "#dataset-analysis", "#analysis-title", "#analysis-message", "#analysis-details",
    "#warning-panel", "#warning-list", "#empty-state", "#results", "#equity-chart", "#results-source-note",
    "#trades-body", "#no-trades", "#trade-count", "#metric-note", "#chart-start",
    "#chart-end", "#dataset-id", "#dataset-select-label", "#analysis-mode", "#historical-summary",
    "#synthetic-scenario", "#session-count", "#dataset-validation-status", "#dataset-available-period",
    "#dataset-capabilities", "#dataset-validation-note", "#dataset-instrument", "#dataset-exposure",
    "#source-indicator-main", "#source-indicator-detail", "#source-indicator-scenario",
    "#mode-indicator-label",
    "#historical-price-section", "#historical-price-chart", "#historical-price-period", "#historical-price-status",
    "#historical-summary-title", "#summary-period-note", "#summary-unavailable",
    "#evaluation-start", "#evaluation-end",
    "#summary-values", "#summary-status", "#summary-error",
    "#summary-sessions", "#summary-dates", "#summary-prices", "#summary-change",
    "#summary-volatility", "#summary-drawdown", "#summary-events",
  ];
  const elements = Object.fromEntries(ids.map((id) => [id, new Element()]));
  const metrics = [new Element("resultado anterior A"), new Element("resultado anterior B")];
  const buttons = ["both", "buy_and_hold", "sma_crossover"].map((focus) => {
    const button = new Element();
    button.dataset.focus = focus;
    return button;
  });
  const metricCards = [new Element(), new Element()];
  const historicalOnly = [new Element(), new Element()];
  const experimentalOnly = [new Element()];
  const fetchCalls = [];
  let summaryFails = false;
  let seriesFails = false;
  let seriesConnectionFails = false;
  let seriesSinglePoint = false;
  elements["#dataset-id"].value = "spy-2020-2025";
  elements["#evaluation-start"].value = "2020-03-18";
  elements["#evaluation-end"].value = "2024-12-31";
  elements["#analysis-mode"].value = "historical";
  elements["#synthetic-scenario"].value = "sideways";
  elements["#session-count"].value = "60";
  const formValues = {
    dataset_id: "spy-2020-2025",
    initial_capital: "1000000",
    evaluation_start: "2020-03-18",
    evaluation_end: "2024-12-31",
    transaction_cost_rate: "0.1",
    short_window: "20",
    long_window: "50",
  };
  const document = {
    querySelector(selector) { return elements[selector] || new Element(); },
    querySelectorAll(selector) {
      if (selector === "[data-metric]") return metrics;
      if (selector === "[data-focus]") return buttons;
      if (selector === ".metric-card") return metricCards;
      if (selector === "[data-historical-only]") return historicalOnly;
      if (selector === "[data-experimental-only]") return experimentalOnly;
      return [];
    },
    createElement() { return new Element(); },
  };
  class FormDataMock {
    get(key) {
      if (key === "analysis_mode") return elements["#analysis-mode"].value;
      if (key === "scenario") return elements["#synthetic-scenario"].value;
      if (key === "session_count") return elements["#session-count"].value;
      if (key === "dataset_id") return elements["#dataset-id"].value;
      return formValues[key];
    }
  }
  const window = { devicePixelRatio: 1, addEventListener() {} };
  const fetch = async (...args) => {
    fetchCalls.push(args);
    if ((args[1]?.method || "GET") === "GET") {
      if (args[0] === "http://127.0.0.1:8000/api/v1/datasets") {
        const records = [
          ["spy-2020-2025", "SPY", "SPDR S&P 500 ETF Trust", "descriptive_only", true, false, "2020-01-02", "2024-12-31", "Análisis descriptivo disponible; simulación histórica bloqueada."],
          ["qqq-2020-2025", "QQQ", "Invesco QQQ Trust", "descriptive_only", true, false, "2020-01-02", "2024-12-31", "Análisis descriptivo disponible; simulación histórica bloqueada hasta reconciliar eventos corporativos de QQQ."],
          ["iwm-pending", "IWM", "iShares Russell 2000 ETF", "pending_validation", false, false, null, null, "No hay datos históricos validados registrados para IWM."],
          ["tlt-pending", "TLT", "iShares 20+ Year Treasury Bond ETF", "pending_validation", false, false, null, null, "No hay datos históricos validados registrados para TLT."],
          ["gld-pending", "GLD", "SPDR Gold Shares", "pending_validation", false, false, null, null, "No hay datos históricos validados registrados para GLD."],
        ];
        return {
          ok: true, status: 200,
          async json() {
            return { datasets: records.map(([dataset_id, ticker, name, validation_status, descriptive_analysis, historical_simulation, available_start, available_end, validation_note]) => ({
              dataset_id, ticker, name,
              asset_type: ticker === "TLT" ? "fixed_income_etf" : ticker === "GLD" ? "commodity_etf" : "equity_etf",
              exposure: ({
                SPY: "Acciones estadounidenses de gran capitalización; índice S&P 500.",
                QQQ: "Acciones de grandes empresas no financieras del Nasdaq-100.",
                IWM: "Acciones estadounidenses de pequeña capitalización del Russell 2000.",
                TLT: "Bonos del Tesoro de Estados Unidos con vencimientos superiores a 20 años.",
                GLD: "Exposición al precio del oro físico, menos gastos del fondo.",
              })[ticker], currency: "USD",
              validation_status, capabilities: { descriptive_analysis, historical_simulation },
              available_start, available_end,
              sha256: ["spy-2020-2025", "qqq-2020-2025"].includes(dataset_id) ? "a".repeat(64) : null,
              validation_note,
            })) };
          },
        };
      }
      if (args[0].includes("/series?")) {
        if (seriesConnectionFails) throw new TypeError("Failed to fetch");
        if (seriesFails) {
          return { ok: false, status: 503, async json() { return { detail: "registered local dataset unavailable" }; } };
        }
        const isQqq = args[0].includes("qqq-2020-2025");
        const dataset_id = isQqq ? "qqq-2020-2025" : "spy-2020-2025";
        const ticker = isQqq ? "QQQ" : "SPY";
        const points = [
          { date: "2024-12-27", close: 600 },
          { date: "2024-12-30", close: 605 },
          { date: "2024-12-31", close: 603 },
        ];
        const returnedPoints = seriesSinglePoint ? points.slice(0, 1) : points;
        return {
          ok: true, status: 200,
          async json() {
            return {
              dataset_id, ticker, sha256: "d".repeat(64),
              requested_start: "2024-09-30", requested_end: "2024-12-31",
              first_date: returnedPoints[0].date, last_date: returnedPoints.at(-1).date,
              session_count: returnedPoints.length,
              points: returnedPoints,
            };
          },
        };
      }
      if (summaryFails) {
        return {
          ok: false,
          status: 404,
          async json() { return { detail: "dataset_id is not registered" }; },
        };
      }
      if (args[0].includes("/datasets/qqq-2020-2025/summary")) {
        return {
          ok: true,
          status: 200,
          async json() {
            return {
              dataset_id: "qqq-2020-2025", ticker: "QQQ", name: "Invesco QQQ Trust",
              sha256: "c".repeat(64), session_count: 4,
              first_date: "2024-01-02", last_date: "2024-01-05",
              requested_start: "2020-03-18", requested_end: "2024-12-31",
              period_note: "Fechas solicitadas inclusivas; período efectivo ajustado a sesiones disponibles.",
              initial_close: 400, final_close: 500, price_change: 0.25,
              annualized_volatility: 0.32, maximum_drawdown: -0.1,
              unavailable_reasons: {}, dividend_events: 1, split_events: 0,
              price_basis: "Close", includes_distributions: false, is_strategy_result: false,
              interpretation: "Estadísticas descriptivas de Close, sin distribuciones.",
            };
          },
        };
      }
      return {
        ok: true,
        status: 200,
        async json() {
          return {
            dataset_id: "spy-2020-2025", ticker: "SPY", name: "SPDR S&P 500 ETF Trust", sha256: "a".repeat(64),
            session_count: 1258, first_date: "2020-01-02", last_date: "2024-12-31",
            requested_start: "2020-03-18", requested_end: "2024-12-31",
            period_note: "Fechas solicitadas inclusivas; período efectivo ajustado a sesiones disponibles.",
            initial_close: 320, final_close: 590, price_change: 0.84,
            annualized_volatility: 0.2, maximum_drawdown: -0.3,
            unavailable_reasons: {},
            dividend_events: 20, split_events: 0, price_basis: "Close",
            includes_distributions: false, is_strategy_result: false,
            interpretation: "Estadística descriptiva del precio Close.",
          };
        },
      };
    }
    if (args[0] === "http://127.0.0.1:8000/api/v1/experimental/comparisons") {
      const curve = (startingEquity) => [0, 1, 2].map((offset) => ({
        date: ["2025-01-02", "2025-01-03", "2025-01-06"][offset],
        equity: startingEquity + offset * 10,
      }));
      const strategy = () => ({
        equity_curve: curve(1000),
        executions: [{ session: "2025-01-02", side: "buy", units: 2, price: 100, notional: 200, fee: 0.2 }],
        final_cash: 799.8, final_units: 2,
        metrics: {
          cumulative_return: 0.02, annualized_return: 0.3, annualized_volatility: 0.1,
          maximum_drawdown: -0.01, valuation_intervals: 3, unavailable_reasons: {},
        },
      });
      return {
        ok: true,
        status: 200,
        async json() {
          return {
            mode: "experimental", data_origin: "synthetic", scenario: "sideways",
            notice: "Resultados experimentales con datos sintéticos. No representan rentabilidades históricas reales ni constituyen una recomendación de inversión.",
            configuration: {}, dataset: { ticker: "SYNTHETIC", sha256: "b".repeat(64) },
            evaluation_dates: ["2025-01-02", "2025-01-03", "2025-01-06"],
            buy_and_hold: strategy(), sma_crossover: strategy(), warnings: [],
          };
        },
      };
    }
    return {
      ok: false,
      status: 409,
      async json() { return { detail: "Dividends contiene eventos no procesados." }; },
    };
  };

  elements["#results"].hidden = false;
  elements["#empty-state"].hidden = true;
  elements["#warning-panel"].hidden = false;
  elements["#trades-body"].children = [new Element("operación anterior")];
  const app = fs.readFileSync(path.join(__dirname, "..", "frontend", "app.js"), "utf8");
  vm.runInNewContext(app, { document, window, FormData: FormDataMock, fetch, URLSearchParams, Intl, Number, Math, String, Object, Array });
  return {
    elements, metrics, fetchCalls, form: elements["#comparison-form"],
    historicalOnly, experimentalOnly,
    setSummaryFails(value) { summaryFails = value; },
    setSeriesFails(value) { seriesFails = value; },
    setSeriesConnectionFails(value) { seriesConnectionFails = value; },
    setSeriesSinglePoint(value) { seriesSinglePoint = value; },
  };
}

test("HTTP 409 shows dataset analysis and clears all previous financial results", async () => {
  const { elements, metrics, fetchCalls, form } = makeHarness();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(elements["#summary-values"].hidden, false);
  assert.equal(elements["#summary-sessions"].textContent, "1.258,00");
  await form.listeners.submit({ preventDefault() {} });

  const postCall = fetchCalls.find((call) => call[1]?.method === "POST");
  assert.equal(postCall[0], "http://127.0.0.1:8000/api/v1/comparisons");
  assert.equal(elements["#summary-values"].hidden, false);
  assert.equal(elements["#summary-events"].textContent, "20 · 0");
  assert.equal(elements["#dataset-analysis"].hidden, false);
  assert.equal(elements["#analysis-title"].textContent, "Análisis del dataset");
  assert.match(elements["#analysis-message"].textContent, /no se ejecutó/i);
  const details = elements["#analysis-details"].children.map((item) => item.textContent).join(" ");
  assert.match(details, /spy-2020-2025/);
  assert.match(details, /2020-03-18 a 2024-12-31/);
  assert.match(details, /Dividends contiene eventos no procesados/);
  assert.match(details, /no se generaron curvas, métricas de rentabilidad ni operaciones/i);

  assert.equal(elements["#results"].hidden, true);
  assert.equal(elements["#empty-state"].hidden, false);
  assert.equal(elements["#error-panel"].hidden, true);
  assert.equal(elements["#warning-panel"].hidden, true);
  assert.deepEqual(elements["#trades-body"].children, []);
  assert.deepEqual(metrics.map((metric) => metric.textContent), ["—", "—"]);
  assert.equal(elements["#status-tag"].textContent, "BLOQUEADA");
  assert.match(elements["#status-title"].textContent, /bloqueada de forma controlada/i);
  assert.equal(elements["#equity-chart"].context.wasCleared, true);
});

test("a failed dataset summary clears values from the previously selected dataset", async () => {
  const { elements, setSummaryFails } = makeHarness();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(elements["#summary-values"].hidden, false);

  setSummaryFails(true);
  elements["#dataset-id"].value = "spy-2020-2025";
  await elements["#dataset-id"].listeners.change();
  await new Promise((resolve) => setImmediate(resolve));

  assert.equal(elements["#summary-values"].hidden, true);
  assert.equal(elements["#summary-sessions"].textContent, "—");
  assert.equal(elements["#summary-error"].hidden, false);
  assert.match(elements["#summary-error"].textContent, /no está disponible/i);
});

test("dataset selector is populated from the API catalog and explains pending assets", async () => {
  const { elements, fetchCalls } = makeHarness();
  await new Promise((resolve) => setImmediate(resolve));

  const catalogCall = fetchCalls.find((call) => call[0] === "http://127.0.0.1:8000/api/v1/datasets");
  assert.ok(catalogCall);
  assert.equal(elements["#dataset-id"].children.length, 5);
  assert.match(elements["#dataset-id"].children[0].textContent, /SPY.*SPDR S&P 500 ETF Trust/);
  assert.equal(elements["#dataset-instrument"].textContent, "SPY · SPDR S&P 500 ETF Trust");
  assert.match(elements["#dataset-exposure"].textContent, /S&P 500/);
  assert.match(elements["#dataset-validation-note"].textContent, /análisis descriptivo disponible; simulación histórica bloqueada/i);
  assert.equal(elements["#dataset-available-period"].textContent, "2020-01-02 → 2024-12-31");
  elements["#dataset-id"].value = "qqq-2020-2025";
  const priorCalls = fetchCalls.length;
  await elements["#dataset-id"].listeners.change();
  await new Promise((resolve) => setImmediate(resolve));
  assert.match(elements["#dataset-validation-status"].textContent, /Apto para análisis descriptivo/);
  assert.equal(elements["#dataset-available-period"].textContent, "2020-01-02 → 2024-12-31");
  assert.equal(elements["#dataset-capabilities"].textContent, "análisis descriptivo");
  assert.match(elements["#dataset-instrument"].textContent, /QQQ · Invesco QQQ Trust/);
  assert.match(elements["#dataset-exposure"].textContent, /Nasdaq-100/);
  assert.match(elements["#dataset-validation-note"].textContent, /simulación histórica bloqueada/i);
  assert.equal(elements["#historical-summary-title"].textContent, "Análisis descriptivo de QQQ");
  assert.equal(elements["#summary-values"].hidden, false);
  assert.equal(elements["#summary-prices"].textContent, "US$ 400,00 → US$ 500,00");
  assert.match(elements["#summary-status"].textContent, /QQQ · Invesco QQQ Trust/);
  assert.match(elements["#summary-period-note"].textContent, /período efectivo ajustado/i);
  const qqqSummaryCall = fetchCalls.find((call) => call[0].includes("/datasets/qqq-2020-2025/summary"));
  assert.match(qqqSummaryCall[0], /start_date=2020-03-18/);
  assert.match(qqqSummaryCall[0], /end_date=2024-12-31/);
  assert.equal(elements["#results"].hidden, true);
  const afterQqqSummary = fetchCalls.length;
  for (const [datasetId, ticker, exposure] of [
    ["iwm-pending", "IWM", /Russell 2000/],
    ["tlt-pending", "TLT", /Bonos del Tesoro/],
    ["gld-pending", "GLD", /oro físico/],
  ]) {
    elements["#dataset-id"].value = datasetId;
    await elements["#dataset-id"].listeners.change();
    assert.match(elements["#dataset-instrument"].textContent, new RegExp(`${ticker} ·`));
    assert.match(elements["#dataset-exposure"].textContent, exposure);
    assert.equal(elements["#dataset-available-period"].textContent, "Aún no disponible");
    assert.match(elements["#dataset-validation-note"].textContent, new RegExp(`para ${ticker}`));
  }
  assert.equal(fetchCalls.length, afterQqqSummary);
});

test("experimental mode keeps ETF visible as reference and uses only synthetic scenario data", async () => {
  const { elements, fetchCalls, form, historicalOnly, experimentalOnly } = makeHarness();
  elements["#analysis-mode"].value = "experimental";
  await elements["#analysis-mode"].listeners.change();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(elements["#dataset-id"].hidden, false);
  assert.equal(elements["#dataset-id"].disabled, false);
  assert.equal(elements["#dataset-select-label"].textContent, "ETF de referencia");
  assert.equal(elements["#source-indicator-main"].textContent, "ETF de referencia · SPY");
  assert.equal(elements["#source-indicator-detail"].textContent, "Datos sintéticos");
  assert.equal(elements["#source-indicator-scenario"].textContent, "Mercado lateral");
  assert.equal(elements["#mode-indicator-label"].textContent, "Comparación experimental");
  assert.equal(historicalOnly.every((node) => node.hidden), true);
  assert.equal(experimentalOnly.every((node) => !node.hidden), true);

  elements["#synthetic-scenario"].value = "high_volatility";
  elements["#synthetic-scenario"].listeners.change();
  assert.equal(elements["#source-indicator-detail"].textContent, "Datos sintéticos");
  assert.equal(elements["#source-indicator-scenario"].textContent, "Alta volatilidad");
  elements["#synthetic-scenario"].value = "sideways";
  elements["#synthetic-scenario"].listeners.change();

  elements["#dataset-id"].value = "qqq-2020-2025";
  await elements["#dataset-id"].listeners.change();
  assert.equal(elements["#dataset-id"].hidden, false);
  assert.equal(elements["#source-indicator-main"].textContent, "ETF de referencia · QQQ");
  assert.equal(elements["#source-indicator-detail"].textContent, "Datos sintéticos");
  assert.equal(elements["#source-indicator-scenario"].textContent, "Mercado lateral");

  await form.listeners.submit({ preventDefault() {} });

  const postCall = fetchCalls.find((call) => call[1]?.method === "POST");
  assert.equal(postCall[0], "http://127.0.0.1:8000/api/v1/experimental/comparisons");
  assert.deepEqual(JSON.parse(postCall[1].body), {
    scenario: "sideways", initial_capital: 1000000, session_count: 60,
    transaction_cost_rate: 0.001, short_window: 20, long_window: 50,
  });
  assert.equal(elements["#results"].hidden, false);
  assert.equal(elements["#results-source-note"].hidden, false);
  assert.match(elements["#results-source-note"].textContent, /referencia visual.*sintéticos/i);
  assert.equal(elements["#warning-panel"].hidden, true);
  assert.equal(elements["#historical-summary"].hidden, true);
});

test("historical source indicator tracks the selected ETF and mode", async () => {
  const { elements, historicalOnly, experimentalOnly } = makeHarness();
  await new Promise((resolve) => setImmediate(resolve));
  await elements["#analysis-mode"].listeners.change();
  assert.equal(elements["#source-indicator-main"].textContent, "SPY");
  assert.equal(elements["#source-indicator-detail"].textContent, "Datos históricos locales");
  assert.equal(elements["#mode-indicator-label"].textContent, "Análisis histórico");
  assert.equal(elements["#dataset-id"].hidden, false);
  assert.equal(elements["#dataset-select-label"].textContent, "ETF");
  assert.equal(historicalOnly.every((node) => !node.hidden), true);
  assert.equal(experimentalOnly.every((node) => node.hidden), true);
  elements["#dataset-id"].value = "qqq-2020-2025";
  await elements["#dataset-id"].listeners.change();
  assert.equal(elements["#source-indicator-main"].textContent, "QQQ");
  assert.equal(elements["#source-indicator-detail"].textContent, "Datos históricos locales");
  assert.equal(elements["#source-indicator-scenario"].hidden, true);
});

test("historical Close chart uses selected ETF and available-range period options", async () => {
  const { elements, fetchCalls } = makeHarness();
  await new Promise((resolve) => setImmediate(resolve));
  const initialCall = fetchCalls.find((call) => call[0].includes("/datasets/spy-2020-2025/series"));
  assert.match(initialCall[0], /start_date=2020-01-02/);
  assert.match(initialCall[0], /end_date=2024-12-31/);
  assert.equal(elements["#historical-price-chart"].hidden, false);
  assert.match(elements["#historical-price-status"].textContent, /SPY · 3 sesiones/);

  elements["#dataset-id"].value = "qqq-2020-2025";
  await elements["#dataset-id"].listeners.change();
  await new Promise((resolve) => setImmediate(resolve));
  assert.match(elements["#historical-price-status"].textContent, /^QQQ ·/);

  elements["#historical-price-period"].value = "3m";
  elements["#historical-price-period"].listeners.change();
  await new Promise((resolve) => setImmediate(resolve));
  const recentCall = fetchCalls.filter((call) => call[0].includes("/datasets/qqq-2020-2025/series")).at(-1);
  assert.match(recentCall[0], /start_date=2024-09-30/);
  assert.match(recentCall[0], /end_date=2024-12-31/);
  assert.equal(elements["#historical-price-chart"].hidden, false);
});

test("historical Close chart clears prior points on errors and insufficient observations", async () => {
  const { elements, setSeriesFails, setSeriesSinglePoint } = makeHarness();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(elements["#historical-price-chart"].hidden, false);

  setSeriesFails(true);
  elements["#historical-price-period"].value = "6m";
  elements["#historical-price-period"].listeners.change();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(elements["#historical-price-chart"].hidden, true);
  assert.match(elements["#historical-price-status"].textContent, /HTTP 503/);
  assert.equal(elements["#historical-price-chart"].context.wasCleared, true);

  setSeriesFails(false);
  setSeriesSinglePoint(true);
  elements["#historical-price-period"].value = "1y";
  elements["#historical-price-period"].listeners.change();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(elements["#historical-price-chart"].hidden, true);
  assert.match(elements["#historical-price-status"].textContent, /al menos dos sesiones/i);
});

test("historical Close chart reports a backend connection failure without stale data", async () => {
  const { elements, setSeriesConnectionFails } = makeHarness();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(elements["#historical-price-chart"].hidden, false);

  setSeriesConnectionFails(true);
  elements["#historical-price-period"].value = "1y";
  elements["#historical-price-period"].listeners.change();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(elements["#historical-price-chart"].hidden, true);
  assert.match(elements["#historical-price-status"].textContent, /comprueba que FastAPI/i);
});
