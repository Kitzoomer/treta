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
    renderNavigation();
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
    ui.pageContent.innerHTML = `
      <section class="home-identity" aria-label="Treta identity">
        <h1 class="treta-title" aria-label="TRETA">
          <span class="treta-title-text">TRETA</span>
          <span class="treta-wave" aria-hidden="true"></span>
        </h1>
      </section>
    `;
  },

  loadDashboard() {
    const proposalsByStatus = state.proposals.reduce((acc, item) => {
      const status = helpers.normalizeStatus(item.status);
      acc[status] = (acc[status] || 0) + 1;
      return acc;
    }, {});

    const opportunitiesCount = state.opportunities.length;
    const buildsCount = state.proposals.filter((item) => ["approved", "building", "ready_to_launch", "ready_for_review"].includes(helpers.normalizeStatus(item.status))).length;
    const activeLaunches = state.launches.filter((item) => helpers.normalizeStatus(item.status) === "active").length;
    const readyToLaunch = (proposalsByStatus.ready_to_launch || 0) + (proposalsByStatus.ready_for_review || 0);
    const draftCount = proposalsByStatus.draft || 0;
    const approvedCount = proposalsByStatus.approved || 0;
    const buildsInProgress = proposalsByStatus.building || 0;
    const scanningCount = draftCount + (proposalsByStatus.ready_for_review || 0);

    const systemMode = (() => {
      if (activeLaunches > 0) return "LAUNCHING";
      if (approvedCount > 0 || buildsInProgress > 0) return "BUILDING";
      if (scanningCount > 0) return "SCANNING";
      return "IDLE";
    })();

    const primaryAction = (() => {
      if (opportunitiesCount === 0) {
        return {
          key: "scan",
          buttonLabel: "Run Opportunity Scan",
        };
      }
      if (draftCount > 0) {
        return {
          key: "review",
          buttonLabel: "Review Drafts",
        };
      }
      if (approvedCount > 0) {
        return {
          key: "start-build",
          buttonLabel: "Start Build",
        };
      }
      if (readyToLaunch > 0) {
        return {
          key: "launch",
          buttonLabel: "Launch Product",
        };
      }
      return {
        key: "scan",
        buttonLabel: "Run Opportunity Scan",
      };
    })();

    const strategicFocus = (() => {
      if (activeLaunches > 0) return "Monitoring live launches.";
      if (buildsInProgress > 0 || readyToLaunch > 0) return "Shipping current builds.";
      if (draftCount > 0) return "Converting drafts into products.";
      return "Acquiring new opportunities.";
    })();

    const systemHealth = (() => {
      if (opportunitiesCount === 0 && draftCount === 0 && buildsCount === 0) {
        return { label: "Critical", tone: "error" };
      }
      if (draftCount > 0 && buildsCount === 0) {
        return { label: "Attention Needed", tone: "warn" };
      }
      return { label: "Healthy", tone: "ok" };
    })();

    const modeHelper = (() => {
      if (systemMode === "LAUNCHING") return "Launches are active and being monitored.";
      if (systemMode === "BUILDING") return "Products are moving through build execution.";
      if (systemMode === "SCANNING") return "Opportunity discovery and proposal review are in progress.";
      return "No active pipeline movement detected.";
    })();

    this.shell("Dashboard", "Operational summary and next best action", `
      <section class="os-dashboard">
        <article class="card os-system-mode">
          <h3>System Mode</h3>
          <div class="system-mode-badge ${helpers.badgeClass(systemMode)}">${systemMode}</div>
          <p class="system-mode-helper">${modeHelper}</p>
        </article>

        <article class="card os-primary-action">
          <h3>Primary Action</h3>
          <button class="primary-action-btn" data-action="dashboard-primary" data-primary-action="${primaryAction.key}">${primaryAction.buttonLabel}</button>
          <p>Treta recommends this as your next highest-leverage action.</p>
        </article>

        <article class="card os-strategic-focus">
          <h3>Strategic Focus</h3>
          <p>${strategicFocus}</p>
        </article>

        <article class="card os-system-health">
          <span>System Health:</span>
          <span class="badge ${systemHealth.tone}">${systemHealth.label}</span>
        </article>

        <section class="os-key-metrics">
          <article class="card">
            <h3>Opportunities</h3>
            <div class="metric"><strong>${opportunitiesCount}</strong></div>
          </article>
          <article class="card">
            <h3>Draft Proposals</h3>
            <div class="metric"><strong>${draftCount}</strong></div>
          </article>
          <article class="card">
            <h3>Active Builds</h3>
            <div class="metric"><strong>${buildsCount}</strong></div>
          </article>
          <article class="card">
            <h3>Total Revenue</h3>
            <div class="metric"><strong>${helpers.t(state.performance.total_revenue, 0)}</strong></div>
          </article>
        </section>
      </section>
    `);
    bindDashboardActions();
  },

  loadWork() {
    const opportunitiesCount = state.opportunities.length;
    const proposalStatuses = state.proposals.reduce((acc, item) => {
      const status = helpers.normalizeStatus(item.status);
      acc[status] = (acc[status] || 0) + 1;
      return acc;
    }, {});
    const proposalsDraft = proposalStatuses.draft || 0;
    const buildsInProgress = proposalStatuses.building || 0;
    const launchedProducts = state.launches.filter((item) => helpers.normalizeStatus(item.status) === "launched").length;

    const transitionConfig = {
      draft: [{ transition: "approve", label: "Edit" }, { transition: "reject", label: "Dismiss" }],
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
        <div class="card-actions work-secondary-actions">
          <button class="secondary-btn" data-action="eval-opp" data-id="${item.id}">Evaluate</button>
          <button class="secondary-btn" data-action="dismiss-opp" data-id="${item.id}">Dismiss</button>
        </div>
      </article>
    `).join("") || "<p class='empty'>No opportunities yet. Run a scan to discover new ideas.</p>";

    const activeReadyProposals = state.proposals
      .filter((item) => helpers.normalizeStatus(item.status) === "ready")
      .slice(0, 10)
      .map((item) => `
        <article class="card row-item">
          <h4>${helpers.t(item.product_name, item.id)}</h4>
          <p>
            <span class="badge ${helpers.badgeClass(item.status)}">${helpers.statusLabel(item.status)}</span>
          </p>
          <div class="card-actions">
            <button data-action="proposal" data-transition="launch" data-id="${item.id}">Launch Product</button>
          </div>
        </article>
      `).join("") || "<p class='empty'>No ready proposals in execution.</p>";

    const activeBuilds = state.proposals
      .filter((item) => helpers.normalizeStatus(item.status) === "building")
      .slice(0, 10)
      .map((item) => `
        <article class="card row-item">
          <h4>${helpers.t(item.product_name, item.id)}</h4>
          <p><span class="badge ${helpers.badgeClass(item.status)}">${helpers.statusLabel(item.status)}</span></p>
          <div class="card-actions">
            <button data-action="proposal" data-transition="ready" data-id="${item.id}">Mark Ready</button>
          </div>
        </article>
      `).join("") || "<p class='empty'>No builds in progress.</p>";

    const activeReadyToLaunch = state.proposals
      .filter((item) => helpers.normalizeStatus(item.status) === "ready_to_launch")
      .slice(0, 10)
      .map((item) => `
        <article class="card row-item">
          <h4>${helpers.t(item.product_name, item.id)}</h4>
          <p><span class="badge ${helpers.badgeClass(item.status)}">${helpers.statusLabel(item.status)}</span></p>
          <div class="card-actions">
            <button data-action="proposal" data-transition="launch" data-id="${item.id}">Launch Product</button>
          </div>
        </article>
      `).join("") || "<p class='empty'>No products ready to launch.</p>";

    const draftProposals = state.proposals.filter((item) => helpers.normalizeStatus(item.status) === "draft").slice(0, 10).map((item) => {
      const status = helpers.normalizeStatus(item.status);
      const actions = (transitionConfig[status] || []).map((action) => (
        `<button class="secondary-btn" data-action="proposal" data-transition="${action.transition}" data-id="${item.id}">${action.label}</button>`
      )).join("");

      return `
        <article class="card row-item">
          <h4>${helpers.t(item.product_name, item.id)}</h4>
          <p>
            <span class="badge ${helpers.badgeClass(item.status)}">${helpers.statusLabel(item.status)}</span>
            confidence: ${helpers.t(item.confidence, "-")} · price: ${helpers.t(item.price_suggestion, "-")}
          </p>
          <div class="card-actions wrap work-secondary-actions">
            ${actions || "<span class='empty'>No lifecycle actions available.</span>"}
          </div>
        </article>
      `;
    }).join("") || "<p class='empty'>No proposals yet. Evaluate opportunities to create proposals.</p>";

    this.shell("Work", "Execution pipeline with guided lifecycle", `
      <section class="work-execution">
        <div class="card work-pipeline-overview">
          <div class="pipeline-step"><span>Opportunities</span><strong>${opportunitiesCount}</strong></div>
          <div class="pipeline-step"><span>Drafts</span><strong>${proposalsDraft}</strong></div>
          <div class="pipeline-step"><span>Building</span><strong>${buildsInProgress}</strong></div>
          <div class="pipeline-step"><span>Launched</span><strong>${launchedProducts}</strong></div>
        </div>

        <div class="work-active-execution">
          <article class="card">
            <h3>Ready Proposals</h3>
            ${activeReadyProposals}
          </article>

          <article class="card">
            <h3>Builds In Progress</h3>
            ${activeBuilds}
          </article>

          <article class="card">
            <h3>Products Ready to Launch</h3>
            ${activeReadyToLaunch}
          </article>
        </div>

        <div class="work-backlog card">
          <h3>Backlog</h3>
          <section>
            <h4>New Opportunities</h4>
            ${opportunities}
          </section>
          <section>
            <h4>Draft Proposals</h4>
            ${draftProposals}
          </section>
        </div>

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

function bindDashboardActions() {
  ui.pageContent.querySelectorAll("button[data-action='dashboard-primary']").forEach((button) => {
    button.addEventListener("click", async () => {
      const action = button.dataset.primaryAction;
      if (action === "scan") {
        await runAction(
          () => api.fetchJson("/event", { method: "POST", body: JSON.stringify({ type: "RunInfoproductScan", payload: {} }) }),
          ACTION_TARGETS.work
        );
        return;
      }

      if (["review", "start-build", "launch"].includes(action)) {
        router.navigate("work");
        log("system", "Navigated to Work to complete the recommended action.");
      }
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
