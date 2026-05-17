/**
 * PV Profitability Card
 * Lovelace Custom Card für Home Assistant
 * Zeigt Amortisationskurve und Kennzahlen der PV-Anlage(n).
 */

class PVProfitabilityCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  setConfig(config) {
    if (!config.timeline_entity) {
      throw new Error("timeline_entity muss konfiguriert sein");
    }
    this._config = config;
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _render() {
    const hass = this._hass;
    const cfg = this._config;

    const timelineState = hass.states[cfg.timeline_entity];
    const investmentState = hass.states[cfg.investment_entity || "sensor.pv_gesamtinvestition"];
    const revenueState = hass.states[cfg.revenue_entity || "sensor.pv_gesamteinnahmen"];
    const balanceState = hass.states[cfg.balance_entity || "sensor.pv_netto_saldo"];
    const pctState = hass.states[cfg.percent_entity || "sensor.pv_amortisation"];
    const yearState = hass.states[cfg.year_entity || "sensor.pv_amortisationsjahr"];

    const timeline = timelineState?.attributes?.timeline || [];
    const investment = parseFloat(investmentState?.state || 0);
    const revenue = parseFloat(revenueState?.state || 0);
    const balance = parseFloat(balanceState?.state || 0);
    const pct = parseFloat(pctState?.state || 0);
    const amorYear = yearState?.state || "–";

    // Chart-Dimensionen
    const W = 600, H = 220, PAD = { top: 20, right: 20, bottom: 40, left: 70 };
    const chartW = W - PAD.left - PAD.right;
    const chartH = H - PAD.top - PAD.bottom;

    // Daten aufbereiten
    const actual = timeline.filter(d => !d.forecast);
    const forecast = timeline.filter(d => d.forecast);

    const allValues = timeline.map(d => d.cumulative_revenue).concat([investment]);
    const minY = Math.min(0, ...timeline.map(d => d.net_balance));
    const maxY = Math.max(...allValues) * 1.05;
    const years = timeline.map(d => d.year);
    const minX = years.length ? Math.min(...years) : 2020;
    const maxX = years.length ? Math.max(...years) : 2030;

    const xScale = (year) =>
      PAD.left + ((year - minX) / Math.max(1, maxX - minX)) * chartW;
    const yScale = (val) =>
      PAD.top + chartH - ((val - minY) / Math.max(1, maxY - minY)) * chartH;

    // Pfade bauen
    const linePath = (data, key) =>
      data
        .map((d, i) => `${i === 0 ? "M" : "L"}${xScale(d.year)},${yScale(d[key])}`)
        .join(" ");

    const forecastPath = forecast.length && actual.length
      ? `M${xScale(actual[actual.length - 1].year)},${yScale(actual[actual.length - 1].cumulative_revenue)} ` +
        forecast.map(d => `L${xScale(d.year)},${yScale(d.cumulative_revenue)}`).join(" ")
      : "";

    // Y-Achse Ticks
    const yTicks = 5;
    const yTickValues = Array.from({ length: yTicks + 1 }, (_, i) =>
      minY + ((maxY - minY) / yTicks) * i
    );

    // X-Achse Ticks (nur jedes 2. Jahr wenn viele Datenpunkte)
    const xTickStep = years.length > 10 ? 2 : 1;
    const xTickValues = years.filter((_, i) => i % xTickStep === 0);

    // Investitions-Linie (horizontal)
    const investY = yScale(investment);

    // Amortisationspunkt markieren
    let amorPoint = null;
    for (let i = 1; i < timeline.length; i++) {
      if (
        timeline[i - 1].cumulative_revenue < investment &&
        timeline[i].cumulative_revenue >= investment
      ) {
        amorPoint = timeline[i];
        break;
      }
    }

    const balanceColor = balance >= 0 ? "#4caf50" : "#f44336";
    const pctColor = pct >= 100 ? "#4caf50" : pct >= 50 ? "#ff9800" : "#2196f3";

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: var(--primary-font-family, Roboto, sans-serif);
          color: var(--primary-text-color);
        }
        ha-card {
          padding: 16px;
          background: var(--ha-card-background, var(--card-background-color));
          border-radius: var(--ha-card-border-radius, 12px);
          box-shadow: var(--ha-card-box-shadow, 0 2px 8px rgba(0,0,0,.15));
        }
        .title {
          font-size: 1.1em;
          font-weight: 600;
          margin-bottom: 14px;
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .kpi-row {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
          gap: 10px;
          margin-bottom: 16px;
        }
        .kpi {
          background: var(--secondary-background-color, rgba(0,0,0,.05));
          border-radius: 8px;
          padding: 10px 12px;
          text-align: center;
        }
        .kpi-value {
          font-size: 1.3em;
          font-weight: 700;
          margin-bottom: 2px;
        }
        .kpi-label {
          font-size: 0.72em;
          opacity: 0.7;
          text-transform: uppercase;
          letter-spacing: .04em;
        }
        .progress-wrap {
          margin-bottom: 16px;
        }
        .progress-label {
          display: flex;
          justify-content: space-between;
          font-size: .82em;
          margin-bottom: 4px;
        }
        .progress-bar-bg {
          background: var(--secondary-background-color, rgba(0,0,0,.08));
          border-radius: 99px;
          height: 10px;
          overflow: hidden;
        }
        .progress-bar {
          height: 100%;
          border-radius: 99px;
          transition: width .4s ease;
        }
        .chart-wrap {
          width: 100%;
          overflow-x: auto;
        }
        svg text {
          fill: var(--primary-text-color);
        }
        .legend {
          display: flex;
          gap: 16px;
          font-size: .78em;
          margin-top: 8px;
          flex-wrap: wrap;
        }
        .legend-item {
          display: flex;
          align-items: center;
          gap: 5px;
        }
        .legend-line {
          width: 22px;
          height: 3px;
          border-radius: 2px;
        }
        .no-data {
          text-align: center;
          opacity: .5;
          padding: 32px 0;
          font-size: .9em;
        }
      </style>

      <ha-card>
        <div class="title">
          ☀️ PV Rentabilität
        </div>

        <div class="kpi-row">
          <div class="kpi">
            <div class="kpi-value" style="color:#f44336">${this._fmt(investment)} €</div>
            <div class="kpi-label">Investition</div>
          </div>
          <div class="kpi">
            <div class="kpi-value" style="color:#4caf50">${this._fmt(revenue)} €</div>
            <div class="kpi-label">Einnahmen</div>
          </div>
          <div class="kpi">
            <div class="kpi-value" style="color:${balanceColor}">${balance >= 0 ? "+" : ""}${this._fmt(balance)} €</div>
            <div class="kpi-label">Netto-Saldo</div>
          </div>
          <div class="kpi">
            <div class="kpi-value">${amorYear}</div>
            <div class="kpi-label">Amortisation</div>
          </div>
        </div>

        <div class="progress-wrap">
          <div class="progress-label">
            <span>Amortisationsfortschritt</span>
            <span style="color:${pctColor};font-weight:600">${pct.toFixed(1)} %</span>
          </div>
          <div class="progress-bar-bg">
            <div class="progress-bar" style="width:${Math.min(100, pct)}%;background:${pctColor}"></div>
          </div>
        </div>

        ${
          timeline.length === 0
            ? `<div class="no-data">Noch keine Jahresabrechnungen eingetragen.<br>Öffne die Integration → Optionen → Jahresabrechnung hinzufügen.</div>`
            : `
        <div class="chart-wrap">
          <svg viewBox="0 0 ${W} ${H}" width="100%" style="display:block">
            <!-- Hintergrundgitter -->
            ${yTickValues
              .map(
                (v) =>
                  `<line x1="${PAD.left}" y1="${yScale(v)}" x2="${W - PAD.right}" y2="${yScale(v)}"
                    stroke="var(--secondary-text-color,#aaa)" stroke-width="0.5" stroke-dasharray="4,4"/>`
              )
              .join("")}

            <!-- Investitions-Linie -->
            <line x1="${PAD.left}" y1="${investY}" x2="${W - PAD.right}" y2="${investY}"
              stroke="#f44336" stroke-width="1.5" stroke-dasharray="6,4"/>
            <text x="${PAD.left + 4}" y="${investY - 5}" font-size="10" fill="#f44336">Investition</text>

            <!-- Nulllinie -->
            ${
              minY < 0
                ? `<line x1="${PAD.left}" y1="${yScale(0)}" x2="${W - PAD.right}" y2="${yScale(0)}"
                stroke="var(--secondary-text-color,#888)" stroke-width="1"/>`
                : ""
            }

            <!-- Prognose-Bereich (gefüllt) -->
            ${
              forecastPath
                ? `<path d="${forecastPath} L${xScale(forecast[forecast.length - 1].year)},${yScale(minY)} L${xScale(actual[actual.length - 1].year)},${yScale(minY)} Z"
                fill="#ff980020" stroke="none"/>`
                : ""
            }

            <!-- Prognose-Linie -->
            ${forecastPath ? `<path d="${forecastPath}" fill="none" stroke="#ff9800" stroke-width="2" stroke-dasharray="5,3"/>` : ""}

            <!-- Ist-Kurve -->
            ${
              actual.length > 1
                ? `<path d="${linePath(actual, "cumulative_revenue")}" fill="none" stroke="#2196f3" stroke-width="2.5" stroke-linejoin="round"/>`
                : ""
            }

            <!-- Amortisationspunkt -->
            ${
              amorPoint
                ? `<circle cx="${xScale(amorPoint.year)}" cy="${yScale(amorPoint.cumulative_revenue)}" r="6"
                fill="#4caf50" stroke="white" stroke-width="2"/>
                <text x="${xScale(amorPoint.year) + 8}" y="${yScale(amorPoint.cumulative_revenue) + 4}" font-size="10" fill="#4caf50">${amorPoint.year}</text>`
                : ""
            }

            <!-- Datenpunkte -->
            ${actual
              .map(
                (d) =>
                  `<circle cx="${xScale(d.year)}" cy="${yScale(d.cumulative_revenue)}" r="3.5"
                  fill="#2196f3"/>`
              )
              .join("")}

            <!-- Y-Achse Labels -->
            ${yTickValues
              .map(
                (v) =>
                  `<text x="${PAD.left - 6}" y="${yScale(v) + 4}" text-anchor="end" font-size="10"
                  opacity="0.7">${this._fmtK(v)} €</text>`
              )
              .join("")}

            <!-- X-Achse Labels -->
            ${xTickValues
              .map(
                (yr) =>
                  `<text x="${xScale(yr)}" y="${H - 8}" text-anchor="middle" font-size="10"
                  opacity="0.7">${yr}</text>`
              )
              .join("")}

            <!-- Achsen -->
            <line x1="${PAD.left}" y1="${PAD.top}" x2="${PAD.left}" y2="${H - PAD.bottom}"
              stroke="var(--secondary-text-color,#aaa)" stroke-width="1"/>
            <line x1="${PAD.left}" y1="${H - PAD.bottom}" x2="${W - PAD.right}" y2="${H - PAD.bottom}"
              stroke="var(--secondary-text-color,#aaa)" stroke-width="1"/>
          </svg>
        </div>

        <div class="legend">
          <div class="legend-item">
            <div class="legend-line" style="background:#2196f3"></div>
            <span>Kumulierte Einnahmen (Ist)</span>
          </div>
          <div class="legend-item">
            <div class="legend-line" style="background:#ff9800"></div>
            <span>Prognose</span>
          </div>
          <div class="legend-item">
            <div class="legend-line" style="background:#f44336"></div>
            <span>Gesamtinvestition</span>
          </div>
          ${amorPoint ? `<div class="legend-item">
            <div style="width:12px;height:12px;border-radius:50%;background:#4caf50"></div>
            <span>Amortisiert</span>
          </div>` : ""}
        </div>
        `
        }
      </ha-card>
    `;
  }

  _fmt(val) {
    return Number(val).toLocaleString("de-DE", {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    });
  }

  _fmtK(val) {
    if (Math.abs(val) >= 1000) {
      return (val / 1000).toFixed(1) + "k";
    }
    return Math.round(val).toString();
  }

  getCardSize() {
    return 5;
  }

  static getConfigElement() {
    return document.createElement("pv-profitability-card-editor");
  }

  static getStubConfig() {
    return {
      timeline_entity: "sensor.pv_verlaufsdaten",
      investment_entity: "sensor.pv_gesamtinvestition",
      revenue_entity: "sensor.pv_gesamteinnahmen",
      balance_entity: "sensor.pv_netto_saldo",
      percent_entity: "sensor.pv_amortisation",
      year_entity: "sensor.pv_amortisationsjahr",
    };
  }
}

customElements.define("pv-profitability-card", PVProfitabilityCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "pv-profitability-card",
  name: "PV Profitability Card",
  description: "Zeigt Amortisationskurve und Kennzahlen der PV-Anlage(n).",
  preview: true,
});
