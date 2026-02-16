const AppConfig = {
  refreshIntervalMs: 20000,
  pages: [
    { id: "home", label: "Home", hash: "#/home" },
    { id: "work", label: "Work", hash: "#/work" },
    { id: "profile", label: "Profile", hash: "#/profile" },
    { id: "game", label: "Game", hash: "#/game" },
    { id: "settings", label: "Settings", hash: "#/settings" },
  ],
};

const AppState = {
  system: { state: "LISTENING" },
  events: [],
  opportunities: [],
  proposals: [],
  launches: [],
  performance: {},
  strategyRecommendations: { recommendations: [] },
  debugMode: localStorage.getItem("treta.debug") === "true",
};

const UI = {
  pageContent: document.getElementById("page-content"),
  pageNav: document.getElementById("page-nav"),
  chatHistory: document.getElementById("chat-history"),
  chatForm: document.getElementById("chat-form"),
  chatInput: document.getElementById("chat-input"),
  statusDot: document.getElementById("status-dot"),
  statusText: document.getElementById("system-status"),
  eventLog: document.getElementById("event-log"),
  lastEvent: document.getElementById("last-event"),
  telemetry: document.getElementById("telemetry-content"),
};

const Api = {
  async get(url, fallback) {
    try {
      const response = await fetch(url);
      if (!response.ok) return fallback;
      return await response.json();
    } catch (error) {
      return fallback;
    }
  },
  async post(url, payload = {}) {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      throw new Error(`Request failed: ${url}`);
    }
    return response.json().catch(() => ({}));
  },
};

const Helpers = {
  text(value, fallback = "-") {
    if (value === null || value === undefined || value === "") return fallback;
    return String(value);
  },
  route() {
    const hash = window.location.hash || "#/home";
    return AppConfig.pages.find((page) => page.hash === hash)?.id || "home";
  },
  badgeClass(rawStatus) {
    const status = String(rawStatus || "").toLowerCase();
    if (["launched", "approved", "running", "ok", "success", "active"].includes(status)) return "ok";
    if (["error", "failed", "offline", "rejected"].includes(status)) return "error";
    return "warn";
  },
  latestEvent() {
    return AppState.events[0] || null;
  },
  latestDecision() {
    return AppState.events.find((event) => ["StrategyDecisionMade", "OpportunityEvaluated"].includes(event.type));
  },
};

const ControlCenter = {
  addChat(role, text) {
    const row = document.createElement("div");
    row.className = `chat-row ${role}`;
    row.textContent = text;
    UI.chatHistory.appendChild(row);
    UI.chatHistory.scrollTop = UI.chatHistory.scrollHeight;
  },
  updateSystemStatus() {
    const rawState = Helpers.text(AppState.system.state, "LISTENING");
    const upper = rawState.toUpperCase();
    let normalized = "LISTENING";
    if (["RUNNING", "ACTIVE", "ONLINE"].includes(upper)) normalized = "RUNNING";
    if (["ERROR", "FAILED", "OFFLINE"].includes(upper)) normalized = "ERROR";

    UI.statusText.textContent = normalized;
    UI.statusDot.classList.remove("status-running", "status-error");
    if (normalized === "RUNNING") UI.statusDot.classList.add("status-running");
    if (normalized === "ERROR") UI.statusDot.classList.add("status-error");
  },
  updateEventWidgets() {
    const latest = Helpers.latestEvent();
    UI.lastEvent.textContent = latest
      ? `${latest.type} · ${Helpers.text(latest.timestamp, "No timestamp")}`
      : "No events yet.";

    const stream = AppState.events.slice(0, 6).map((event) => {
      const payload = typeof event.payload === "object" ? JSON.stringify(event.payload) : Helpers.text(event.payload, "{}");
      return `<div class="event-log-item"><strong>${event.type}</strong><br>${payload.slice(0, 84)}</div>`;
    }).join("");
    UI.eventLog.innerHTML = stream || '<div class="event-log-item">Waiting for events…</div>';
  },
  updateTelemetry() {
    UI.telemetry.innerHTML = `
      <div class="metric"><span>Opportunities</span><strong>${AppState.opportunities.length}</strong></div>
      <div class="metric"><span>Proposals</span><strong>${AppState.proposals.length}</strong></div>
      <div class="metric"><span>Launches</span><strong>${AppState.launches.length}</strong></div>
      <div class="metric"><span>Total revenue</span><strong>${Helpers.text(AppState.performance.total_revenue, 0)}</strong></div>
    `;
  },
};

const Navigation = {
  render() {
    const route = Helpers.route();
    UI.pageNav.innerHTML = "";
    for (const page of AppConfig.pages) {
      const button = document.createElement("button");
      button.className = `nav-btn ${page.id === route ? "active" : ""}`;
      button.textContent = page.label;
      button.addEventListener("click", () => {
        window.location.hash = page.hash;
      });
      UI.pageNav.appendChild(button);
    }
  },
};

const Views = {
  frame(title, subtitle, body) {
    UI.pageContent.innerHTML = `
      <header class="page-head">
        <div>
          <h2 class="page-title">${title}</h2>
          <span class="page-subtitle">${subtitle}</span>
        </div>
      </header>
      ${body}
    `;
  },
  statusBadge(status) {
    const cls = Helpers.badgeClass(status);
    return `<span class="badge ${cls}">${Helpers.text(status, "pending")}</span>`;
  },
  card(title, content) {
    return `<article class="card"><h3>${title}</h3>${content}</article>`;
  },
};

function loadHome() {
  const latestDecision = Helpers.latestDecision();
  const latestLaunch = AppState.launches[0] || {};
  const activeAlerts = AppState.events.filter((event) => String(event.type).toLowerCase().includes("error")).length;

  Views.frame("Home", "System overview", `
    <section class="card-grid">
      ${Views.card("System status card", `<div class="metric"><span>State</span><strong>${Helpers.text(AppState.system.state, "LISTENING")}</strong></div>`)}
      ${Views.card("Latest decision", `<p>${Helpers.text(latestDecision?.type, "No strategic decision yet")}</p>`)}
      ${Views.card("Latest launch", `<p>${Helpers.text(latestLaunch.product_name || latestLaunch.id, "No launches yet")}</p>${Views.statusBadge(latestLaunch.status || "pending")}`)}
      ${Views.card("Revenue summary", `<div class="metric"><span>Total</span><strong>${Helpers.text(AppState.performance.total_revenue, 0)}</strong></div>`)}
      ${Views.card("Active alerts", `<div class="metric"><span>Alerts</span><strong>${activeAlerts}</strong></div>`)}
    </section>
  `);
}

function workCards(items, itemRenderer) {
  if (!items.length) return '<article class="card"><p>No data available.</p></article>';
  return items.map(itemRenderer).join("");
}

function loadWork() {
  Views.frame("Work", "Execution pipeline", `
    <section class="card-grid">
      ${workCards(AppState.opportunities.slice(0, 4), (opportunity) => Views.card(
        `Opportunity · ${Helpers.text(opportunity.id)}`,
        `<p>${Helpers.text(opportunity.title || opportunity.summary, "Untitled opportunity")}</p>${Views.statusBadge(opportunity.status || "new")}`
      ))}

      ${workCards(AppState.proposals.slice(0, 4), (proposal) => Views.card(
        `Proposal · ${Helpers.text(proposal.id)}`,
        `<p>${Helpers.text(proposal.title || proposal.name, "Untitled proposal")}</p>${Views.statusBadge(proposal.status || "draft")}`
      ))}

      ${workCards(AppState.launches.slice(0, 4), (launch) => Views.card(
        `Launch · ${Helpers.text(launch.product_name || launch.id)}`,
        `<div class="metric"><span>Revenue</span><strong>${Helpers.text(launch.metrics?.revenue, 0)}</strong></div>${Views.statusBadge(launch.status || "queued")}`
      ))}

      ${Views.card("Performance summary", `
        <div class="metric"><span>Total sales</span><strong>${Helpers.text(AppState.performance.total_sales, 0)}</strong></div>
        <div class="metric"><span>Best product</span><strong>${Helpers.text(AppState.performance.best_product, "-")}</strong></div>
      `)}

      ${Views.card("Strategy recommendations", (AppState.strategyRecommendations.recommendations || []).slice(0, 3)
        .map((rec) => `<p>${Helpers.text(rec)}</p>`)
        .join("") || "<p>No recommendations.</p>")}
    </section>
  `);
}

function loadProfile() {
  const weeklyOutput = AppState.events.length;
  const revenuePerProduct = AppState.launches.length
    ? (Number(AppState.performance.total_revenue || 0) / AppState.launches.length).toFixed(2)
    : "0";

  Views.frame("Profile", "Personal operating metrics", `
    <section class="card-grid">
      ${Views.card("Energy score", `<div class="metric"><span>Energy</span><strong>82</strong></div>`)}
      ${Views.card("Focus score", `<div class="metric"><span>Focus</span><strong>79</strong></div>`)}
      ${Views.card("Weekly output", `<div class="metric"><span>Events this week</span><strong>${weeklyOutput}</strong></div>`)}
      ${Views.card("Revenue per product", `<div class="metric"><span>Average</span><strong>${revenuePerProduct}</strong></div>`)}
      ${Views.card("Productivity score", `<div class="metric"><span>Score</span><strong>88</strong></div>`)}
    </section>
  `);
}

function loadGame() {
  Views.frame("Game", "Gamification", `
    <section class="card center-message">En construcción</section>
  `);
}

function loadSettings() {
  Views.frame("Settings", "Runtime controls", `
    <section class="card">
      <div class="settings-grid">
        <label>Environment mode
          <select id="environment-mode">
            <option value="production">production</option>
            <option value="staging">staging</option>
            <option value="development">development</option>
          </select>
        </label>
        <label>Scan hour
          <input id="scan-hour" type="time" value="08:00" />
        </label>
        <label>Timezone
          <input id="timezone" value="${Intl.DateTimeFormat().resolvedOptions().timeZone}" />
        </label>
        <label>API status
          <input value="${Helpers.text(AppState.system.state, "LISTENING")}" readonly />
        </label>
        <label>Data path
          <input value="data/memory/treta.sqlite" readonly />
        </label>
        <label>Toggle debug mode
          <button type="button" id="toggle-debug">${AppState.debugMode ? "Disable" : "Enable"} debug mode</button>
        </label>
        <label>Reset data
          <button type="button" id="reset-data">Reset data</button>
        </label>
      </div>
    </section>
  `);

  const toggleButton = document.getElementById("toggle-debug");
  const resetButton = document.getElementById("reset-data");

  toggleButton.addEventListener("click", async () => {
    AppState.debugMode = !AppState.debugMode;
    localStorage.setItem("treta.debug", String(AppState.debugMode));
    await Api.post("/event", {
      type: "DebugModeToggled",
      source: "dashboard",
      payload: { enabled: AppState.debugMode },
    });
    loadSettings();
  });

  resetButton.addEventListener("click", async () => {
    await Api.post("/event", {
      type: "ResetDataRequested",
      source: "dashboard",
      payload: { requested_at: new Date().toISOString() },
    });
    ControlCenter.addChat("system", "Reset data event sent to backend.");
  });
}

const Router = {
  renderCurrent() {
    Navigation.render();
    const route = Helpers.route();
    if (route === "home") return loadHome();
    if (route === "work") return loadWork();
    if (route === "profile") return loadProfile();
    if (route === "game") return loadGame();
    return loadSettings();
  },
};

const DataSync = {
  async refresh() {
    const [
      systemData,
      eventsData,
      opportunitiesData,
      proposalsData,
      launchesData,
      performanceData,
      strategyRecommendations,
    ] = await Promise.all([
      Api.get("/state", { state: "LISTENING" }),
      Api.get("/events", { events: [] }),
      Api.get("/opportunities", { items: [] }),
      Api.get("/product_proposals", { items: [] }),
      Api.get("/product_launches", { items: [] }),
      Api.get("/performance/summary", {}),
      Api.get("/strategy/recommendations", { recommendations: [] }),
    ]);

    AppState.system = systemData;
    AppState.events = eventsData.events || [];
    AppState.opportunities = opportunitiesData.items || [];
    AppState.proposals = proposalsData.items || [];
    AppState.launches = launchesData.items || [];
    AppState.performance = performanceData || {};
    AppState.strategyRecommendations = strategyRecommendations || { recommendations: [] };

    ControlCenter.updateSystemStatus();
    ControlCenter.updateEventWidgets();
    ControlCenter.updateTelemetry();
    Router.renderCurrent();
  },
};

async function runChatCommand(rawInput) {
  const input = rawInput.trim();
  if (!input) return;

  ControlCenter.addChat("user", input);

  if (input === "/scan") {
    await Api.post("/scan/infoproduct");
    ControlCenter.addChat("system", "Infoproduct scan requested.");
  } else if (input.startsWith("/evaluate ")) {
    const id = input.replace("/evaluate", "").trim();
    await Api.post("/opportunities/evaluate", { id });
    ControlCenter.addChat("system", `Opportunity evaluation requested for ${id}.`);
  } else {
    await Api.post("/event", {
      type: "ChatCommandReceived",
      source: "dashboard",
      payload: { message: input },
    });
    ControlCenter.addChat("system", "Command sent to system event bus.");
  }

  await DataSync.refresh();
}

UI.chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await runChatCommand(UI.chatInput.value);
  UI.chatInput.value = "";
});

window.addEventListener("hashchange", () => Router.renderCurrent());

ControlCenter.addChat("system", "Treta OS dashboard online.");
DataSync.refresh();
setInterval(() => {
  DataSync.refresh();
}, AppConfig.refreshIntervalMs);
