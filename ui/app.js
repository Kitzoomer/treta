const CONFIG = {
  routes: ["home", "dashboard", "work", "profile", "game", "settings"],
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
  appRoot: document.getElementById("app-root"),
  pageContent: null,
  pageNav: null,
  chatHistory: null,
  chatForm: null,
  chatInput: null,
  statusDot: null,
  statusText: null,
  eventLog: null,
  lastEvent: null,
  telemetry: null,
};

function cacheUIElements() {
  ui.pageContent = document.getElementById("page-content");
  ui.pageNav = document.getElementById("page-nav");
  ui.chatHistory = document.getElementById("chat-history");
  ui.chatForm = document.getElementById("chat-form");
  ui.chatInput = document.getElementById("chat-input");
  ui.statusDot = document.getElementById("status-dot");
  ui.statusText = document.getElementById("system-status");
  ui.eventLog = document.getElementById("event-log");
  ui.lastEvent = document.getElementById("last-event");
  ui.telemetry = document.getElementById("telemetry-content");
}

function bindShellEvents() {
  ui.chatForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    await executeCommand(ui.chatInput.value);
    ui.chatInput.value = "";
  });
}

function renderLayout({ centerContent }) {
  ui.appRoot.innerHTML = `
    <main class="app-layout">
      <aside class="panel panel-left" aria-label="Control center">
        <header class="panel-header">
          <h1>Control Center</h1>
          <div class="system-status" id="system-indicator">
            <span class="status-dot" id="status-dot"></span>
            <span id="system-status">LISTENING</span>
          </div>
        </header>

        <section class="control-card chat-panel">
          <h2>Chat</h2>
          <p class="control-helper">Ask for actions in plain language. Treta translates quick commands into pipeline events.</p>
          <section id="chat-history" class="chat-history chat-messages" aria-live="polite"></section>

          <form id="chat-form" class="chat-controls chat-input-row">
            <input id="chat-input" type="text" placeholder="Try: 'scan for opportunities' or 'show me proposals ready to launch'" autocomplete="off" />
            <button type="submit">Execute</button>
          </form>
        </section>

        <section class="control-card mini-status">
          <h2>Last event executed</h2>
          <p id="last-event" class="last-event">No events yet.</p>
        </section>

        <section class="control-card mini-log">
          <h2>Event stream</h2>
          <div id="event-log" class="event-log"></div>
        </section>
      </aside>

      <section class="panel panel-center">
        <div id="page-content" class="page-content">${centerContent}</div>
      </section>

      <aside class="panel panel-right" aria-label="Navigation and telemetry">
        <section class="control-card">
          <h2>Navigation</h2>
          <nav id="page-nav" class="page-nav" aria-label="Main navigation"></nav>
        </section>

        <section class="control-card" id="telemetry-panel">
          <h2>Live telemetry</h2>
          <div id="telemetry-content" class="telemetry-content"></div>
        </section>
      </aside>
    </main>
  `;

  cacheUIElements();
  bindShellEvents();
  renderNavigation();
  renderControlCenter();
  renderTelemetry();
}

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
  normalizeStatus(status) {
    return String(status || "").toLowerCase();
  },
  badgeClass(status) {
    const value = this.normalizeStatus(status);
    if (["launched", "approved", "active", "completed", "ready", "ready_to_launch"].includes(value)) return "ok";
    if (["rejected", "dismissed", "archived", "failed", "error"].includes(value)) return "error";
    if (["building", "in_progress", "draft", "ready_for_review"].includes(value)) return "info";
    return "warn";
  },
  statusLabel(status) {
    return this.normalizeStatus(status).replaceAll("_", " ") || "pending";
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
    document.body.dataset.route = state.currentRoute;
    if (state.currentRoute === "home") return views.loadHome();
    if (state.currentRoute === "dashboard") return views.loadDashboard();
    if (state.currentRoute === "work") return views.loadWork();
    if (state.currentRoute === "profile") return views.loadProfile();
    if (state.currentRoute === "game") return views.loadGame();
    return views.loadSettings();
  },
};

const views = {
  shell(title, subtitle, body) {
    renderLayout({
      centerContent: `
        <header class="page-head">
          <div>
            <h2 class="page-title">${title}</h2>
            <p class="page-subtitle">${subtitle}</p>
          </div>
        </header>
        ${body}
      `,
    });
  },

  loadHome() {
    renderLayout({
      centerContent: `
        <section class="home-identity" aria-label="Treta identity">
          <h1 class="treta-title" aria-label="TRETA">
            <span class="treta-title-text">TRETA</span>
            <span class="treta-wave" aria-hidden="true"></span>
          </h1>
        </section>
      `,
    });
  },

  loadDashboard() {
    const latestDecision = state.proposals[0];
    const latestLaunch = state.launches[0];
    const proposalsByStatus = state.proposals.reduce((acc, item) => {
      const status = helpers.normalizeStatus(item.status);
      acc[status] = (acc[status] || 0) + 1;
      return acc;
    }, {});

    const opportunitiesCount = state.opportunities.length;
    const proposalsCount = state.proposals.length;
    const buildsCount = state.proposals.filter((item) => ["approved", "building", "ready_to_launch", "ready_for_review"].includes(helpers.normalizeStatus(item.status))).length;
    const launchedProducts = state.launches.filter((item) => helpers.normalizeStatus(item.status) === "launched").length;
    const readyToLaunch = (proposalsByStatus.ready_to_launch || 0) + (proposalsByStatus.ready_for_review || 0);
    const draftCount = proposalsByStatus.draft || 0;
    const alertsCount = state.events.filter((event) => ["error", "failed", "warning"].some((keyword) => helpers.normalizeStatus(event.type).includes(keyword))).length;

    const recommendation = (() => {
      if (readyToLaunch > 0) {
        return {
          title: "Launch products already marked ready",
          body: `${readyToLaunch} proposal(s) can be launched now to validate demand and convert momentum into revenue.`,
        };
      }
      if (draftCount > 0) {
        return {
          title: "Review and approve draft proposals",
          body: `${draftCount} draft proposal(s) are waiting for a decision and can unblock the build queue.`,
        };
      }
      if (opportunitiesCount === 0) {
        return {
          title: "Run a new opportunity scan",
          body: "No opportunities are available yet. Trigger a scan from chat to refill the pipeline.",
        };
      }
      return {
        title: "Keep builds moving",
        body: "Pipeline is healthy. Prioritize items in building to keep launch cadence consistent.",
      };
    })();

    this.shell("Dashboard", "Operational summary and next best action", `
      <section class="stack">
        <section class="card-grid cols-2">
          <article class="card">
            <h3>System state</h3>
            <div class="metric"><span>Current</span><strong>${helpers.t(state.system.state, "IDLE")}</strong></div>
          </article>
          <article class="card">
            <h3>Latest decision</h3>
            <p>${latestDecision ? `${helpers.t(latestDecision.product_name, latestDecision.id)} · ${helpers.statusLabel(latestDecision.status)}` : "No data yet."}</p>
          </article>
          <article class="card">
            <h3>Latest launch</h3>
            <p>${latestLaunch ? `${helpers.t(latestLaunch.product_name, latestLaunch.id)} · ${helpers.statusLabel(latestLaunch.status)}` : "No data yet."}</p>
          </article>
          <article class="card">
            <h3>Revenue summary</h3>
            <div class="metric"><span>Total revenue</span><strong>${helpers.t(state.performance.total_revenue, 0)}</strong></div>
            <div class="metric"><span>Total sales</span><strong>${helpers.t(state.performance.total_sales, 0)}</strong></div>
          </article>
          <article class="card">
            <h3>Alerts</h3>
            <div class="metric"><span>Recent alerts</span><strong>${alertsCount}</strong></div>
          </article>
        </section>

        <article class="card pipeline-summary">
          <h3>Pipeline Summary</h3>
          <div class="pipeline-flow">
            <div class="pipeline-step"><span>Opportunities</span><strong>${opportunitiesCount}</strong></div>
            <div class="pipeline-arrow">→</div>
            <div class="pipeline-step"><span>Proposals</span><strong>${proposalsCount}</strong></div>
            <div class="pipeline-arrow">→</div>
            <div class="pipeline-step"><span>Builds</span><strong>${buildsCount}</strong></div>
            <div class="pipeline-arrow">→</div>
            <div class="pipeline-step"><span>Launched</span><strong>${launchedProducts}</strong></div>
          </div>
        </article>

        <article class="card recommendation-card">
          <h3>Recommended Action</h3>
          <h4>${recommendation.title}</h4>
          <p>${recommendation.body}</p>
          <div class="recommendation-cta">UI heuristic based on current pipeline data</div>
        </article>
      </section>
    `);
  },

  loadWork() {
    const opportunitiesCount = state.opportunities.length;
    const proposalStatuses = state.proposals.reduce((acc, item) => {
      const status = helpers.normalizeStatus(item.status);
      acc[status] = (acc[status] || 0) + 1;
      return acc;
    }, {});
    const proposalsDraft = proposalStatuses.draft || 0;
    const proposalsReady = (proposalStatuses.ready_to_launch || 0) + (proposalStatuses.ready_for_review || 0);
    const buildsInProgress = proposalStatuses.building || 0;
    const launchedProducts = state.launches.filter((item) => helpers.normalizeStatus(item.status) === "launched").length;

    const recommendedAction = (() => {
      if (proposalsDraft > 0) {
        return {
          title: "Move proposals into build",
          body: "You have draft proposals waiting for approval. Promote the strongest draft to start execution.",
          cta: "Review draft proposals",
        };
      }
      if (proposalsReady > 0) {
        return {
          title: "Launch ready products",
          body: "Some builds are marked ready. Launch them now to start collecting market feedback.",
          cta: "Launch ready products",
        };
      }
      return {
        title: "Scan for new opportunities",
        body: "Pipeline is quiet. Run a fresh scan to feed new opportunities into the workflow.",
        cta: "Run opportunity scan",
      };
    })();

    const transitionConfig = {
      draft: [{ transition: "approve", label: "Move to Build" }, { transition: "reject", label: "Reject" }],
      approved: [{ transition: "start_build", label: "Start Build" }, { transition: "archive", label: "Archive" }],
      building: [{ transition: "ready", label: "Mark Ready" }],
      ready_to_launch: [{ transition: "launch", label: "Launch Product" }],
      ready_for_review: [{ transition: "launch", label: "Launch Product" }],
      launched: [{ transition: "archive", label: "Archive" }],
      rejected: [{ transition: "archive", label: "Archive" }],
      archived: [],
    };

    const opportunities = state.opportunities.slice(0, 10).map((item) => `
      <article class="card row-item">
        <h4>${helpers.t(item.title, item.id)}</h4>
        <p><span class="badge ${helpers.badgeClass(item.status || item.decision)}">${helpers.t(item.status || item.decision, "pending")}</span>source: ${helpers.t(item.source, "-")}</p>
        <div class="card-actions">
          <button data-action="eval-opp" data-id="${item.id}">Evaluate Opportunity</button>
          <button data-action="dismiss-opp" data-id="${item.id}">Dismiss Opportunity</button>
        </div>
      </article>
    `).join("") || "<p class='empty'>No opportunities yet. Run a scan to discover new ideas.</p>";

    const proposals = state.proposals.slice(0, 10).map((item) => {
      const status = helpers.normalizeStatus(item.status);
      const actions = (transitionConfig[status] || []).map((action) => (
        `<button data-action="proposal" data-transition="${action.transition}" data-id="${item.id}">${action.label}</button>`
      )).join("");

      return `
        <article class="card row-item">
          <h4>${helpers.t(item.product_name, item.id)}</h4>
          <p>
            <span class="badge ${helpers.badgeClass(item.status)}">${helpers.statusLabel(item.status)}</span>
            confidence: ${helpers.t(item.confidence, "-")} · price: ${helpers.t(item.price_suggestion, "-")}
          </p>
          <div class="card-actions wrap">
            ${actions || "<span class='empty'>No lifecycle actions available.</span>"}
          </div>
        </article>
      `;
    }).join("") || "<p class='empty'>No proposals yet. Evaluate opportunities to create proposals.</p>";

    const builds = state.proposals
      .filter((item) => ["approved", "building", "ready_to_launch", "ready_for_review"].includes(helpers.normalizeStatus(item.status)))
      .slice(0, 10)
      .map((item) => `
        <article class="card row-item">
          <h4>${helpers.t(item.product_name, item.id)}</h4>
          <p><span class="badge ${helpers.badgeClass(item.status)}">${helpers.statusLabel(item.status)}</span> updated: ${helpers.t(item.updated_at, "-")}</p>
        </article>
      `).join("") || "<p class='empty'>No builds in progress. Move approved proposals to build.</p>";

    const launches = state.launches.slice(0, 10).map((item) => `
      <article class="card row-item">
        <h4>${helpers.t(item.product_name, item.id)}</h4>
        <p>
          <span class="badge ${helpers.badgeClass(item.status)}">${helpers.statusLabel(item.status || "queued")}</span>
          sales: ${helpers.t(item.metrics?.sales, 0)} · revenue: ${helpers.t(item.metrics?.revenue, 0)}
        </p>
        <div class="card-actions">
          <button data-action="launch-sale" data-id="${item.id}">Record Sale</button>
          <button data-action="launch-status" data-id="${item.id}">Update Status</button>
        </div>
      </article>
    `).join("") || "<p class='empty'>No launches yet. Launch a ready product to populate this section.</p>";

    this.shell("Work", "Execution pipeline with guided lifecycle", `
      <section class="stack work-stack">
        <article class="card pipeline-summary">
          <h3>Pipeline Summary</h3>
          <div class="pipeline-flow">
            <div class="pipeline-step"><span>Opportunities</span><strong>${opportunitiesCount}</strong></div>
            <div class="pipeline-arrow">→</div>
            <div class="pipeline-step"><span>Proposals</span><strong>${proposalsDraft} draft · ${proposalsReady} ready</strong></div>
            <div class="pipeline-arrow">→</div>
            <div class="pipeline-step"><span>Builds</span><strong>${buildsInProgress} in progress</strong></div>
            <div class="pipeline-arrow">→</div>
            <div class="pipeline-step"><span>Launched</span><strong>${launchedProducts}</strong></div>
          </div>
        </article>

        <article class="card recommendation-card">
          <h3>Recommended Action</h3>
          <h4>${recommendedAction.title}</h4>
          <p>${recommendedAction.body}</p>
          <div class="recommendation-cta">${recommendedAction.cta}</div>
        </article>

        <details class="card accordion" open>
          <summary>Opportunities <span class="helper">Validate market demand before proposing products.</span></summary>
          ${opportunities}
        </details>

        <details class="card accordion" open>
          <summary>Proposals <span class="helper">Convert ideas into decisions and move them through lifecycle gates.</span></summary>
          ${proposals}
        </details>

        <details class="card accordion" open>
          <summary>Builds <span class="helper">Track approved and actively built products.</span></summary>
          ${builds}
        </details>

        <details class="card accordion" open>
          <summary>Launches <span class="helper">Operate live products and monitor outcomes.</span></summary>
          ${launches}
        </details>

        <details class="card accordion">
          <summary>Performance <span class="helper">Review output signals to steer the next cycle.</span></summary>
          ${helpers.json(state.performance)}
        </details>

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
  if (!ui.pageNav) return;
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
  if (!ui.chatHistory) return;
  ui.chatHistory.innerHTML = state.logs
    .slice(-30)
    .map((entry) => `<div class="chat-row ${entry.role}">${helpers.escape(entry.message)}</div>`)
    .join("");
  ui.chatHistory.scrollTop = ui.chatHistory.scrollHeight;
}

function renderControlCenter() {
  if (!ui.statusText || !ui.statusDot || !ui.lastEvent || !ui.eventLog) return;
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
  if (!ui.telemetry) return;
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

    if (command === "scan" || command.includes("scan")) {
      const result = await api.fetchJson("/event", {
        method: "POST",
        body: JSON.stringify({ type: "RunInfoproductScan", payload: {} }),
      });
      log("system", `scan => ${JSON.stringify(result)}`);
      return refreshLoop();
    }

    if (command === "list opps" || command.includes("opportun")) {
      router.navigate("work");
      log("system", "Navigated to Work (opportunities visible).");
      return;
    }

    if (command === "list proposals" || command.includes("proposal")) {
      router.navigate("work");
      log("system", "Navigated to Work (proposals visible).");
      return;
    }

    if (command === "sync sales" || (command.includes("sync") && command.includes("sale"))) {
      const result = await api.fetchJson("/gumroad/sync_sales", {
        method: "POST",
        body: JSON.stringify({}),
      });
      log("system", `sync sales => ${JSON.stringify(result)}`);
      return refreshLoop();
    }

    log("system", "Unknown request. Try: 'scan for opportunities', 'show opportunities', 'show proposals', 'sync sales', or paste JSON.");
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

window.addEventListener("hashchange", () => router.render());

startRefreshLoop();
refreshLoop();
