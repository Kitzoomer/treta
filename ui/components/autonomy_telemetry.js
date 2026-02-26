(function attachAutonomyTelemetry(global) {
  function normalizeObject(payload) {
    if (!payload || typeof payload !== "object") return {};
    if (payload.data && typeof payload.data === "object") return payload.data;
    return payload;
  }

  function formatNumber(value, digits = 0) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return "-";
    return numeric.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
  }

  function formatPercent(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return "-";
    return `${numeric.toFixed(1)}%`;
  }

  function formatDate(value) {
    if (!value) return "-";
    const parsed = new Date(value);
    if (!Number.isFinite(parsed.getTime())) return String(value);
    return parsed.toLocaleString();
  }

  function modeBadgeClass(mode) {
    const normalized = String(mode || "manual").toLowerCase();
    if (normalized === "partial") return "mode-partial";
    if (normalized === "disabled") return "mode-disabled";
    return "mode-manual";
  }

  function budgetClass(remaining, max) {
    const maxValue = Number(max);
    const remainingValue = Number(remaining);
    if (!Number.isFinite(maxValue) || maxValue <= 0 || !Number.isFinite(remainingValue)) return "budget-healthy";
    if (remainingValue <= 0) return "budget-empty";
    const ratio = remainingValue / maxValue;
    if (ratio < 0.3) return "budget-low";
    return "budget-healthy";
  }

  function renderMetricCard(label, value) {
    return `
      <article class="autonomy-metric-card">
        <h4>${label}</h4>
        <p>${value}</p>
      </article>
    `;
  }

  function renderError(message) {
    return `<p class="autonomy-telemetry-error">${message}</p>`;
  }

  function mapStrategicSummary(summary) {
    const totalDecisions = Number(summary.total_decisions || 0);
    const autonomousDecisions = Number(summary.autonomous_decisions ?? summary.total_autonomous ?? 0);
    const manualDecisions = Number(summary.manual_decisions ?? summary.total_manual ?? Math.max(totalDecisions - autonomousDecisions, 0));
    const avgPredictedImpact = Number(summary.avg_predicted_impact ?? summary.avg_predicted_risk ?? 0);
    const avgRealImpact = Number(summary.avg_real_impact ?? summary.success_rate ?? 0);
    const revenueDeltaTotal = Number(summary.revenue_delta_total ?? summary.total_revenue ?? 0);
    const autonomousPercentage = totalDecisions > 0 ? (autonomousDecisions / totalDecisions) * 100 : 0;

    return {
      totalDecisions,
      autonomousDecisions,
      manualDecisions,
      autonomousPercentage,
      avgPredictedImpact,
      avgRealImpact,
      revenueDeltaTotal,
    };
  }

  function mapAutonomyState(statePayload) {
    const mode = String(statePayload.mode || "manual").toLowerCase();
    const impactThreshold = Number(statePayload.impact_threshold ?? 0);
    const maxAutoExecutions = Number(statePayload.max_auto_executions_per_24h ?? 0);
    const autoExecutionsLast24h = Number(statePayload.auto_executions_last_24h ?? statePayload.auto_executed_last_24h ?? 0);
    const remainingBudgetRaw = statePayload.remaining_budget_24h;
    const derivedBudget = Number.isFinite(Number(remainingBudgetRaw))
      ? Number(remainingBudgetRaw)
      : Math.max(maxAutoExecutions - autoExecutionsLast24h, 0);

    return {
      mode,
      impactThreshold,
      maxAutoExecutions,
      autoExecutionsLast24h,
      remainingBudget24h: derivedBudget,
      adaptiveState: statePayload.adaptive_state && typeof statePayload.adaptive_state === "object"
        ? statePayload.adaptive_state
        : statePayload,
    };
  }

  function renderAutonomyStatusSection(stateModel) {
    const manualMessage = stateModel.mode === "manual"
      ? '<p class="autonomy-manual-note">Autonomy is in manual mode. No automatic executions will run.</p>'
      : "";

    return `
      <section class="card autonomy-block">
        <header>
          <h3>Autonomy Status</h3>
        </header>
        <div class="autonomy-status-grid">
          <article class="autonomy-mode-card">
            <h4>Mode</h4>
            <p><span class="autonomy-mode-badge ${modeBadgeClass(stateModel.mode)}">${stateModel.mode.toUpperCase()}</span></p>
          </article>
          ${renderMetricCard("Impact Threshold", formatNumber(stateModel.impactThreshold))}
          ${renderMetricCard("Max Auto Executions (24h)", formatNumber(stateModel.maxAutoExecutions))}
          ${renderMetricCard("Auto Executions Last 24h", formatNumber(stateModel.autoExecutionsLast24h))}
          <article class="autonomy-metric-card">
            <h4>Remaining Budget (24h)</h4>
            <p class="${budgetClass(stateModel.remainingBudget24h, stateModel.maxAutoExecutions)}">${formatNumber(stateModel.remainingBudget24h)}</p>
          </article>
        </div>
        ${manualMessage}
      </section>
    `;
  }

  function renderPerformanceSection(summaryModel) {
    return `
      <section class="card autonomy-block">
        <header>
          <h3>Performance Summary</h3>
        </header>
        <div class="autonomy-metrics-grid">
          ${renderMetricCard("Total Decisions", formatNumber(summaryModel.totalDecisions))}
          ${renderMetricCard("Autonomous Decisions", formatNumber(summaryModel.autonomousDecisions))}
          ${renderMetricCard("Manual Decisions", formatNumber(summaryModel.manualDecisions))}
          ${renderMetricCard("% Autonomous", formatPercent(summaryModel.autonomousPercentage))}
          ${renderMetricCard("Avg Predicted Impact", formatNumber(summaryModel.avgPredictedImpact, 2))}
          ${renderMetricCard("Avg Real Impact", formatNumber(summaryModel.avgRealImpact, 2))}
          ${renderMetricCard("Revenue Delta Total", formatNumber(summaryModel.revenueDeltaTotal, 2))}
        </div>
      </section>
    `;
  }

  function renderAdaptiveSection(stateModel) {
    const adaptive = stateModel.adaptiveState;
    if (!adaptive || typeof adaptive !== "object") {
      return `
        <section class="card autonomy-block">
          <header><h3>Adaptive Policy State</h3></header>
          <p class="muted-note">Adaptive policy active but no detailed telemetry available.</p>
        </section>
      `;
    }

    const priorityOrder = Array.isArray(adaptive.strategy_priority_order)
      ? adaptive.strategy_priority_order
      : (adaptive.strategy_weights && typeof adaptive.strategy_weights === "object"
        ? Object.entries(adaptive.strategy_weights)
          .sort((left, right) => Number(right[1] || 0) - Number(left[1] || 0))
          .map(([name]) => name)
        : []);

    return `
      <section class="card autonomy-block">
        <header>
          <h3>Adaptive Policy State</h3>
        </header>
        <div class="autonomy-metrics-grid">
          ${renderMetricCard("Current Impact Threshold", formatNumber(adaptive.impact_threshold ?? stateModel.impactThreshold))}
          ${renderMetricCard("Last Update", formatDate(adaptive.updated_at || adaptive.last_updated_at || adaptive.last_update))}
          <article class="autonomy-metric-card autonomy-priority-card">
            <h4>Strategy Priority Order</h4>
            <p>${priorityOrder.length ? priorityOrder.join(" → ") : "Not available"}</p>
          </article>
        </div>
      </section>
    `;
  }

  async function fetchWithFallback(api, primaryPath, fallbackPath) {
    if (!api || typeof api.fetchJson !== "function") {
      const fetchPath = async (path) => fetch(path, { headers: { "Content-Type": "application/json" } }).then((response) => {
        if (!response.ok) throw new Error(`Request failed (${response.status})`);
        return response.json();
      });
      try {
        return { payload: normalizeObject(await fetchPath(primaryPath)), error: null };
      } catch (error) {
        if (!fallbackPath) return { payload: null, error };
        try {
          return { payload: normalizeObject(await fetchPath(fallbackPath)), error: null };
        } catch (_fallbackError) {
          return { payload: null, error };
        }
      }
    }

    try {
      return { payload: normalizeObject(await api.fetchJson(primaryPath)), error: null };
    } catch (error) {
      if (!fallbackPath) return { payload: null, error };
      try {
        return { payload: normalizeObject(await api.fetchJson(fallbackPath)), error: null };
      } catch (_fallbackError) {
        return { payload: null, error };
      }
    }
  }

  async function render(options) {
    const target = options?.target;
    const api = options?.api;
    if (!target) return;

    target.innerHTML = `
      <header class="page-head">
        <div>
          <h2 class="page-title">Autonomy Telemetry</h2>
          <p class="page-subtitle">Live autonomous policy state, limits, and adaptive behavior.</p>
        </div>
      </header>
      <section class="card autonomy-block">
        <p class="autonomy-telemetry-loading">Loading autonomy telemetry…</p>
      </section>
    `;

    const [stateResult, summaryResult] = await Promise.all([
      fetchWithFallback(api, "/autonomy/state", "/autonomy/status"),
      fetchWithFallback(api, "/metrics/strategic/summary", null),
    ]);

    const sections = [];

    if (stateResult.payload) {
      const stateModel = mapAutonomyState(stateResult.payload);
      sections.push(renderAutonomyStatusSection(stateModel));
      sections.push(renderAdaptiveSection(stateModel));
      target.dataset.autonomyMode = stateModel.mode;
    } else {
      sections.push(renderError("Unable to load autonomy state."));
    }

    if (summaryResult.payload) {
      const summaryModel = mapStrategicSummary(summaryResult.payload);
      sections.splice(stateResult.payload ? 1 : 0, 0, renderPerformanceSection(summaryModel));
    } else {
      sections.push(renderError("Unable to load strategic performance summary."));
    }

    target.innerHTML = `
      <header class="page-head">
        <div>
          <h2 class="page-title">Autonomy Telemetry</h2>
          <p class="page-subtitle">Live autonomous policy state, limits, and adaptive behavior.</p>
        </div>
      </header>
      <section class="autonomy-telemetry-grid">
        ${sections.join("\n")}
      </section>
    `;
  }

  global.TretaAutonomyTelemetry = { render };
}(window));
