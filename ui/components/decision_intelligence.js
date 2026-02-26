(function attachDecisionIntelligence(global) {
  function normalizeItems(payload) {
    if (!payload) return [];
    if (Array.isArray(payload)) return payload;
    if (Array.isArray(payload.data)) return payload.data;
    if (Array.isArray(payload.items)) return payload.items;
    if (Array.isArray(payload.data?.items)) return payload.data.items;
    return [];
  }

  function normalizeRisk(item) {
    const fromRisk = String(item?.risk_level || "").trim().toLowerCase();
    if (fromRisk) return fromRisk;
    const score = Number(item?.risk_score);
    if (!Number.isFinite(score)) return "unknown";
    if (score < 0.34) return "low";
    if (score < 0.67) return "medium";
    return "high";
  }

  function resolveMode(item) {
    if (typeof item?.auto_executed === "boolean") return item.auto_executed ? "Auto" : "Manual";
    const status = String(item?.status || "").toLowerCase();
    if (status === "auto_executed") return "Auto";
    return "Manual";
  }

  function sortByNewest(left, right) {
    const leftTime = Date.parse(left?.created_at || "");
    const rightTime = Date.parse(right?.created_at || "");
    return (Number.isFinite(rightTime) ? rightTime : 0) - (Number.isFinite(leftTime) ? leftTime : 0);
  }

  function renderRows(items) {
    return items.map((item) => {
      const createdAt = item?.created_at ? new Date(item.created_at).toLocaleString() : "-";
      const risk = normalizeRisk(item);
      const status = String(item?.status || "unknown").toLowerCase();
      const statusLabel = status.replaceAll("_", " ");
      const entity = item?.entity_id || item?.entity_type || "-";

      return `
        <tr>
          <td>${createdAt}</td>
          <td>${item?.decision_type || "-"}</td>
          <td>${entity}</td>
          <td>${item?.score ?? item?.autonomy_score ?? item?.risk_score ?? "-"}</td>
          <td><span class="di-badge risk ${risk}">${risk}</span></td>
          <td><span class="di-badge status ${status}">${statusLabel}</span></td>
          <td>${resolveMode(item)}</td>
          <td class="di-correlation-id">${item?.correlation_id || "-"}</td>
        </tr>
      `;
    }).join("");
  }

  async function render(options) {
    const target = options?.target;
    const api = options?.api;
    if (!target) return;

    target.innerHTML = `
      <header class="page-head">
        <div>
          <h2 class="page-title">Decision Intelligence</h2>
          <p class="page-subtitle">Latest strategic decisions and execution signals.</p>
        </div>
      </header>
      <section class="card decision-intelligence-panel">
        <p class="decision-intelligence-loading">Loading decision logs…</p>
      </section>
    `;

    const panel = target.querySelector(".decision-intelligence-panel");
    if (!panel) return;

    try {
      const payload = api
        ? await api.fetchJson("/decision-logs?limit=20")
        : await fetch("/decision-logs?limit=20", { headers: { "Content-Type": "application/json" } }).then((res) => res.json());
      const items = normalizeItems(payload).sort(sortByNewest);

      if (!items.length) {
        panel.innerHTML = '<p class="empty">No decisions recorded yet.</p>';
        return;
      }

      panel.innerHTML = `
        <div class="decision-intelligence-table-wrap">
          <table class="decision-intelligence-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Type</th>
                <th>Entity</th>
                <th>Score</th>
                <th>Risk</th>
                <th>Status</th>
                <th>Mode</th>
                <th>Correlation ID</th>
              </tr>
            </thead>
            <tbody>
              ${renderRows(items)}
            </tbody>
          </table>
        </div>
      `;
    } catch (_error) {
      panel.innerHTML = '<p class="error">Unable to load decision logs right now.</p>';
    }
  }

  global.TretaDecisionIntelligence = { render };
}(window));
