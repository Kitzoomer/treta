const CONFIG = {
  routes: ["home", "work", "profile", "game", "settings"],
  defaultRoute: "home",
  defaultRefreshMs: 3000,
  maxEventStream: 10,
};

const STORAGE_KEYS = {
  debug: "treta.debug",
  refreshMs: "treta.refreshMs",
  profile: "treta.profile",
};

const ACTION_TARGETS = {
  work: "work-response",
  settings: "settings-response",
};

const state = {
  system: { state: "IDLE" },
  events: [],
  opportunities: [],
  proposals: [],
  launches: [],
  performance: {},
  strategy: {},
  logs: [{ role: "system", message: "Treta mini-OS online." }],
  debugMode: localStorage.getItem(STORAGE_KEYS.debug) === "true",
  refreshMs: Number(localStorage.getItem(STORAGE_KEYS.refreshMs) || CONFIG.defaultRefreshMs),
  profile: loadProfileState(),
  currentRoute: CONFIG.defaultRoute,
  timerId: null,
};

const ui = {
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

function loadProfileState() {
  const raw = localStorage.getItem(STORAGE_KEYS.profile);
  if (!raw) {
    return {
      energy: 82,
      focus: 79,
      weeklyOutput: 12,
      revenuePerProduct: 0,
      productivity: 88,
    };
  }
  try {
    return JSON.parse(raw);
  } catch (_error) {
    return {
      energy: 82,
      focus: 79,
      weeklyOutput: 12,
      revenuePerProduct: 0,
      productivity: 88,
    };
  }
}

function saveProfileState() {
  localStorage.setItem(STORAGE_KEYS.profile, JSON.stringify(state.profile));
}

const api = {
  async fetchJson(url, options = {}) {
    const response = await fetch(url, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    const text = await response.text();
    const data = text ? JSON.parse(text) : {};
    if (!response.ok) {
      throw new Error(data.error || `HTTP ${response.status}`);
    }
    return data;
  },
  getState() {
    return this.fetchJson("/state");
  },
  getRecentEvents() {
    return this.fetchJson("/events");
  },
  getOpportunities() {
    return this.fetchJson("/opportunities");
  },
  getProductProposals() {
    return this.fetchJson("/product_proposals");
  },
  getProductLaunches() {
    return this.fetchJson("/product_launches");
  },
  getPerformanceSummary() {
    return this.fetchJson("/performance/summary");
  },
  getStrategyRecommendations() {
    return this.fetchJson("/strategy/recommendations");
  },
};

const helpers = {
  t(value, fallback = "-") {
    if (value === undefined || value === null || value === "") return fallback;
    return String(value);
  },
  json(value) {
    return `<pre>${this.escape(JSON.stringify(value, null, 2))}</pre>`;
  },
  escape(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  },
  badgeClass(status) {
    const value = String(status || "").toLowerCase();
    if (["launched", "approved", "active", "completed", "ready"].includes(value)) return "ok";
    if (["rejected", "dismissed", "archived", "failed", "error"].includes(value)) return "error";
    return "warn";
  },
};

const router = {
  resolveRoute() {
    const hash = (window.location.hash || "").replace("#/", "").toLowerCase();
    return CONFIG.routes.includes(hash) ? hash : CONFIG.defaultRoute;
  },
  navigate(route) {
    window.location.hash = `#/${route}`;
  },
  render() {
    state.currentRoute = this.resolveRoute();
    renderNavigation();
    if (state.currentRoute === "home") return views.loadHome();
    if (state.currentRoute === "work") return views.loadWork();
    if (state.currentRoute === "profile") return views.loadProfile();
    if (state.currentRoute === "game") return views.loadGame();
    return views.loadSettings();
  },
};

const views = {
  shell(title, subtitle, body) {
    ui.pageContent.innerHTML = `
      <header class="page-head">
        <div>
          <h2 class="page-title">${title}</h2>
          <p class="page-subtitle">${subtitle}</p>
        </div>
      </header>
      ${body}
    `;
  },

  loadHome() {
    this.shell("Home", "Resumen operativo de Treta", `
      <section class="card-grid cols-2">
        <article class="card">
          <h3>System State</h3>
          <div class="metric"><span>Current</span><strong>${helpers.t(state.system.state, "IDLE")}</strong></div>
          <div class="metric"><span>Latest event</span><strong>${helpers.t(state.events[0]?.type, "none")}</strong></div>
        </article>
        <article class="card">
          <h3>Quick KPIs</h3>
          <div class="metric"><span>Opportunities</span><strong>${state.opportunities.length}</strong></div>
          <div class="metric"><span>Proposals</span><strong>${state.proposals.length}</strong></div>
          <div class="metric"><span>Revenue</span><strong>${helpers.t(state.performance.total_revenue, 0)}</strong></div>
        </article>
      </section>
    `);
  },

  loadWork() {
    const opportunities = state.opportunities.slice(0, 10).map((item) => `
      <article class="card row-item">
        <h4>${helpers.t(item.title, item.id)}</h4>
        <p>source: ${helpers.t(item.source, "-")} · status: ${helpers.t(item.status || item.decision, "pending")}</p>
        <div class="card-actions">
          <button data-action="eval-opp" data-id="${item.id}">Evaluate</button>
          <button data-action="dismiss-opp" data-id="${item.id}">Dismiss</button>
        </div>
      </article>
    `).join("") || "<p class='empty'>No opportunities.</p>";

    const proposals = state.proposals.slice(0, 10).map((item) => `
      <article class="card row-item">
        <h4>${helpers.t(item.product_name, item.id)}</h4>
        <p>
          <span class="badge ${helpers.badgeClass(item.status)}">${helpers.t(item.status, "pending")}</span>
          confidence: ${helpers.t(item.confidence, "-")} · price: ${helpers.t(item.price_suggestion, "-")}
        </p>
        <div class="card-actions wrap">
          ${["approve", "reject", "start_build", "ready", "launch", "archive"].map((action) => `<button data-action="proposal" data-transition="${action}" data-id="${item.id}">${action}</button>`).join("")}
        </div>
      </article>
    `).join("") || "<p class='empty'>No proposals.</p>";

    const launches = state.launches.slice(0, 10).map((item) => `
      <article class="card row-item">
        <h4>${helpers.t(item.product_name, item.id)}</h4>
        <p>
          <span class="badge ${helpers.badgeClass(item.status)}">${helpers.t(item.status, "queued")}</span>
          sales: ${helpers.t(item.metrics?.sales, 0)} · revenue: ${helpers.t(item.metrics?.revenue, 0)}
        </p>
        <div class="card-actions">
          <button data-action="launch-sale" data-id="${item.id}">add_sale</button>
          <button data-action="launch-status" data-id="${item.id}">status</button>
        </div>
      </article>
    `).join("") || "<p class='empty'>No launches.</p>";

    this.shell("Work", "Operaciones y lifecycle", `
      <section class="stack">
        <article class="card"><h3>Opportunities (last 10)</h3>${opportunities}</article>
        <article class="card"><h3>Product Proposals (latest 10)</h3>${proposals}</article>
        <article class="card"><h3>Product Launches (latest 10)</h3>${launches}</article>
        <article class="card"><h3>Performance summary</h3>${helpers.json(state.performance)}</article>
        <article class="card"><h3>Strategy recommendations</h3>${helpers.json(state.strategy)}</article>
        <article class="card"><h3>Action output</h3><section id="work-response" class="result-box">Ready.</section></article>
      </section>
    `);
    bindWorkActions();
  },

  loadProfile() {
    const derivedRevenuePerProduct = state.launches.length
      ? (Number(state.performance.total_revenue || 0) / state.launches.length).toFixed(2)
      : 0;
    if (!state.profile.revenuePerProduct) {
      state.profile.revenuePerProduct = derivedRevenuePerProduct;
    }

    this.shell("Profile", "Ficha editable local (localStorage)", `
      <section class="card">
        <div class="settings-grid">
          ${renderEditableMetric("energy", "Energy")}
          ${renderEditableMetric("focus", "Focus")}
          ${renderEditableMetric("weeklyOutput", "Weekly output")}
          ${renderEditableMetric("revenuePerProduct", "Revenue per product")}
          ${renderEditableMetric("productivity", "Productivity")}
        </div>
        <div class="card-actions"><button id="save-profile">Save profile</button></div>
      </section>
    `);
    document.getElementById("save-profile")?.addEventListener("click", () => {
      ["energy", "focus", "weeklyOutput", "revenuePerProduct", "productivity"].forEach((key) => {
        const value = Number(document.getElementById(`profile-${key}`)?.value || 0);
        state.profile[key] = value;
      });
      saveProfileState();
      log("system", "Profile saved in localStorage.");
    });
  },

  loadGame() {
    this.shell("Game", "Vista reservada", "<section class='card center-message'>En construcción</section>");
  },

  loadSettings() {
    this.shell("Settings", "UI runtime controls", `
      <section class="card">
        <div class="settings-grid">
          <label>Debug mode <input id="debug-toggle" type="checkbox" ${state.debugMode ? "checked" : ""}></label>
          <label>Auto-refresh interval (ms) <input id="refresh-input" type="number" min="1000" step="500" value="${state.refreshMs}"></label>
        </div>
        <div class="card-actions wrap">
          <button id="sync-sales">Sync sales</button>
          <button id="clear-cache">Clear UI cache</button>
        </div>
        <section id="settings-response" class="result-box">Ready.</section>
      </section>
    `);

    document.getElementById("debug-toggle")?.addEventListener("change", (event) => {
      state.debugMode = event.target.checked;
      localStorage.setItem(STORAGE_KEYS.debug, String(state.debugMode));
      log("system", `Debug mode ${state.debugMode ? "enabled" : "disabled"}.`);
    });

    document.getElementById("refresh-input")?.addEventListener("change", (event) => {
      const next = Math.max(1000, Number(event.target.value || CONFIG.defaultRefreshMs));
      state.refreshMs = next;
      localStorage.setItem(STORAGE_KEYS.refreshMs, String(next));
      startRefreshLoop();
      log("system", `Refresh interval updated to ${next}ms.`);
    });

    document.getElementById("sync-sales")?.addEventListener("click", async () => {
      await runAction(async () => api.fetchJson("/gumroad/sync_sales", { method: "POST", body: JSON.stringify({}) }), ACTION_TARGETS.settings);
    });

    document.getElementById("clear-cache")?.addEventListener("click", () => {
      localStorage.clear();
      state.debugMode = false;
      state.refreshMs = CONFIG.defaultRefreshMs;
      state.profile = loadProfileState();
      document.getElementById(ACTION_TARGETS.settings).textContent = "UI cache cleared.";
      log("system", "UI cache cleared.");
    });
  },
};

function renderEditableMetric(key, label) {
  return `<label>${label}<input id="profile-${key}" type="number" value="${helpers.t(state.profile[key], 0)}"></label>`;
}

function renderNavigation() {
  const active = state.currentRoute;
  ui.pageNav.innerHTML = CONFIG.routes
    .map((route) => `<button class="nav-btn ${route === active ? "active" : ""}" data-route="${route}">${route[0].toUpperCase()}${route.slice(1)}</button>`)
    .join("");

  ui.pageNav.querySelectorAll("button[data-route]").forEach((button) => {
    button.addEventListener("click", () => router.navigate(button.dataset.route));
  });
}

function log(role, message) {
  state.logs.push({ role, message });
  if (state.logs.length > 100) state.logs = state.logs.slice(-100);
  renderChat();
}

function renderChat() {
  ui.chatHistory.innerHTML = state.logs
    .slice(-30)
    .map((entry) => `<div class="chat-row ${entry.role}">${helpers.escape(entry.message)}</div>`)
    .join("");
  ui.chatHistory.scrollTop = ui.chatHistory.scrollHeight;
}

function renderControlCenter() {
  const currentState = helpers.t(state.system.state, "IDLE").toUpperCase();
  ui.statusText.textContent = currentState;
  ui.statusDot.classList.remove("status-running", "status-error");
  if (["LISTENING", "RUNNING", "ACTIVE"].includes(currentState)) ui.statusDot.classList.add("status-running");
  if (["ERROR", "FAILED", "OFFLINE"].includes(currentState)) ui.statusDot.classList.add("status-error");

  const last = state.events[0];
  ui.lastEvent.textContent = last ? `${last.type} · ${helpers.t(last.timestamp)}` : "No events yet.";

  ui.eventLog.innerHTML = state.events
    .slice(0, CONFIG.maxEventStream)
    .map((event) => `<div class="event-log-item"><strong>${helpers.escape(event.type)}</strong><br>${helpers.escape(JSON.stringify(event.payload || {}))}</div>`)
    .join("") || "<div class='event-log-item'>Waiting for events…</div>";

  renderChat();
}

function renderTelemetry() {
  ui.telemetry.innerHTML = `
    <div class="metric"><span>Opportunities</span><strong>${state.opportunities.length}</strong></div>
    <div class="metric"><span>Proposals</span><strong>${state.proposals.length}</strong></div>
    <div class="metric"><span>Launches</span><strong>${state.launches.length}</strong></div>
    <div class="metric"><span>Total revenue</span><strong>${helpers.t(state.performance.total_revenue, 0)}</strong></div>
  `;
}

async function refreshLoop() {
  try {
    const [systemData, eventData, oppData, proposalData, launchData, perfData, strategyData] = await Promise.all([
      api.getState(),
      api.getRecentEvents(),
      api.getOpportunities(),
      api.getProductProposals(),
      api.getProductLaunches(),
      api.getPerformanceSummary(),
      api.getStrategyRecommendations(),
    ]);

    state.system = systemData || { state: "IDLE" };
    state.events = eventData.events || [];
    state.opportunities = oppData.items || [];
    state.proposals = proposalData.items || [];
    state.launches = launchData.items || [];
    state.performance = perfData || {};
    state.strategy = strategyData || {};
  } catch (error) {
    log("system", `refresh error: ${error.message}`);
  }

  renderControlCenter();
  renderTelemetry();
  router.render();
}

function startRefreshLoop() {
  if (state.timerId) window.clearInterval(state.timerId);
  state.timerId = window.setInterval(refreshLoop, state.refreshMs);
}

async function executeCommand(rawInput) {
  const input = rawInput.trim();
  const command = input.toLowerCase();
  if (!input) return;

  log("user", input);

  try {
    if (input.startsWith("{")) {
      const payload = JSON.parse(input);
      const result = await api.fetchJson("/event", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      log("system", `POST /event => ${JSON.stringify(result)}`);
      return refreshLoop();
    }

    if (command === "scan") {
      const result = await api.fetchJson("/event", {
        method: "POST",
        body: JSON.stringify({ type: "RunInfoproductScan", payload: {} }),
      });
      log("system", `scan => ${JSON.stringify(result)}`);
      return refreshLoop();
    }

    if (command === "list opps") {
      router.navigate("work");
      log("system", "Navigated to Work (opportunities visible).");
      return;
    }

    if (command === "list proposals") {
      router.navigate("work");
      log("system", "Navigated to Work (proposals visible).");
      return;
    }

    if (command === "sync sales") {
      const result = await api.fetchJson("/gumroad/sync_sales", {
        method: "POST",
        body: JSON.stringify({}),
      });
      log("system", `sync sales => ${JSON.stringify(result)}`);
      return refreshLoop();
    }

    log("system", "Unknown command. Supported: scan, list opps, list proposals, sync sales, JSON payload.");
  } catch (error) {
    log("system", `command error: ${error.message}`);
  }
}

async function runAction(actionFn, targetId) {
  const target = document.getElementById(targetId);
  try {
    const result = await actionFn();
    if (target) target.textContent = JSON.stringify(result, null, 2);
    log("system", `Action ok: ${JSON.stringify(result)}`);
    await refreshLoop();
  } catch (error) {
    if (target) target.textContent = `error: ${error.message}`;
    log("system", `Action failed: ${error.message}`);
  }
}

function bindWorkActions() {
  ui.pageContent.querySelectorAll("button[data-action='eval-opp']").forEach((button) => {
    button.addEventListener("click", async () => {
      await runAction(
        () => api.fetchJson("/opportunities/evaluate", { method: "POST", body: JSON.stringify({ id: button.dataset.id }) }),
        ACTION_TARGETS.work
      );
    });
  });

  ui.pageContent.querySelectorAll("button[data-action='dismiss-opp']").forEach((button) => {
    button.addEventListener("click", async () => {
      await runAction(
        () => api.fetchJson("/opportunities/dismiss", { method: "POST", body: JSON.stringify({ id: button.dataset.id }) }),
        ACTION_TARGETS.work
      );
    });
  });

  ui.pageContent.querySelectorAll("button[data-action='proposal']").forEach((button) => {
    button.addEventListener("click", async () => {
      const endpoint = `/product_proposals/${button.dataset.id}/${button.dataset.transition}`;
      await runAction(() => api.fetchJson(endpoint, { method: "POST", body: JSON.stringify({}) }), ACTION_TARGETS.work);
    });
  });

  ui.pageContent.querySelectorAll("button[data-action='launch-sale']").forEach((button) => {
    button.addEventListener("click", async () => {
      const amount = Number(window.prompt("Sale amount", "1") || "0");
      await runAction(
        () => api.fetchJson(`/product_launches/${button.dataset.id}/add_sale`, { method: "POST", body: JSON.stringify({ amount }) }),
        ACTION_TARGETS.work
      );
    });
  });

  ui.pageContent.querySelectorAll("button[data-action='launch-status']").forEach((button) => {
    button.addEventListener("click", async () => {
      const status = (window.prompt("New status", "active") || "").trim();
      await runAction(
        () => api.fetchJson(`/product_launches/${button.dataset.id}/status`, { method: "POST", body: JSON.stringify({ status }) }),
        ACTION_TARGETS.work
      );
    });
  });
}

ui.chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await executeCommand(ui.chatInput.value);
  ui.chatInput.value = "";
});

window.addEventListener("hashchange", () => router.render());

startRefreshLoop();
refreshLoop();
