const CONFIG = {
  routes: ["home", "dashboard", "work", "profile", "game", "strategy", "settings"],
  defaultRoute: "home",
  defaultRefreshMs: 3000,
  maxEventStream: 20,
};

const STORAGE_KEYS = {
  debug: "treta.debug",
  refreshMs: "treta.refreshMs",
  profile: "treta.profile",
};

const ACTION_TARGETS = {
  work: "work-response",
  strategy: "strategy-response",
  settings: "settings-response",
};

const state = {
  system: { state: "IDLE" },
  events: [],
  opportunities: [],
  proposals: [],
  launches: [],
  plans: [],
  performance: {},
  strategy: {},
  strategyView: {
    pendingActions: [],
    recommendation: {},
    autonomyStatus: {},
    adaptiveStatus: {},
    loading: false,
    loaded: false,
    error: "",
  },
  expandedTimelineEvents: {},
  debugMode: localStorage.getItem(STORAGE_KEYS.debug) === "true",
  refreshMs: Number(localStorage.getItem(STORAGE_KEYS.refreshMs) || CONFIG.defaultRefreshMs),
  profile: loadProfileState(),
  currentRoute: CONFIG.defaultRoute,
  workView: {
    messages: {},
    executionPackages: {},
    activeExecutionProposalId: "",
    plansByProposal: {},
    activePlanProposalId: "",
  },
  timerId: null,
};

const ui = {
  pageContent: document.getElementById("page-content"),
  pageNav: document.getElementById("page-nav"),
  chatForm: document.getElementById("chat-form"),
  chatInput: document.getElementById("chat-input"),
  systemStatusPanel: document.getElementById("system-status-panel"),
  activityTimelinePanel: document.getElementById("activity-timeline-panel"),
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
  getProductLaunch(id) {
    return this.fetchJson(`/product_launches/${id}`);
  },
  addLaunchSale(id, amount) {
    return this.fetchJson(`/product_launches/${id}/add_sale`, { method: "POST", body: JSON.stringify({ amount }) });
  },
  setLaunchStatus(id, status) {
    return this.fetchJson(`/product_launches/${id}/status`, { method: "POST", body: JSON.stringify({ status }) });
  },
  linkLaunchGumroad(id, gumroadProductId) {
    return this.fetchJson(`/product_launches/${id}/link_gumroad`, { method: "POST", body: JSON.stringify({ gumroad_product_id: gumroadProductId }) });
  },
  getProductPlans() {
    return this.fetchJson("/product_plans");
  },
  getProductPlan(id) {
    return this.fetchJson(`/product_plans/${id}`);
  },
  buildProductPlan(proposalId) {
    return this.fetchJson("/product_plans/build", { method: "POST", body: JSON.stringify({ proposal_id: proposalId }) });
  },
  executeProposal(id) {
    return this.fetchJson("/product_proposals/execute", { method: "POST", body: JSON.stringify({ id }) });
  },
  getPerformanceSummary() {
    return this.fetchJson("/performance/summary");
  },
  getStrategyRecommendations() {
    return this.fetchJson("/strategy/recommendations");
  },
  getPendingStrategyActions() {
    return this.fetchJson("/strategy/pending_actions");
  },
  executeStrategyAction(id) {
    return this.fetchJson(`/strategy/execute_action/${id}`, { method: "POST", body: JSON.stringify({}) });
  },
  rejectStrategyAction(id) {
    return this.fetchJson(`/strategy/reject_action/${id}`, { method: "POST", body: JSON.stringify({}) });
  },
  getAutonomyStatus() {
    return this.fetchJson("/autonomy/status");
  },
  getAutonomyAdaptiveStatus() {
    return this.fetchJson("/autonomy/adaptive_status");
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
  normalizeActionType(type) {
    return this.normalizeStatus(type).replaceAll("-", "_");
  },
  priorityBadgeClass(priority) {
    const value = this.normalizeStatus(priority);
    if (value === "high") return "error";
    if (value === "medium") return "warn";
    if (value === "low") return "ok";
    return "info";
  },
  strategyGroup(type) {
    const normalized = this.normalizeActionType(type);
    if (["scale", "new_product"].includes(normalized)) return "Growth";
    if (["review", "price_test"].includes(normalized)) return "Optimization";
    if (normalized.includes("risk") || normalized.includes("defense") || normalized.includes("defensive")) return "Defensive";
    return "Defensive";
  },
  actionImpactScore(action) {
    const value = Number(action?.expected_impact_score);
    return Number.isFinite(value) ? value : 0;
  },
  strategyHealthSummary(pendingActions) {
    const actions = pendingActions || [];
    const total = actions.length;
    const highPriorityCount = actions.filter((item) => this.normalizeStatus(item.priority) === "high").length;
    const mediumPriorityCount = actions.filter((item) => this.normalizeStatus(item.priority) === "medium").length;
    const lowPriorityCount = actions.filter((item) => this.normalizeStatus(item.priority) === "low").length;
    const autoExecutableCount = actions.filter((item) => Boolean(item.auto_executable)).length;
    const averageImpactScore = total
      ? actions.reduce((sum, item) => sum + this.actionImpactScore(item), 0) / total
      : 0;

    let status = "Stable";
    if (highPriorityCount > Math.max(mediumPriorityCount, lowPriorityCount)) {
      status = "Aggressive";
    } else if (mediumPriorityCount > highPriorityCount && mediumPriorityCount >= lowPriorityCount) {
      status = "Defensive";
    }

    return {
      total,
      highPriorityCount,
      autoExecutableCount,
      averageImpactScore,
      status,
    };
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
    if (state.currentRoute === "strategy") return views.loadStrategy();
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
    const transitionLabels = {
      approve: "Approve",
      reject: "Reject",
      start_build: "Move to Build",
      ready: "Mark Ready",
      launch: "Launch Product",
      archive: "Archive",
    };

    const transitionConfig = {
      draft: ["approve", "reject"],
      approved: ["start_build", "archive"],
      ready_to_review: ["launch", "archive"],
      ready_for_review: ["launch", "archive"],
      ready_to_launch: ["launch", "archive"],
      building: ["ready"],
      launched: ["archive"],
      rejected: ["archive"],
      archived: [],
    };

    const opportunityStatus = (item) => {
      const normalized = helpers.normalizeStatus(item.status || item.decision || "new");
      if (["evaluated", "evaluate"].includes(normalized)) return "EVALUATED";
      if (["dismissed", "dismiss"].includes(normalized)) return "DISMISSED";
      return "NEW";
    };

    const renderProposal = (item) => {
      const status = helpers.normalizeStatus(item.status);
      const actions = (transitionConfig[status] || []).map((transition) => (
        `<button class="secondary-btn" data-action="proposal" data-transition="${transition}" data-id="${item.id}">${transitionLabels[transition] || helpers.statusLabel(transition)}</button>`
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
    };

    const opportunities = state.opportunities.slice(0, 10).map((item) => {
      const status = opportunityStatus(item);
      return `
        <article class="card row-item">
          <h4>${helpers.t(item.title, item.id)}</h4>
          <p>
            <span class="badge ${helpers.badgeClass(status)}">${status}</span>
            source: ${helpers.t(item.source, "-")}
          </p>
          <div class="card-actions work-secondary-actions">
            <button class="secondary-btn" data-action="eval-opp" data-id="${item.id}">Evaluate</button>
            <button class="secondary-btn" data-action="dismiss-opp" data-id="${item.id}">Dismiss</button>
          </div>
        </article>
      `;
    }).join("") || "<p class='empty'>No opportunities yet. Run a scan to discover new ideas.</p>";

    const proposalGroups = [
      { key: "draft", title: "Draft" },
      { key: "ready_to_review", title: "Ready to Review", aliases: ["ready_for_review"] },
      { key: "ready_to_launch", title: "Ready to Launch" },
      { key: "building", title: "Building" },
    ].map((group) => {
      const statuses = [group.key, ...(group.aliases || [])];
      const cards = state.proposals
        .filter((item) => statuses.includes(helpers.normalizeStatus(item.status)))
        .slice(0, 10)
        .map(renderProposal)
        .join("") || `<p class='empty'>No proposals in ${group.title.toLowerCase()}.</p>`;

      return `
        <section class="work-status-group">
          <h4>${group.title}</h4>
          ${cards}
        </section>
      `;
    }).join("");

    const launchesRows = state.launches.slice(0, 20).map((item) => {
      const launchId = helpers.t(item.id, "-");
      const message = state.workView.messages[`launch-${launchId}`] || "";
      return `
        <tr>
          <td>${helpers.t(item.id)}</td>
          <td>${helpers.t(item.proposal_id)}</td>
          <td><span class="badge ${helpers.badgeClass(item.status)}">${helpers.statusLabel(item.status)}</span></td>
          <td>${helpers.t(item.sales, 0)}</td>
          <td>${helpers.t(item.revenue, 0)}</td>
          <td>${helpers.t(item.gumroad_product_id)}</td>
          <td>${helpers.t(item.last_synced_at)}</td>
          <td>
            <div class="inline-form-grid launch-actions-inline">
              <div class="inline-control-group">
                <label>Amount</label>
                <input type="number" step="0.01" min="0" data-launch-input="sale" data-id="${helpers.t(item.id)}" placeholder="0.00">
                <button class="secondary-btn" data-action="launch-add-sale" data-id="${helpers.t(item.id)}">Add sale</button>
              </div>
              <div class="inline-control-group">
                <label>Status</label>
                <select data-launch-input="status" data-id="${helpers.t(item.id)}">
                  <option value="active">Active</option>
                  <option value="paused">Paused</option>
                  <option value="launched">Launched</option>
                  <option value="archived">Archived</option>
                </select>
                <button class="secondary-btn" data-action="launch-set-status" data-id="${helpers.t(item.id)}">Set status</button>
              </div>
              <div class="inline-control-group">
                <label>Gumroad Product</label>
                <input type="text" data-launch-input="gumroad" data-id="${helpers.t(item.id)}" placeholder="gumroad_product_id" value="${helpers.t(item.gumroad_product_id, "")}">
                <button class="secondary-btn" data-action="launch-link-gumroad" data-id="${helpers.t(item.id)}">Link Gumroad</button>
              </div>
            </div>
            <p class="inline-feedback">${helpers.escape(message)}</p>
          </td>
        </tr>
      `;
    }).join("") || "<tr><td colspan='8' class='empty'>No launches yet.</td></tr>";

    const proposalActionRows = state.proposals.slice(0, 20).map((proposal) => {
      const proposalId = helpers.t(proposal.id);
      const plan = state.plans.find((item) => String(item.proposal_id) === String(proposal.id));
      const planId = plan?.id;
      const planMsg = state.workView.messages[`plan-${proposalId}`] || "";
      const executeMsg = state.workView.messages[`exec-${proposalId}`] || "";
      return `
        <tr>
          <td>${proposalId}</td>
          <td>${helpers.t(proposal.product_name, "-")}</td>
          <td><span class="badge ${helpers.badgeClass(proposal.status)}">${helpers.statusLabel(proposal.status)}</span></td>
          <td>
            <div class="card-actions wrap no-margin">
              <button class="secondary-btn" data-action="generate-execution-package" data-id="${proposalId}">Generate execution package</button>
              ${state.workView.executionPackages[proposalId] ? `<button class="secondary-btn" data-action="show-execution-package" data-id="${proposalId}">Preview package</button>` : ""}
            </div>
            <p class="inline-feedback">${helpers.escape(executeMsg)}</p>
          </td>
          <td>
            <div class="card-actions wrap no-margin">
              <button class="secondary-btn" data-action="build-plan" data-id="${proposalId}">Build plan</button>
              <button class="secondary-btn" data-action="view-plan" data-id="${proposalId}" data-plan-id="${helpers.t(planId, "")}">View plan</button>
            </div>
            <p class="inline-feedback">${helpers.escape(planMsg)}</p>
          </td>
        </tr>
      `;
    }).join("") || "<tr><td colspan='5' class='empty'>No proposals available for execution/plans.</td></tr>";

    const selectedExecutionId = state.workView.activeExecutionProposalId;
    const selectedExecutionPackage = state.workView.executionPackages[selectedExecutionId] || null;
    const selectedPlanId = state.workView.activePlanProposalId;
    const selectedPlan = state.workView.plansByProposal[selectedPlanId] || null;

    this.shell("Work", "Execution pipeline with guided lifecycle", `
      <section class="work-execution">
        <article class="card work-section">
          <header class="work-section-header">
            <h3>Opportunities</h3>
            <p class="muted-note">New market signals detected. Evaluate or dismiss before generating products.</p>
          </header>
          ${opportunities}
        </article>

        <article class="card work-section">
          <header class="work-section-header">
            <h3>Product Proposals</h3>
            <p class="muted-note">Validated product concepts ready for build, launch, or archive.</p>
          </header>
          <div class="work-proposals-grid">
            ${proposalGroups}
          </div>
        </article>

        <article class="card work-section">
          <header class="work-section-header">
            <h3>Build &amp; Execution</h3>
            <p class="muted-note">Manage product plans and generate execution packages.</p>
          </header>
          <div class="work-table-wrap">
            <table class="work-table">
              <thead>
                <tr>
                  <th>Proposal ID</th>
                  <th>Product</th>
                  <th>Status</th>
                  <th>Execution package</th>
                  <th>Plans</th>
                </tr>
              </thead>
              <tbody>${proposalActionRows}</tbody>
            </table>
          </div>
          <div class="work-preview-grid">
            <section class="work-preview-panel">
              <h3>Execution Package Preview</h3>
              ${renderExecutionPackagePreview(selectedExecutionId, selectedExecutionPackage)}
            </section>
            <section class="work-preview-panel">
              <h3>Product Plan Viewer</h3>
              ${renderPlanPreview(selectedPlanId, selectedPlan)}
            </section>
          </div>
        </article>

        <article class="card work-section">
          <header class="work-section-header">
            <h3>Launches</h3>
            <p class="muted-note">Live products and revenue tracking.</p>
          </header>
          <div class="work-table-wrap">
            <table class="work-table work-launch-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Proposal</th>
                  <th>Status</th>
                  <th>Sales</th>
                  <th>Revenue</th>
                  <th>Gumroad Product</th>
                  <th>Last synced</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>${launchesRows}</tbody>
            </table>
          </div>
        </article>

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

  loadStrategy() {
    const strategyView = state.strategyView;
    const pendingActions = strategyView.pendingActions || [];
    const recommendation = strategyView.recommendation || {};
    const autonomyStatus = strategyView.autonomyStatus || {};
    const adaptiveStatus = strategyView.adaptiveStatus || {};

    const numberOrNull = (value) => {
      const normalized = typeof value === "string" ? value.replace("%", "") : value;
      const parsed = Number.parseFloat(normalized);
      return Number.isFinite(parsed) ? parsed : null;
    };

    const renderAutonomyStabilityBadge = () => {
      const successRate = numberOrNull(adaptiveStatus.success_rate ?? adaptiveStatus.current_success_rate ?? autonomyStatus.success_rate);
      const threshold = numberOrNull(adaptiveStatus.impact_threshold ?? autonomyStatus.impact_threshold);

      if (successRate === null || threshold === null) {
        return '<span class="badge info">Learning</span>';
      }

      if (successRate > threshold) {
        return '<span class="badge ok">Stable</span>';
      }

      if (successRate >= threshold - 0.05) {
        return '<span class="badge warn">Learning</span>';
      }

      return '<span class="badge error">Risk</span>';
    };

    const renderActionQueue = () => {
      if (strategyView.loading) return "<p class='empty'>Loading pending actions…</p>";
      if (!pendingActions.length) return "<p class='empty'>No pending actions right now. Queue is clear.</p>";

      return `
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Action name</th>
                <th>Priority</th>
                <th>Risk</th>
                <th>Expected impact</th>
                <th>Auto executable</th>
                <th>Controls</th>
              </tr>
            </thead>
            <tbody>
              ${pendingActions.map((item) => `
                <tr>
                  <td>${helpers.escape(helpers.t(item.title || item.name, item.id))}</td>
                  <td><span class="badge ${helpers.priorityBadgeClass(item.priority)}">${helpers.t(item.priority, "unknown")}</span></td>
                  <td><span class="badge ${helpers.badgeClass(item.risk_level)}">${helpers.t(item.risk_level, "unknown")}</span></td>
                  <td>${helpers.escape(helpers.t(item.expected_impact || item.expected_impact_score, "Not specified"))}</td>
                  <td>${item.auto_executable ? '<span class="badge ok">Auto</span>' : '<span class="badge info">Manual</span>'}</td>
                  <td>
                    <div class="card-actions wrap">
                      <button data-action="strategy-execute" data-id="${item.id}">Execute</button>
                      <button class="secondary-btn" data-action="strategy-reject" data-id="${item.id}">Reject</button>
                    </div>
                  </td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      `;
    };

    const strategyError = strategyView.error ? `<p class="empty">${helpers.escape(strategyView.error)}</p>` : "";

    this.shell("Strategy", "Strategic Control Layer", `
      <section class="stack">
        <article class="card strategy-health-card">
          <h3>Strategic Situation</h3>
          <p class="empty">A concise executive snapshot from the latest recommendation engine output.</p>
          <p>
            <span class="badge ${helpers.priorityBadgeClass(recommendation.priority_level)}">Priority ${helpers.t(recommendation.priority_level, "Unknown")}</span>
            <span class="badge ${recommendation.auto_executable ? "ok" : "info"}">${recommendation.auto_executable ? "Auto Executable" : "Manual Review"}</span>
          </p>
          <section class="card-grid cols-2">
            <div class="metric"><span>Focus area</span><strong>${helpers.t(recommendation.focus_area || recommendation.focus, "No focus area available")}</strong></div>
            <div class="metric"><span>Risk level</span><strong>${helpers.t(recommendation.risk_level, "Risk not specified")}</strong></div>
            <div class="metric"><span>Recommended next move</span><strong>${helpers.t(recommendation.suggested_next_move || recommendation.next_move, "No recommended move yet")}</strong></div>
            <div class="metric"><span>Summary</span><strong>${helpers.t(recommendation.summary_text || recommendation.summary, "No summary available")}</strong></div>
          </section>
        </article>

        <article class="card">
          <h3>Action Queue</h3>
          ${strategyError}
          ${renderActionQueue()}
          <section id="strategy-response" class="result-box">Ready.</section>
        </article>

        <article class="card">
          <h3>Autonomy Engine</h3>
          <p>
            <strong>Derived status:</strong>
            ${renderAutonomyStabilityBadge()}
          </p>
          <section class="card-grid cols-2">
            <div class="metric"><span>Current mode</span><strong>${helpers.t(autonomyStatus.mode || autonomyStatus.autonomy_mode, "Unknown mode")}</strong></div>
            <div class="metric"><span>Success rate</span><strong>${helpers.t(adaptiveStatus.success_rate || adaptiveStatus.current_success_rate || autonomyStatus.success_rate, "No data")}</strong></div>
            <div class="metric"><span>Max auto executions/day</span><strong>${helpers.t(autonomyStatus.max_auto_executions_per_day)}</strong></div>
            <div class="metric"><span>Impact threshold</span><strong>${helpers.t(adaptiveStatus.impact_threshold || autonomyStatus.impact_threshold, "No threshold")}</strong></div>
            <div class="metric"><span>Executions today</span><strong>${helpers.t(autonomyStatus.executions_today || autonomyStatus.auto_executions_today || adaptiveStatus.executions_today, "Not available")}</strong></div>
          </section>
        </article>
      </section>
    `);

    bindStrategyActions();
    if (!strategyView.loading && !strategyView.loaded) {
      loadStrategyData();
    }
  },
};

async function loadStrategyData() {
  state.strategyView.loading = true;
  state.strategyView.error = "";
  if (state.currentRoute === "strategy") router.render();
  try {
    const [pendingData, recommendationData, autonomyData, adaptiveData] = await Promise.all([
      api.getPendingStrategyActions(),
      api.getStrategyRecommendations(),
      api.getAutonomyStatus(),
      api.getAutonomyAdaptiveStatus(),
    ]);

    state.strategyView.pendingActions = pendingData.items || pendingData.actions || pendingData.pending_actions || [];
    state.strategyView.recommendation = recommendationData || {};
    state.strategyView.autonomyStatus = autonomyData || {};
    state.strategyView.adaptiveStatus = adaptiveData || {};
  } catch (error) {
    state.strategyView.error = `strategy data error: ${error.message}`;
    log("system", state.strategyView.error);
  } finally {
    state.strategyView.loading = false;
    state.strategyView.loaded = true;
    if (state.currentRoute === "strategy") router.render();
  }
}

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
  console.info(`[${role}] ${message}`);
}

function mapSystemMode(rawState) {
  const value = helpers.t(rawState, "IDLE").toUpperCase();
  if (value === "IDLE") return { label: "IDLE", className: "mode-idle" };
  if (["LISTENING", "THINKING"].includes(value)) return { label: "SCANNING", className: "mode-scanning" };
  if (value === "SPEAKING") return { label: "BUILDING", className: "mode-building" };
  if (value === "ERROR") return { label: "ERROR", className: "mode-error" };
  return { label: value, className: "mode-idle" };
}

function formatEventTitle(type) {
  if (!type) return "System event";
  const knownTitles = {
    RunInfoproductScan: "Infoproduct scan started",
    OpportunityDetected: "Opportunity detected",
    ProductProposalGenerated: "Proposal generated",
    ProductLaunchCreated: "Launch created",
    StrategyActionCreated: "Strategy action created",
  };
  if (knownTitles[type]) return knownTitles[type];
  return type.replace(/([a-z])([A-Z])/g, "$1 $2");
}

function eventIcon(type) {
  const knownIcons = {
    RunInfoproductScan: "🔍",
    OpportunityDetected: "💡",
    ProductProposalGenerated: "📦",
    ProductLaunchCreated: "🚀",
    StrategyActionCreated: "🧠",
  };
  return knownIcons[type] || "⚙";
}

function eventKey(event, index) {
  return `${helpers.t(event.timestamp, "no-time")}-${helpers.t(event.type, "event")}-${index}`;
}

function renderSystemStatus() {
  const mode = mapSystemMode(state.system.state);
  const latestEvent = state.events[0];
  const lastAction = latestEvent ? formatEventTitle(latestEvent.type) : "No events yet";

  ui.systemStatusPanel.innerHTML = `
    <h2>System Status</h2>
    <div class="system-mode-row">
      <span class="status-dot ${mode.className}" aria-hidden="true"></span>
      <span class="mode-label">SYSTEM MODE</span>
    </div>
    <div class="system-status-lines">
      <p><span>Current Mode:</span> <strong>${helpers.escape(mode.label)}</strong></p>
      <p><span>Last Action:</span> <strong>${helpers.escape(lastAction)}</strong></p>
    </div>
  `;
}

function renderActivityTimeline() {
  const timelineItems = state.events.slice(0, CONFIG.maxEventStream);
  if (!timelineItems.length) {
    ui.activityTimelinePanel.innerHTML = "<h2>Activity Timeline</h2><p class='empty'>Waiting for events…</p>";
    return;
  }

  ui.activityTimelinePanel.innerHTML = `
    <h2>Activity Timeline</h2>
    <div class="activity-timeline-list">
      ${timelineItems
        .map((event, index) => {
          const key = eventKey(event, index);
          const expanded = Boolean(state.expandedTimelineEvents[key]);
          return `
            <article class="timeline-item ${expanded ? "expanded" : ""}" data-event-key="${helpers.escape(key)}">
              <button class="timeline-item-toggle" type="button" data-action="toggle-event" data-event-key="${helpers.escape(key)}">
                <span class="timeline-icon" aria-hidden="true">${eventIcon(event.type)}</span>
                <span class="timeline-main">
                  <strong>${helpers.escape(formatEventTitle(event.type))}</strong>
                  <small>${helpers.escape(helpers.t(event.timestamp, "Unknown time"))}</small>
                </span>
              </button>
              ${expanded ? `<pre class="timeline-payload">${helpers.escape(JSON.stringify(event.payload || {}, null, 2))}</pre>` : ""}
            </article>
          `;
        })
        .join("")}
    </div>
  `;

  ui.activityTimelinePanel.querySelectorAll("button[data-action='toggle-event']").forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.dataset.eventKey;
      state.expandedTimelineEvents[key] = !state.expandedTimelineEvents[key];
      renderActivityTimeline();
    });
  });
}

function renderCommandBar() {
  if (!ui.chatForm) return;
  ui.chatForm.classList.add("quick-command-bar");
}

function renderControlCenter() {
  renderSystemStatus();
  renderActivityTimeline();
  renderCommandBar();
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
    const [systemData, eventData, oppData, proposalData, launchData, planData, perfData, strategyData] = await Promise.all([
      api.getState(),
      api.getRecentEvents(),
      api.getOpportunities(),
      api.getProductProposals(),
      api.getProductLaunches(),
      api.getProductPlans(),
      api.getPerformanceSummary(),
      api.getStrategyRecommendations(),
    ]);

    state.system = systemData || { state: "IDLE" };
    state.events = eventData.events || [];
    state.opportunities = oppData.items || [];
    state.proposals = proposalData.items || [];
    state.launches = launchData.items || [];
    state.plans = planData.items || [];
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

  ui.pageContent.querySelectorAll("button[data-action='launch-add-sale']").forEach((button) => {
    button.addEventListener("click", async () => {
      const input = ui.pageContent.querySelector(`input[data-launch-input='sale'][data-id='${button.dataset.id}']`);
      const amount = Number(input?.value || "0");
      await runWorkInlineAction(
        `launch-${button.dataset.id}`,
        () => api.addLaunchSale(button.dataset.id, amount),
        `Sale added to launch ${button.dataset.id}.`
      );
    });
  });

  ui.pageContent.querySelectorAll("button[data-action='launch-set-status']").forEach((button) => {
    button.addEventListener("click", async () => {
      const input = ui.pageContent.querySelector(`select[data-launch-input='status'][data-id='${button.dataset.id}']`);
      const status = helpers.t(input?.value, "active");
      await runWorkInlineAction(
        `launch-${button.dataset.id}`,
        () => api.setLaunchStatus(button.dataset.id, status),
        `Launch ${button.dataset.id} status updated to ${status}.`
      );
    });
  });

  ui.pageContent.querySelectorAll("button[data-action='launch-link-gumroad']").forEach((button) => {
    button.addEventListener("click", async () => {
      const input = ui.pageContent.querySelector(`input[data-launch-input='gumroad'][data-id='${button.dataset.id}']`);
      const gumroadProductId = helpers.t(input?.value, "").trim();
      await runWorkInlineAction(
        `launch-${button.dataset.id}`,
        () => api.linkLaunchGumroad(button.dataset.id, gumroadProductId),
        `Launch ${button.dataset.id} linked to Gumroad product ${gumroadProductId || "-"}.`
      );
    });
  });

  ui.pageContent.querySelectorAll("button[data-action='generate-execution-package']").forEach((button) => {
    button.addEventListener("click", async () => {
      await runWorkInlineAction(
        `exec-${button.dataset.id}`,
        async () => {
          const result = await api.executeProposal(button.dataset.id);
          state.workView.executionPackages[button.dataset.id] = result.execution_package || result;
          state.workView.activeExecutionProposalId = button.dataset.id;
          return result;
        },
        `Execution package generated for proposal ${button.dataset.id}.`
      );
    });
  });

  ui.pageContent.querySelectorAll("button[data-action='show-execution-package']").forEach((button) => {
    button.addEventListener("click", () => {
      state.workView.activeExecutionProposalId = button.dataset.id;
      router.render();
    });
  });

  ui.pageContent.querySelectorAll("button[data-action='copy-package-block']").forEach((button) => {
    button.addEventListener("click", async () => {
      const raw = decodeURIComponent(button.dataset.copyValue || "");
      try {
        await navigator.clipboard.writeText(raw);
        state.workView.messages[`exec-${button.dataset.id}`] = "Copied to clipboard.";
      } catch (_error) {
        state.workView.messages[`exec-${button.dataset.id}`] = "Clipboard unavailable in this environment.";
      }
      router.render();
    });
  });

  ui.pageContent.querySelectorAll("button[data-action='build-plan']").forEach((button) => {
    button.addEventListener("click", async () => {
      await runWorkInlineAction(
        `plan-${button.dataset.id}`,
        async () => {
          const result = await api.buildProductPlan(button.dataset.id);
          await refreshLoop();
          const builtPlanId = result.id || result.plan_id;
          if (builtPlanId) {
            const planDetails = await api.getProductPlan(builtPlanId);
            state.workView.plansByProposal[button.dataset.id] = planDetails;
            state.workView.activePlanProposalId = button.dataset.id;
          }
          return result;
        },
        `Plan built for proposal ${button.dataset.id}.`
      );
    });
  });

  ui.pageContent.querySelectorAll("button[data-action='view-plan']").forEach((button) => {
    button.addEventListener("click", async () => {
      const proposalId = button.dataset.id;
      const fromList = state.plans.find((item) => String(item.proposal_id) === String(proposalId));
      const planId = button.dataset.planId || fromList?.id;
      if (!planId) {
        state.workView.activePlanProposalId = proposalId;
        state.workView.plansByProposal[proposalId] = null;
        state.workView.messages[`plan-${proposalId}`] = "No plan yet.";
        router.render();
        return;
      }
      await runWorkInlineAction(
        `plan-${proposalId}`,
        async () => {
          const result = await api.getProductPlan(planId);
          state.workView.activePlanProposalId = proposalId;
          state.workView.plansByProposal[proposalId] = result;
          return result;
        },
        `Plan ${planId} loaded.`
      );
    });
  });
}

async function runWorkInlineAction(key, actionFn, successMessage) {
  try {
    const result = await actionFn();
    state.workView.messages[key] = successMessage;
    document.getElementById(ACTION_TARGETS.work).textContent = JSON.stringify(result, null, 2);
    log("system", `Action ok: ${JSON.stringify(result)}`);
    await refreshLoop();
  } catch (error) {
    state.workView.messages[key] = `Error: ${error.message}`;
    document.getElementById(ACTION_TARGETS.work).textContent = `error: ${error.message}`;
    log("system", `Action failed: ${error.message}`);
    router.render();
  }
}

function renderExecutionPackagePreview(proposalId, executionPackage) {
  if (!proposalId || !executionPackage) {
    return "<p class='empty'>Generate an execution package from a proposal to preview copy blocks.</p>";
  }

  const redditPost = executionPackage.reddit_post || {};
  const launchSteps = Array.isArray(executionPackage.launch_steps) ? executionPackage.launch_steps : [];
  const sections = [
    { label: "Reddit title", value: helpers.t(redditPost.title, "No reddit title") },
    { label: "Reddit body", value: helpers.t(redditPost.body, "No reddit body") },
    { label: "Gumroad description", value: helpers.t(executionPackage.gumroad_description, "No description") },
    { label: "Short pitch", value: helpers.t(executionPackage.short_pitch, "No short pitch") },
    { label: "Pricing strategy", value: helpers.t(executionPackage.pricing_strategy, "No pricing strategy") },
    { label: "Launch steps", value: launchSteps.length ? launchSteps.map((step) => `• ${step}`).join("\n") : "No launch steps" },
  ];

  return `
    <p class="muted-note">Previewing proposal: <strong>${helpers.escape(proposalId)}</strong></p>
    <div class="work-copy-grid">
      ${sections.map((section) => `
        <article class="copy-block">
          <header>
            <h4>${section.label}</h4>
            <button class="secondary-btn" data-action="copy-package-block" data-id="${helpers.escape(proposalId)}" data-copy-value="${encodeURIComponent(section.value)}">Copy</button>
          </header>
          <pre>${helpers.escape(section.value)}</pre>
        </article>
      `).join("")}
    </div>
  `;
}

function renderPlanPreview(proposalId, plan) {
  if (!proposalId) return "<p class='empty'>Select “View plan” on any proposal to load plan details.</p>";
  if (!plan) return `<p class='empty'>No plan yet for proposal ${helpers.escape(proposalId)}.</p>`;

  const renderList = (items) => {
    if (!Array.isArray(items) || items.length === 0) return "<p class='empty'>No entries.</p>";
    return `<ul>${items.map((item) => `<li>${helpers.escape(item)}</li>`).join("")}</ul>`;
  };

  return `
    <p class="muted-note">Plan for proposal: <strong>${helpers.escape(proposalId)}</strong></p>
    <div class="plan-grid">
      <section>
        <h4>Outline</h4>
        <pre>${helpers.escape(helpers.t(plan.outline, "No outline"))}</pre>
      </section>
      <section>
        <h4>Deliverables</h4>
        ${renderList(plan.deliverables)}
      </section>
      <section>
        <h4>Build steps</h4>
        ${renderList(plan.build_steps)}
      </section>
      <section>
        <h4>Launch plan</h4>
        ${renderList(plan.launch_plan)}
      </section>
    </div>
  `;
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

function bindStrategyActions() {
  ui.pageContent.querySelectorAll("button[data-action='strategy-execute']").forEach((button) => {
    button.addEventListener("click", async () => {
      await runAction(() => api.executeStrategyAction(button.dataset.id), ACTION_TARGETS.strategy);
      await loadStrategyData();
    });
  });

  ui.pageContent.querySelectorAll("button[data-action='strategy-reject']").forEach((button) => {
    button.addEventListener("click", async () => {
      await runAction(() => api.rejectStrategyAction(button.dataset.id), ACTION_TARGETS.strategy);
      await loadStrategyData();
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
