const pages = [
  { id: "home", label: "Treta (Home)", hash: "#/home" },
  { id: "work", label: "nomorebusywork (Work)", hash: "#/work" },
  { id: "profile", label: "Area Personal (Profile)", hash: "#/profile" },
  { id: "game", label: "Juegos (Game)", hash: "#/game" },
  { id: "settings", label: "Ajustes (Settings)", hash: "#/settings" },
];

const state = {
  system: { state: "unknown" },
  events: [],
  opportunities: [],
  proposals: [],
  launches: [],
  performance: {},
  strategy: {},
  recommendations: [],
};

const pageContent = document.getElementById("page-content");
const pageNav = document.getElementById("page-nav");
const chatHistory = document.getElementById("chat-history");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const statusDot = document.getElementById("status-dot");
const statusText = document.getElementById("system-status");

function safeText(value, fallback = "-") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  return String(value);
}

async function requestJson(url, fallback) {
  try {
    const response = await fetch(url);
    if (!response.ok) {
      return fallback;
    }
    return await response.json();
  } catch (error) {
    return fallback;
  }
}

function addChat(role, text) {
  const row = document.createElement("div");
  row.className = `chat-row ${role}`;
  row.textContent = text;
  chatHistory.appendChild(row);
  chatHistory.scrollTop = chatHistory.scrollHeight;
}

function getRoute() {
  const hash = window.location.hash || "#/home";
  return pages.find((page) => page.hash === hash)?.id || "home";
}

function renderNav() {
  const route = getRoute();
  pageNav.innerHTML = "";

  for (const page of pages) {
    const button = document.createElement("button");
    button.className = `nav-btn ${page.id === route ? "active" : ""}`;
    button.textContent = page.label;
    button.addEventListener("click", () => {
      window.location.hash = page.hash;
    });
    pageNav.appendChild(button);
  }
}

function lastStrategicDecision() {
  return [...state.events]
    .reverse()
    .find((event) => event.type === "OpportunityEvaluated" || event.type === "StrategyDecisionMade");
}

function buildMetric(label, value) {
  return `<div class="kv"><label>${label}</label><span>${safeText(value)}</span></div>`;
}

function renderHome() {
  const decisionEvent = lastStrategicDecision();
  const decisionPayload = decisionEvent?.payload?.decision || decisionEvent?.payload || {};
  const nextScan = new Date(Date.now() + 60 * 60 * 1000).toLocaleTimeString();
  const recommendation = state.recommendations?.recommendations?.[0] || "Monitor opportunities and keep launch cadence.";

  pageContent.innerHTML = `
    <h2 class="page-title">Treta · Home</h2>
    <section class="card wave" aria-hidden="true"></section>
    <section class="stats-grid">
      ${buildMetric("Current system state", state.system.state)}
      ${buildMetric("Last strategic decision", decisionPayload.decision || "No decisions yet")}
      ${buildMetric("Next scan time", nextScan)}
      ${buildMetric("Current recommendation", recommendation)}
    </section>
  `;
}

function renderWork() {
  const rows = state.launches.slice(0, 10).map((launch) => {
    const metrics = launch.metrics || {};
    return `
      <tr>
        <td>${safeText(launch.product_name || launch.id)}</td>
        <td>${safeText(launch.status)}</td>
        <td>${safeText(launch.price || launch.price_suggestion)}</td>
        <td>${safeText(metrics.sales, 0)}</td>
        <td>${safeText(metrics.revenue, 0)}</td>
        <td>${safeText(state.strategy.suggested_action || "Optimize pricing and update creatives")}</td>
      </tr>
    `;
  }).join("");

  const statuses = ["draft", "approved", "ready", "launched", "archived"];
  const lifecycle = statuses.map((statusLabel) => {
    const count = state.proposals.filter((proposal) => (proposal.status || "draft") === statusLabel).length;
    return `<article class="card">${buildMetric(statusLabel, count)}</article>`;
  }).join("");

  pageContent.innerHTML = `
    <h2 class="page-title">nomorebusywork · Work</h2>
    <section class="card">
      <h3>Product Overview</h3>
      <div class="table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th>product_name</th><th>status</th><th>price</th><th>sales</th><th>revenue</th><th>recommended_action</th>
            </tr>
          </thead>
          <tbody>${rows || '<tr><td colspan="6">No products available.</td></tr>'}</tbody>
        </table>
      </div>
    </section>

    <section>
      <h3>Lifecycle</h3>
      <div class="lifecycle-grid">${lifecycle}</div>
    </section>

    <section class="stats-grid">
      ${buildMetric("total_revenue", state.performance.total_revenue || 0)}
      ${buildMetric("total_sales", state.performance.total_sales || 0)}
      ${buildMetric("best_product", state.performance.best_product || "-")}
      ${buildMetric("top_category", state.performance.top_category || "-")}
    </section>

    <section class="card">
      <h3>Strategy</h3>
      <p><strong>Last decision:</strong> ${safeText(state.strategy.last_decision || "-")}</p>
      <p><strong>Reason:</strong> ${safeText(state.strategy.reason || "-")}</p>
      <p><strong>Suggested action:</strong> ${safeText(state.strategy.suggested_action || "-")}</p>
    </section>
  `;
}

function renderProfile() {
  const totalProducts = state.proposals.length;
  pageContent.innerHTML = `
    <h2 class="page-title">Area Personal · Profile</h2>
    <section class="stats-grid">
      ${buildMetric("Energy level indicator", "High focus")}
      ${buildMetric("Productivity metrics", `${state.events.length} tracked events`)}
      ${buildMetric("Total products created", totalProducts)}
      ${buildMetric("Total revenue", state.performance.total_revenue || 0)}
      ${buildMetric("Active goals", "3")}
      ${buildMetric("Weekly consistency", "86%")}
    </section>
  `;
}

function renderGame() {
  pageContent.innerHTML = `
    <h2 class="page-title">Juegos · Game</h2>
    <section class="card big-message">System in construction – gamification module coming soon</section>
  `;
}

function renderSettings() {
  pageContent.innerHTML = `
    <h2 class="page-title">Ajustes · Settings</h2>

    <section class="card">
      <h3>System</h3>
      <div class="settings-grid">
        ${buildMetric("Timezone", Intl.DateTimeFormat().resolvedOptions().timeZone)}
        ${buildMetric("Scan hour", "08:00")}
        ${buildMetric("Environment", "production")}
      </div>
    </section>

    <section class="card">
      <h3>Integrations</h3>
      <div class="settings-grid">
        ${buildMetric("Reddit status", "Not connected")}
        ${buildMetric("Gumroad status", state.launches.length ? "Connected" : "Pending")}
        ${buildMetric("Token configured", state.launches.length > 0)}
      </div>
    </section>

    <section class="card">
      <h3>Automation</h3>
      <div class="settings-grid">
        ${buildMetric("Auto launch toggle", "On")}
        ${buildMetric("Auto pricing toggle", "On")}
        ${buildMetric("Strategy mode selector", "Balanced")}
      </div>
    </section>

    <section class="card">
      <h3>Security</h3>
      <div class="settings-grid">
        <button type="button">Reset data</button>
        <button type="button">Clear proposals</button>
        <button type="button">Clear launches</button>
      </div>
    </section>
  `;
}

function renderRoute() {
  renderNav();
  const route = getRoute();

  if (route === "home") return renderHome();
  if (route === "work") return renderWork();
  if (route === "profile") return renderProfile();
  if (route === "game") return renderGame();
  return renderSettings();
}

function normalizeStrategy(decisionData, eventDecision) {
  return {
    last_decision: decisionData.decision || eventDecision?.decision || "-",
    reason: decisionData.reasoning || eventDecision?.reasoning || "-",
    suggested_action: decisionData.recommended_action || "Prepare next launch",
  };
}

async function refreshData() {
  const [systemData, eventsData, proposalsData, launchesData, performanceData, strategyData, recommendationsData] = await Promise.all([
    requestJson("/state", { state: "offline" }),
    requestJson("/events", { events: [] }),
    requestJson("/product_proposals", { items: [] }),
    requestJson("/product_launches", { items: [] }),
    requestJson("/performance/summary", {}),
    requestJson("/strategy/decide", {}),
    requestJson("/strategy/recommendations", { recommendations: [] }),
  ]);

  state.system = systemData;
  state.events = eventsData.events || [];
  state.proposals = proposalsData.items || [];
  state.launches = launchesData.items || [];
  state.performance = performanceData || {};
  const eventDecision = lastStrategicDecision()?.payload?.decision || lastStrategicDecision()?.payload;
  state.strategy = normalizeStrategy(strategyData, eventDecision || {});
  state.recommendations = recommendationsData || {};

  statusText.textContent = safeText(systemData.state);
  if (String(systemData.state || "").toLowerCase() !== "offline") {
    statusDot.classList.add("online");
  } else {
    statusDot.classList.remove("online");
  }

  renderRoute();
}

async function runChatCommand(rawInput) {
  const input = rawInput.trim();
  if (!input) return;

  addChat("user", input);

  if (input === "/scan") {
    await fetch("/scan/infoproduct", { method: "POST" });
    addChat("system", "Infoproduct scan requested.");
  } else if (input.startsWith("/evaluate ")) {
    const id = input.replace("/evaluate", "").trim();
    await fetch("/opportunities/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    });
    addChat("system", `Opportunity evaluation requested for ${id}.`);
  } else {
    await fetch("/event", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        type: "ChatCommandReceived",
        source: "dashboard",
        payload: { message: input },
      }),
    });
    addChat("system", "Command sent to system event bus.");
  }

  await refreshData();
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await runChatCommand(chatInput.value);
  chatInput.value = "";
});

window.addEventListener("hashchange", renderRoute);

addChat("system", "Treta interface ready.");
refreshData();
setInterval(refreshData, 20000);
