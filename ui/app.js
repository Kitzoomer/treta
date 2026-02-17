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
  autonomyEnabled: "treta_autonomy_enabled",
  chatMode: "treta_chat_mode",
};

const ACTION_TARGETS = {
  work: "work-response",
  strategy: "strategy-response",
  settings: "settings-response",
};

const state = {
  system: { state: "IDLE" },
  events: [],
  chatHistory: [],
  chatCards: [],
  opportunities: [],
  proposals: [],
  launches: [],
  plans: [],
  performance: {},
  strategy: {},
  strategyPendingActions: [],
  dailyLoop: {
    phase: "IDLE",
    summary: "System operating normally.",
    next_action_label: "No Immediate Action",
    route: null,
    timestamp: null,
  },
  strategyView: {
    pendingActions: [],
    recommendation: {},
    autonomyStatus: {},
    adaptiveStatus: {},
    loading: false,
    loaded: false,
    error: "",
  },
  dashboardView: {
    pendingActions: [],
    loading: false,
    loaded: false,
    feedback: "",
    error: "",
  },
  expandedTimelineEvents: {},
  debugMode: localStorage.getItem(STORAGE_KEYS.debug) === "true",
  refreshMs: Number(localStorage.getItem(STORAGE_KEYS.refreshMs) || CONFIG.defaultRefreshMs),
  profile: loadProfileState(),
  autonomyEnabled: localStorage.getItem(STORAGE_KEYS.autonomyEnabled) === "true",
  chatMode: localStorage.getItem(STORAGE_KEYS.chatMode) === "auto" ? "auto" : "manual",
  currentRoute: CONFIG.defaultRoute,
  workView: {
    messages: {},
    traceFilter: "all",
    executionPackages: {},
    activeExecutionProposalId: "",
    plansByProposal: {},
    activePlanProposalId: "",
    expandedStrategicAnalyses: {},
    strategyPendingActionsLoading: false,
    strategyPendingActionsLoaded: false,
  },
  timerId: null,
};

const ui = {
  pageContent: document.getElementById("page-content"),
  pageNav: document.getElementById("page-nav"),
  chatForm: document.getElementById("chat-form"),
  chatInput: document.getElementById("chat-input"),
  chatHistory: document.getElementById("chat-history"),
  chatPanel: document.getElementById("chat-panel"),
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

function saveAutonomyEnabledState() {
  localStorage.setItem(STORAGE_KEYS.autonomyEnabled, state.autonomyEnabled ? "true" : "false");
}

function saveChatModeState() {
  localStorage.setItem(STORAGE_KEYS.chatMode, state.chatMode);
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
  getMemory() {
    return this.fetchJson("/memory");
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
  getDailyLoopStatus() {
    return this.fetchJson("/daily_loop/status");
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
  riskBadgeClass(risk) {
    const value = this.normalizeStatus(risk);
    if (value === "high") return "risk-high";
    if (value === "medium") return "risk-medium";
    if (value === "low") return "risk-low";
    return "risk-neutral";
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

function buildPipelineTrace(stateSnapshot) {
  const opportunities = Array.isArray(stateSnapshot?.opportunities) ? stateSnapshot.opportunities : [];
  const proposals = Array.isArray(stateSnapshot?.proposals) ? stateSnapshot.proposals : [];
  const plans = Array.isArray(stateSnapshot?.plans) ? stateSnapshot.plans : [];
  const launches = Array.isArray(stateSnapshot?.launches) ? stateSnapshot.launches : [];

  const normalize = (value) => helpers.normalizeStatus(value);
  const toId = (value) => (value === undefined || value === null || value === "" ? null : String(value));

  const opportunitiesById = new Map(opportunities.map((item) => [toId(item.id), item]).filter(([id]) => id));
  const opportunitiesByTitle = new Map(opportunities.map((item) => [normalize(item.title), item]).filter(([title]) => title));
  const planByProposalId = new Map(plans.map((item) => [toId(item.proposal_id), item]).filter(([proposalId]) => proposalId));
  const launchByProposalId = new Map(launches.map((item) => [toId(item.proposal_id), item]).filter(([proposalId]) => proposalId));

  return proposals.map((proposal, idx) => {
    const proposalId = toId(proposal.id);
    const explicitOpportunityId = toId(proposal.opportunity_id);
    const inferredOpportunity = explicitOpportunityId
      ? opportunitiesById.get(explicitOpportunityId)
      : opportunitiesByTitle.get(normalize(proposal.opportunity_title || proposal.title || proposal.product_name));
    const opportunity = explicitOpportunityId
      ? opportunitiesById.get(explicitOpportunityId) || null
      : inferredOpportunity || null;

    const plan = planByProposalId.get(proposalId) || null;
    const launch = launchByProposalId.get(proposalId) || null;

    const proposalStatus = normalize(proposal.status) || null;
    const launchStatus = normalize(launch?.status);
    const isReady = ["ready_to_launch", "ready_for_review"].includes(proposalStatus);

    let primaryAction = { label: "View details", route: "#/work", run: null };
    if (proposalId && proposalStatus === "draft") {
      primaryAction = { label: "Approve", route: "#/work", run: { method: "POST", path: `/product_proposals/${proposalId}/approve`, body: {} } };
    } else if (proposalId && proposalStatus === "approved" && !plan) {
      primaryAction = { label: "Build plan", route: "#/work", run: { method: "POST", path: "/product_plans/build", body: { proposal_id: proposalId } } };
    } else if (proposalId && plan && !isReady && !["launched", "archived"].includes(proposalStatus)) {
      primaryAction = { label: "Mark ready", route: "#/work", run: { method: "POST", path: `/product_proposals/${proposalId}/ready`, body: {} } };
    } else if (proposalId && isReady && !launch) {
      primaryAction = { label: "Launch", route: "#/work", run: { method: "POST", path: `/product_proposals/${proposalId}/launch`, body: {} } };
    } else if (launch?.id && launchStatus && launchStatus !== "launched") {
      primaryAction = { label: "Set status launched", route: "#/work", run: { method: "POST", path: `/product_launches/${launch.id}/status`, body: { status: "launched" } } };
    }

    const secondaryActions = [];
    if (proposalId && proposalStatus === "approved" && !plan) {
      secondaryActions.push({ label: "Start build", run: { method: "POST", path: `/product_proposals/${proposalId}/start_build`, body: {} } });
    }
    if (proposalId && proposalStatus !== "archived") {
      secondaryActions.push({ label: "Archive", run: { method: "POST", path: `/product_proposals/${proposalId}/archive`, body: {} } });
    }

    return {
      key: proposalId || `trace-${idx}`,
      title: helpers.t(proposal.product_name || proposal.title || proposal.name, `Proposal ${idx + 1}`),
      stage: launch ? "LAUNCH" : plan ? "PLAN" : proposalId ? "PROPOSAL" : "OPPORTUNITY",
      status: {
        opportunity: opportunity ? normalize(opportunity.status || opportunity.decision?.status || "new") : null,
        proposal: proposalStatus,
        plan: plan ? "present" : "missing",
        launch: launch ? normalize(launch.status || "active") : null,
      },
      ids: {
        opportunity_id: toId(opportunity?.id) || explicitOpportunityId,
        proposal_id: proposalId,
        plan_id: toId(plan?.id || plan?.plan_id),
        launch_id: toId(launch?.id),
      },
      metrics: {
        confidence: Number.isFinite(Number(proposal.confidence)) ? Number(proposal.confidence) : null,
        price: Number.isFinite(Number(proposal.price_suggestion)) ? Number(proposal.price_suggestion) : null,
        sales: Number.isFinite(Number(launch?.metrics?.sales ?? launch?.sales)) ? Number(launch?.metrics?.sales ?? launch?.sales) : null,
        revenue: Number.isFinite(Number(launch?.metrics?.revenue ?? launch?.revenue)) ? Number(launch?.metrics?.revenue ?? launch?.revenue) : null,
      },
      primaryAction,
      secondaryActions,
    };
  });
}

function computePrimaryAttention(stateSnapshot) {
  const {
    strategyPendingActions = [],
    proposals = [],
    launches = [],
    opportunities = [],
  } = stateSnapshot || {};

  const toNumber = (value) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  };

  const priorityToNumeric = (priority) => {
    const normalized = helpers.normalizeStatus(priority);
    if (normalized === "high") return 3;
    if (normalized === "medium") return 2;
    if (normalized === "low") return 1;
    return toNumber(priority);
  };

  const autonomyStatus = stateSnapshot?.autonomy?.status
    || stateSnapshot?.autonomyStatus
    || state.strategyView.autonomyStatus
    || {};
  const autoExecutable = Boolean(autonomyStatus.auto_executable);

  const candidates = [];

  if (strategyPendingActions.length > 0) {
    const topStrategicAction = strategyPendingActions.reduce((best, action) => {
      const currentPriority = priorityToNumeric(action?.priority);
      const currentImpact = toNumber(action?.expected_impact_score);
      const currentScore = (currentPriority * 100) + (currentImpact * 10);
      if (!best || currentScore > best.score) {
        return { action, score: currentScore };
      }
      return best;
    }, null);

    if (topStrategicAction) {
      const autonomyBonus = autoExecutable ? 25 : 0;
      candidates.push({
        type: "strategy",
        priorityScore: topStrategicAction.score + autonomyBonus,
        label: "Review Strategic Action",
        route: "#/strategy",
        cta: "Review Strategic Action",
      });
    }
  }

  const draftProposals = proposals.filter((proposal) => helpers.normalizeStatus(proposal.status) === "draft");
  if (draftProposals.length > 0) {
    const topDraftUrgency = draftProposals.reduce((maxScore, proposal) => {
      const confidence = toNumber(proposal.confidence_level ?? proposal.confidence);
      const score = 50 + confidence;
      return Math.max(maxScore, score);
    }, 0);

    candidates.push({
      type: "draft",
      priorityScore: topDraftUrgency,
      label: "Review Drafts",
      route: "#/work",
      cta: "Review Drafts",
    });
  }

  const launchReadyItems = launches.filter((launch) => helpers.normalizeStatus(launch.status) !== "launched");
  if (launchReadyItems.length > 0) {
    const launchScore = launchReadyItems.reduce((maxScore, launch) => {
      const revenueEstimate = toNumber(launch.revenue_estimate ?? launch.projected_revenue ?? launch.target_revenue);
      const score = 40 + (revenueEstimate * 0.1);
      return Math.max(maxScore, score);
    }, 0);

    candidates.push({
      type: "launch",
      priorityScore: launchScore,
      label: "Finalize Launch",
      route: "#/work",
      cta: "Finalize Launch",
    });
  }

  const newOpportunities = opportunities.filter((opportunity) => helpers.normalizeStatus(opportunity.status) === "new");
  if (newOpportunities.length > 0) {
    candidates.push({
      type: "scan",
      priorityScore: 20 + newOpportunities.length,
      label: "Evaluate Opportunities",
      route: "#/work",
      cta: "Evaluate Opportunities",
    });
  }

  if (!candidates.length) return null;

  const decision = candidates.reduce((best, candidate) => {
    if (!best || candidate.priorityScore > best.priorityScore) {
      return candidate;
    }
    return best;
  }, null);

  if (!decision || decision.priorityScore < 10) return null;

  return decision;
}

function computeSystemStatus(stateSnapshot) {
  const primaryDecision = computePrimaryAttention(stateSnapshot);
  const strategyPendingActions = stateSnapshot?.strategyPendingActions || [];
  const proposals = stateSnapshot?.proposals || [];
  const launches = stateSnapshot?.launches || [];
  const opportunities = stateSnapshot?.opportunities || [];

  const hasStrategy = strategyPendingActions.length > 0;
  const hasDrafts = proposals.some((proposal) => helpers.normalizeStatus(proposal.status) === "draft");
  const hasLaunchReady = launches.some((launch) => helpers.normalizeStatus(launch.status) !== "launched");
  const hasNewOpps = opportunities.some((opportunity) => helpers.normalizeStatus(opportunity.status) === "new");

  return {
    mode: primaryDecision ? "FOCUSED" : "STABLE",
    primaryDecision,
    indicators: {
      hasStrategy,
      hasDrafts,
      hasLaunchReady,
      hasNewOpps,
    },
  };
}

function renderMissionControl(loopState) {
  const container = document.getElementById("attention-block");
  if (!container) return;

  const phase = helpers.t(loopState?.phase, "IDLE").toUpperCase();
  const summary = helpers.t(loopState?.summary, "System operating normally.");
  const route = loopState?.route || "";
  const actionLabel = helpers.t(loopState?.next_action_label, "No Immediate Action");
  const disabled = !route || phase === "IDLE";

  container.innerHTML = `
    <div class="card attention-card" style="min-height: 172px;">
      <h3>OS Status</h3>
      <p><strong>Phase:</strong> <span class="badge info">${helpers.escape(phase)}</span></p>
      <p>${helpers.escape(summary)}</p>
      <button class="btn btn-primary" ${disabled ? "disabled" : `data-route="${helpers.escape(route)}"`}>
        ${helpers.escape(actionLabel)}
      </button>
    </div>
  `;
}

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
    const phase = helpers.t(state.dailyLoop?.phase, "IDLE").toUpperCase();
    ui.pageContent.innerHTML = `
      <div class="card" style="margin-bottom: 12px; padding: 10px 14px;">
        <strong>Daily Loop Phase:</strong> <span class="badge info">${helpers.escape(phase)}</span>
      </div>
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
    const phase = helpers.t(state.dailyLoop?.phase, "IDLE").toUpperCase();
    ui.pageContent.innerHTML = `
      <div class="card" style="margin-bottom: 12px; padding: 10px 14px;">
        <strong>Daily Loop Phase:</strong> <span class="badge info">${helpers.escape(phase)}</span>
      </div>
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

    const dashboardView = state.dashboardView;
    const pendingActions = dashboardView.pendingActions || [];
    const sortedStrategicActions = [...pendingActions].sort((left, right) => {
      const priorityRank = { high: 3, medium: 2, low: 1 };
      const leftPriority = priorityRank[helpers.normalizeStatus(left.priority)] || 0;
      const rightPriority = priorityRank[helpers.normalizeStatus(right.priority)] || 0;
      if (leftPriority !== rightPriority) return rightPriority - leftPriority;
      return helpers.actionImpactScore(right) - helpers.actionImpactScore(left);
    });

    const topStrategicActions = sortedStrategicActions.slice(0, 3);
    const topStrategicAction = sortedStrategicActions[0] || null;
    const highRiskAction = sortedStrategicActions.find((item) => helpers.normalizeStatus(item.risk_level) === "high");

    const autonomyStatus = state.strategyView.autonomyStatus || {};
    const autonomyRaw = helpers.normalizeStatus(autonomyStatus.mode || autonomyStatus.autonomy_mode || "manual");
    const autonomyMode = autonomyRaw.includes("partial") ? "PARTIAL-AUTO" : "MANUAL";

    const pipelineHealth = (() => {
      const hasPipeline = state.proposals.length > 0 || buildsCount > 0 || activeLaunches > 0;
      if (highRiskAction) return { label: "ATTENTION", tone: "warn" };
      if (hasPipeline) return { label: "GOOD", tone: "ok" };
      return { label: "IDLE", tone: "info" };
    })();

    const activeRisk = highRiskAction
      ? { label: "HIGH", tone: "error" }
      : sortedStrategicActions.some((item) => helpers.normalizeStatus(item.risk_level) === "medium")
        ? { label: "MEDIUM", tone: "warn" }
        : sortedStrategicActions.length
          ? { label: "LOW", tone: "ok" }
          : { label: "NONE", tone: "info" };

    const renderGlobalStatus = () => `
      <article class="card mission-global-status">
        <h3>Global Status</h3>
        <div class="mission-status-strip">
          <span class="mission-status-item">SYSTEM MODE <strong class="badge ${helpers.badgeClass(systemMode)}">${helpers.escape(systemMode)}</strong></span>
          <span class="mission-status-item">ACTIVE RISK <strong class="badge ${activeRisk.tone}">${helpers.escape(activeRisk.label)}</strong></span>
          <span class="mission-status-item">AUTONOMY MODE <strong class="badge info">${helpers.escape(autonomyMode)}</strong></span>
          <span class="mission-status-item">PIPELINE HEALTH <strong class="badge ${pipelineHealth.tone}">${helpers.escape(pipelineHealth.label)}</strong></span>
        </div>
      </article>
    `;

    const renderAutonomyControls = () => {
      const autonomyEnabled = Boolean(state.autonomyEnabled);
      return `
        <article class="card mission-autonomy-toggle">
          <h3>Autonomy</h3>
          <div class="card-actions">
            <button
              class="btn ${autonomyEnabled ? "btn-primary" : "secondary-btn"}"
              data-action="toggle-autonomy"
              aria-pressed="${autonomyEnabled ? "true" : "false"}"
            >
              ${autonomyEnabled ? "ON (Autonomous)" : "OFF (Manual)"}
            </button>
          </div>
          <p class="control-helper">
            ${autonomyEnabled
    ? "Treta can execute safe actions automatically (guarded)."
    : "Treta recommends. You approve execution."}
          </p>
        </article>
        <article class="card mission-guardrails">
          <h3>Guardrails</h3>
          <p class="control-helper"><strong>Max auto actions per session:</strong> 3</p>
          <p class="control-helper"><strong>Allowed:</strong> Scan, Generate draft</p>
          <p class="control-helper"><strong>Requires confirmation:</strong> Launch, Pricing changes, Publishing</p>
        </article>
      `;
    };

    const renderRevenueFocus = () => {
      const totalRevenue = Number(state.performance.total_revenue || 0);
      const revenueTrend = totalRevenue > 0 ? "Positive" : "Flat";
      const highConfidenceDraft = state.proposals.find((item) => {
        const status = helpers.normalizeStatus(item.status);
        const confidence = Number(item.confidence || 0);
        return status === "draft" && confidence >= 0.8;
      });

      const bestLeverageAction = readyToLaunch > 0
        ? "Launch product"
        : highConfidenceDraft
          ? "Approve proposal"
          : "Run opportunity scan";

      return `
        <article class="card mission-revenue-focus">
          <h3>💰 REVENUE FOCUS</h3>
          <section class="card-grid cols-2">
            <div class="metric"><span>Total revenue</span><strong>${helpers.escape(helpers.t(state.performance.total_revenue, 0))}</strong></div>
            <div class="metric"><span>Revenue trend</span><strong>${helpers.escape(revenueTrend)}</strong></div>
            <div class="metric"><span>Best leverage action</span><strong>${helpers.escape(bestLeverageAction)}</strong></div>
            <div class="metric"><span>Projected impact</span><strong>${helpers.escape(helpers.t(topStrategicAction?.expected_impact_score, "-"))}</strong></div>
          </section>
        </article>
      `;
    };

    const renderStrategicCompact = () => {
      if (dashboardView.loading) return "<p class='empty'>Loading pending strategic actions…</p>";
      if (!topStrategicActions.length) return "<p class='empty'>No pending strategic actions.</p>";

      return `
        <div class="dashboard-strategy-list">
          ${topStrategicActions.map((item) => {
            const priority = helpers.t(item.priority, "Unknown");
            const risk = helpers.t(item.risk_level, "Unknown");
            const actionType = helpers.t(item.action_type || item.type || item.title || item.name, "Unknown");
            const impactScore = helpers.t(item.expected_impact_score, "-");
            return `
              <article class="dashboard-strategy-card">
                <div class="dashboard-strategy-meta">
                  <span class="badge ${helpers.priorityBadgeClass(priority)}">${helpers.escape(priority)}</span>
                  <span class="dashboard-risk-badge ${helpers.riskBadgeClass(risk)}">Risk: ${helpers.escape(risk)}</span>
                </div>
                <p><strong>Action type:</strong> ${helpers.escape(actionType)}</p>
                <p><strong>Expected impact score:</strong> ${helpers.escape(impactScore)}</p>
                <div class="card-actions">
                  <button data-action="dashboard-strategy-execute" data-id="${helpers.escape(item.id)}">Execute</button>
                  <button class="secondary-btn" data-action="dashboard-strategy-reject" data-id="${helpers.escape(item.id)}">Reject</button>
                </div>
              </article>
            `;
          }).join("")}
        </div>
        <a class="dashboard-strategy-view-all" href="#/strategy">View All in Strategy</a>
      `;
    };

    const strategyFeedback = dashboardView.feedback ? `<p class="dashboard-strategy-feedback">${helpers.escape(dashboardView.feedback)}</p>` : "";
    const strategyError = dashboardView.error ? `<p class="empty">${helpers.escape(dashboardView.error)}</p>` : "";

    this.shell("Dashboard", "Operational summary and next best action", `
      <section class="os-dashboard">
        ${renderGlobalStatus()}
        ${renderAutonomyControls()}
        <div id="attention-block"></div>
        ${renderRevenueFocus()}

        <article class="card os-strategic-actions" id="dashboard-strategic-actions">
          <h3>🧠 STRATEGIC ACTIONS</h3>
          ${strategyError}
          ${strategyFeedback}
          ${renderStrategicCompact()}
        </article>
      </section>
    `);
    renderMissionControl(state.dailyLoop);
    bindDashboardActions();
    if (!dashboardView.loading && !dashboardView.loaded) {
      loadDashboardPendingActions();
    }
  },

  loadWork() {
    const transitionLabels = {
      approve: "Approve",
      reject: "Reject",
      ready: "Mark Ready",
      launch: "Launch",
    };

    const getOpportunityStatus = (item) => {
      const normalized = helpers.normalizeStatus(item.status || item.decision?.status || "new");
      if (normalized === "evaluated") return "evaluated";
      if (normalized === "dismissed") return "dismissed";
      return "new";
    };

    const getOpportunityScore = (item) => {
      const candidates = [item.score, item.decision?.score, item.decision?.composite_score];
      const score = candidates.find((value) => Number.isFinite(Number(value)));
      return score === undefined ? "-" : helpers.t(score);
    };

    const renderOpportunityCard = (item) => {
      return `
        <article class="card row-item">
          <h4>${helpers.escape(helpers.t(item.title, item.id))}</h4>
          <p>
            score: ${helpers.escape(getOpportunityScore(item))}
          </p>
          <p><strong>Status:</strong> New Opportunity</p>
          <p class="muted-note" style="display: inline-block; padding: 2px 8px; border-radius: 999px; background: rgba(88, 166, 255, 0.12);"><strong>Next Action:</strong> Evaluate or Dismiss</p>
          <div class="card-actions work-secondary-actions">
            <button class="secondary-btn" data-action="eval-opp" data-id="${helpers.escape(helpers.t(item.id, ""))}">Evaluate</button>
            <button class="secondary-btn" data-action="dismiss-opp" data-id="${helpers.escape(helpers.t(item.id, ""))}">Dismiss</button>
          </div>
        </article>
      `;
    };

    const renderProposalCard = (item, transitions, statusLabel, nextActionLabel) => {
      const proposalId = helpers.t(item.id, "");
      const actionButtons = transitions.map((transition) => {
        if (transition === "generate_execution_package") {
          return `<button class="secondary-btn" data-action="generate-execution-package" data-id="${helpers.escape(proposalId)}">Generate Execution Package</button>`;
        }
        return `
          <button class="secondary-btn" data-action="proposal" data-transition="${helpers.escape(transition)}" data-id="${helpers.escape(proposalId)}">
            ${helpers.escape(transitionLabels[transition] || helpers.statusLabel(transition))}
          </button>
        `;
      }).join("");

      const hasExecutionPackage = Boolean(
        state.workView.executionPackages[proposalId]
        || item.execution_package
        || item.execution_package_generated
        || item.execution_package_ready
        || item.execution_package_id
      );

      return `
        <article class="card row-item">
          <h4>${helpers.escape(helpers.t(item.product_name, item.id))}</h4>
          <p>
            <span class="badge ${helpers.badgeClass(item.status)}">${helpers.escape(helpers.statusLabel(item.status))}</span>
            audience: ${helpers.escape(helpers.t(item.target_audience, "-"))}
          </p>
          <p><strong>Status:</strong> ${helpers.escape(statusLabel)}</p>
          <p class="muted-note" style="display: inline-block; padding: 2px 8px; border-radius: 999px; background: rgba(88, 166, 255, 0.12);"><strong>Next Action:</strong> ${helpers.escape(nextActionLabel)}</p>
          <p>price suggestion: ${helpers.escape(helpers.t(item.price_suggestion, "-"))} · confidence: ${helpers.escape(helpers.t(item.confidence, "-"))}</p>
          ${hasExecutionPackage ? "<p class='muted-note'>Execution package generated.</p>" : ""}
          <div class="card-actions wrap work-secondary-actions">
            ${actionButtons || "<span class='empty'>No actions available.</span>"}
          </div>
        </article>
      `;
    };

    const emptyStageMessage = "<p class='empty'>No items in this stage.</p>";

    const newOpportunities = state.opportunities.filter((item) => getOpportunityStatus(item) === "new");
    const draftProposals = state.proposals.filter((item) => helpers.normalizeStatus(item.status) === "draft");
    const buildingProposals = state.proposals.filter((item) => helpers.normalizeStatus(item.status) === "building");
    const readyToLaunchProposals = state.proposals.filter((item) => {
      const status = helpers.normalizeStatus(item.status);
      return status === "ready_to_launch" || status === "ready_for_review";
    });

    const renderLaunchCard = (item) => {
      const launchId = helpers.t(item.id, "");
      const metrics = item.metrics || {};
      const sales = helpers.t(metrics.sales ?? item.sales, 0);
      const salesCount = Number(metrics.sales ?? item.sales ?? 0);
      const revenue = helpers.t(metrics.revenue ?? item.revenue, 0);
      const message = state.workView.messages[`launch-${launchId}`] || "";
      const nextActionLabel = salesCount === 0
        ? "Add first sale to start tracking performance"
        : "Monitor performance or adjust pricing";

      return `
        <article class="card row-item">
          <h4>${helpers.escape(helpers.t(item.product_name, item.proposal_id || launchId))}</h4>
          <p>
            <span class="badge ${helpers.badgeClass(item.status)}">${helpers.escape(helpers.statusLabel(item.status))}</span>
            sales: ${helpers.escape(sales)} · revenue: ${helpers.escape(revenue)}
          </p>
          <p><strong>Status:</strong> Launch Active</p>
          <p class="muted-note" style="display: inline-block; padding: 2px 8px; border-radius: 999px; background: rgba(88, 166, 255, 0.12);"><strong>Next Action:</strong> ${helpers.escape(nextActionLabel)}</p>
          <div class="inline-form-grid launch-actions-inline">
            <div class="inline-control-group">
              <label>Amount</label>
              <input type="number" step="0.01" min="0" data-launch-input="sale" data-id="${helpers.escape(launchId)}" placeholder="0.00">
              <button class="secondary-btn" data-action="launch-add-sale" data-id="${helpers.escape(launchId)}">Add Sale</button>
            </div>
            <div class="inline-control-group">
              <label>Status</label>
              <select data-launch-input="status" data-id="${helpers.escape(launchId)}">
                <option value="active">Active</option>
                <option value="paused">Paused</option>
                <option value="archived">Archived</option>
              </select>
              <button class="secondary-btn" data-action="launch-set-status" data-id="${helpers.escape(launchId)}">Change Status</button>
            </div>
          </div>
          ${message ? `<p class="muted-note">${helpers.escape(message)}</p>` : ""}
        </article>
      `;
    };

    const launchesContent = state.launches.length
      ? state.launches.map(renderLaunchCard).join("")
      : emptyStageMessage;

    this.shell("Work", "Product Lifecycle Operating System", `
      <section class="work-execution">
        <article class="card work-section">
          <header class="work-section-header">
            <h3>1) Opportunities</h3>
            <p class="muted-note">New demand signals ready for triage.</p>
          </header>
          <section class="work-status-group">
            ${newOpportunities.length ? newOpportunities.map(renderOpportunityCard).join("") : emptyStageMessage}
          </section>
        </article>

        <article class="card work-section">
          <header class="work-section-header">
            <h3>2) Draft Proposals</h3>
            <p class="muted-note">Concepts waiting for an approval decision.</p>
          </header>
          <section class="work-status-group">
            ${draftProposals.length ? draftProposals.map((item) => renderProposalCard(item, ["approve", "reject"], "Draft", "Approve to begin building")).join("") : emptyStageMessage}
          </section>
        </article>

        <article class="card work-section">
          <header class="work-section-header">
            <h3>3) Building</h3>
            <p class="muted-note">Products currently being built.</p>
          </header>
          <section class="work-status-group">
            ${buildingProposals.length ? buildingProposals.map((item) => renderProposalCard(item, ["ready"], "Building", "Mark ready when assets complete")).join("") : emptyStageMessage}
          </section>
        </article>

        <article class="card work-section">
          <header class="work-section-header">
            <h3>4) Ready to Launch</h3>
            <p class="muted-note">Launch-ready proposals waiting for go-live execution.</p>
          </header>
          <section class="work-status-group">
            ${readyToLaunchProposals.length ? readyToLaunchProposals.map((item) => {
              const proposalId = helpers.t(item.id, "");
              const hasExecutionPackage = Boolean(
                state.workView.executionPackages[proposalId]
                || item.execution_package
                || item.execution_package_generated
                || item.execution_package_ready
                || item.execution_package_id
              );
              const transitions = ["launch", ...(hasExecutionPackage ? [] : ["generate_execution_package"])];
              return renderProposalCard(item, transitions, "Ready to Launch", "Launch product");
            }).join("") : emptyStageMessage}
          </section>
        </article>

        <article class="card work-section">
          <header class="work-section-header">
            <h3>5) Active Launches</h3>
            <p class="muted-note">Live operations with status and monetization controls.</p>
          </header>
          <section class="work-status-group">
            ${launchesContent}
          </section>
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
      if (!pendingActions.length) return "<p class='empty'>No strategic actions pending.</p>";

      return `
        <div class="stack">
          ${pendingActions.map((item) => {
            const actionId = String(item.action_id ?? item.id ?? "");
            const actionIdLabel = actionId || "-";
            const escapedActionId = helpers.escape(actionIdLabel);
            return `
              <article class="card">
                <section class="card-grid cols-2">
                  <div class="metric"><span>action_id</span><strong>${escapedActionId}</strong></div>
                  <div class="metric"><span>action_type</span><strong>${helpers.escape(helpers.t(item.action_type, "unknown"))}</strong></div>
                  <div class="metric"><span>priority</span><strong><span class="badge ${helpers.priorityBadgeClass(item.priority)}">${helpers.escape(helpers.t(item.priority, "unknown"))}</span></strong></div>
                  <div class="metric"><span>risk_level</span><strong><span class="badge ${helpers.riskBadgeClass(item.risk_level)}">${helpers.escape(helpers.t(item.risk_level, "unknown"))}</span></strong></div>
                  <div class="metric"><span>expected_impact_score</span><strong>${helpers.escape(helpers.t(item.expected_impact_score, "-"))}</strong></div>
                  <div class="metric"><span>auto_executable</span><strong>${item.auto_executable ? "true" : "false"}</strong></div>
                </section>
                <div class="card-actions wrap" style="margin-top: 12px;">
                  <button data-action="strategy-execute" data-id="${actionId}">Execute</button>
                  <button class="secondary-btn" data-action="strategy-reject" data-id="${actionId}">Reject</button>
                </div>
              </article>
            `;
          }).join("")}
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

    const pendingActions = pendingData.items || pendingData.actions || pendingData.pending_actions || [];
    state.strategyPendingActions = pendingActions;
    state.strategyView.pendingActions = pendingActions;
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

async function loadDashboardPendingActions() {
  state.dashboardView.loading = true;
  state.dashboardView.error = "";
  if (state.currentRoute === "dashboard") router.render();
  try {
    const pendingData = await api.getPendingStrategyActions();
    const pendingActions = pendingData.items || pendingData.actions || pendingData.pending_actions || [];
    state.strategyPendingActions = pendingActions;
    state.dashboardView.pendingActions = pendingActions;
  } catch (error) {
    state.dashboardView.error = `strategy actions error: ${error.message}`;
    log("system", state.dashboardView.error);
  } finally {
    state.dashboardView.loading = false;
    state.dashboardView.loaded = true;
    if (state.currentRoute === "dashboard") router.render();
  }
}

async function loadWorkStrategyPendingActions() {
  state.workView.strategyPendingActionsLoading = true;
  if (state.currentRoute === "work") router.render();
  try {
    const pendingData = await api.getPendingStrategyActions();
    state.strategyPendingActions = pendingData.items || pendingData.actions || pendingData.pending_actions || [];
    const availableIds = new Set(state.strategyPendingActions.map((item) => String(item.id)));
    state.workView.expandedStrategicAnalyses = Object.fromEntries(
      Object.entries(state.workView.expandedStrategicAnalyses).filter(([id]) => availableIds.has(String(id)))
    );
  } catch (error) {
    log("system", `work strategy actions error: ${error.message}`);
  } finally {
    state.workView.strategyPendingActionsLoading = false;
    state.workView.strategyPendingActionsLoaded = true;
    if (state.currentRoute === "work") router.render();
  }
}

function renderEditableMetric(key, label) {
  return `<label>${label}<input id="profile-${key}" type="number" value="${helpers.t(state.profile[key], 0)}"></label>`;
}

function renderNavigation() {
  const active = state.currentRoute;
  ui.pageNav.innerHTML = CONFIG.routes
    .map((route) => `<button class="nav-btn ${route === active ? "active" : ""}" data-route="#/${route}">${route[0].toUpperCase()}${route.slice(1)}</button>`)
    .join("");
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

function renderConversation() {
  if (!ui.chatHistory) return;
  const messages = state.chatCards || [];
  if (!messages.length) {
    ui.chatHistory.innerHTML = "<p class='empty'>No messages yet.</p>";
    return;
  }

  ui.chatHistory.innerHTML = messages
    .map((item) => {
      if (item.type === "user") {
        const text = helpers.escape(helpers.t(item.text, ""));
        return `
          <article class="chat-message user">
            <div class="chat-role">user</div>
            <div>${text}</div>
          </article>
        `;
      }

      if (item.type === "confirm") {
        const title = helpers.escape(helpers.t(item.title, "Confirmation required"));
        const summary = helpers.escape(helpers.t(item.summary, ""));
        return `
          <article class="chat-message assistant chat-card chat-confirmation-card">
            <div class="chat-role">assistant</div>
            <h4>${title}</h4>
            <p>${summary}</p>
            <div class="card-actions">
              <button type="button" data-action="chat-confirm" data-id="${helpers.escape(item.id)}">Confirm</button>
              <button type="button" class="secondary-btn" data-action="chat-cancel" data-id="${helpers.escape(item.id)}">Cancel</button>
            </div>
          </article>
        `;
      }

      const card = item.card || {};
      const title = helpers.escape(helpers.t(card.title, "Treta"));
      const summary = helpers.escape(helpers.t(card.summary, ""));
      const details = card.details ? `<small>${helpers.escape(helpers.t(card.details, ""))}</small>` : "";
      const cta = card.cta
        ? `<button type="button" data-action="chat-cta" data-run="${card.cta.run ? "1" : ""}" data-route="${helpers.escape(card.cta.route || "")}" data-id="${helpers.escape(item.id)}">${helpers.escape(helpers.t(card.cta.label, "Run"))}</button>`
        : "";
      const chips = Array.isArray(card.chips) && card.chips.length
        ? `<div class="chat-chips">${card.chips
            .map((chip) => `<button type="button" class="secondary-btn" data-action="chat-chip" data-route="${helpers.escape(chip.route || "")}" data-run="${chip.run ? "1" : ""}" data-id="${helpers.escape(item.id)}">${helpers.escape(helpers.t(chip.label, "Option"))}</button>`)
            .join("")}</div>`
        : "";
      return `
        <article class="chat-message assistant chat-card">
          <div class="chat-role">assistant</div>
          <h4>${title}</h4>
          <p>${summary}</p>
          ${details}
          ${cta ? `<div class="card-actions">${cta}</div>` : ""}
          ${chips}
        </article>
      `;
    })
    .join("");

  ui.chatHistory.querySelectorAll("button[data-action='chat-confirm']").forEach((button) => {
    button.addEventListener("click", async () => {
      const entry = state.chatCards.find((item) => item.id === button.dataset.id);
      if (!entry?.decision) return;
      state.chatCards = state.chatCards.filter((item) => item.id !== entry.id);
      await executeDecision(entry.decision);
    });
  });

  ui.chatHistory.querySelectorAll("button[data-action='chat-cancel']").forEach((button) => {
    button.addEventListener("click", () => {
      state.chatCards = state.chatCards.filter((item) => item.id !== button.dataset.id);
      state.chatCards.push({
        id: `assistant-${Date.now()}`,
        type: "assistant",
        card: {
          title: "Command canceled",
          summary: "No action was executed.",
        },
      });
      renderConversation();
    });
  });

  ui.chatHistory.querySelectorAll("button[data-action='chat-cta'], button[data-action='chat-chip']").forEach((button) => {
    button.addEventListener("click", async () => {
      const route = button.dataset.route || "";
      const run = button.dataset.run === "1";
      if (route) router.navigate(route.replace("#/", ""));
      if (run) {
        const entry = state.chatCards.find((item) => item.id === button.dataset.id);
        if (entry?.decision) await executeDecision({ ...entry.decision, requires_confirmation: false });
      }
    });
  });

  ui.chatHistory.scrollTop = ui.chatHistory.scrollHeight;
}

function renderCommandBar() {
  if (!ui.chatForm) return;
  ui.chatForm.classList.add("quick-command-bar");
  if (!ui.chatPanel) return;
  const title = ui.chatPanel.querySelector("h2");
  if (!title) return;
  title.innerHTML = `Conversation <span class="chat-mode-toggle"><button type="button" class="secondary-btn ${state.chatMode === "manual" ? "active" : ""}" data-action="chat-mode" data-mode="manual">Manual</button><button type="button" class="secondary-btn ${state.chatMode === "auto" ? "active" : ""}" data-action="chat-mode" data-mode="auto">Auto</button></span>`;
  title.querySelectorAll("button[data-action='chat-mode']").forEach((button) => {
    button.addEventListener("click", () => {
      state.chatMode = button.dataset.mode === "auto" ? "auto" : "manual";
      saveChatModeState();
      renderCommandBar();
    });
  });
}

function getChatStateSnapshot() {
  return {
    opportunities: state.opportunities,
    proposals: state.proposals,
    launches: state.launches,
    strategyPendingActions: state.strategyPendingActions,
    performanceSummary: state.performance,
    autonomyStatus: state.strategyView.autonomyStatus,
    systemMode: state.system,
    events: state.events,
  };
}

function commandNeedsConfirmation(rawText, chatMode, confidence) {
  const trimmed = rawText.trim().toLowerCase();
  if (chatMode === "manual") return !(trimmed.startsWith("!") || trimmed.startsWith("run ") || trimmed.startsWith("execute "));
  return confidence < 0.8;
}

function mapNavigationRoute(command) {
  const normalized = command.toLowerCase();
  if (normalized.includes("dashboard")) return "dashboard";
  if (normalized.includes("work")) return "work";
  if (normalized.includes("strategy")) return "strategy";
  if (normalized.includes("settings")) return "settings";
  if (normalized.includes("profile")) return "profile";
  if (normalized.includes("game")) return "game";
  if (normalized.includes("home")) return "home";
  return "home";
}

function computeChatIntentDecision(rawText, stateSnapshot, settings) {
  const text = helpers.t(rawText, "").trim();
  const lower = text.toLowerCase();
  const decision = {
    intent: "unknown",
    confidence: 0.45,
    requires_confirmation: false,
    action: { kind: "no_op", calls: [] },
    ui: {
      title: "Need clarification",
      summary: "I can run commands, query the pipeline, or navigate to a page.",
      chips: [
        { label: "Scan opportunities", run: true },
        { label: "Show drafts", run: true },
        { label: "Go strategy", route: "#/strategy" },
      ],
    },
    telemetry: { raw_text: rawText, matched_rule: "unknown" },
  };

  const executeMatch = lower.match(/(?:execute strategy|ejecuta accion)\s+([a-z0-9_-]+)/i);
  const rejectMatch = lower.match(/(?:reject strategy|rechaza accion)\s+([a-z0-9_-]+)/i);
  const isHelp = /\b(help|ayuda|comandos)\b/.test(lower);
  const isNavigate = /\b(go|ir|navigate)\b/.test(lower) && /(home|dashboard|work|strategy|settings|profile|game)/.test(lower);
  const isScan = /(opportunity scan|scan|escanea|buscar oportunidades)/.test(lower);
  const isSyncSales = /(sync gumroad|sync sales|sincroniza ventas)/.test(lower);
  const isStatus = /\b(status|estado|como vamos)\b/.test(lower);
  const isOpps = /\b(opportunities|oportunidades)\b/.test(lower);
  const isProposals = /\b(proposals|drafts|propuestas)\b/.test(lower);
  const isLaunches = /\b(launches|lanzamientos)\b/.test(lower);
  const isStrategy = /\b(strategy|acciones|cola)\b/.test(lower);

  if (isHelp) {
    return {
      ...decision,
      intent: "help",
      confidence: 0.99,
      telemetry: { raw_text: rawText, matched_rule: "help" },
      ui: {
        title: "Available commands",
        summary: "Use scan, sync sales, strategy execute/reject, status, drafts, launches, or go <route>.",
        chips: [
          { label: "scan", run: true },
          { label: "status", run: true },
          { label: "go work", route: "#/work" },
        ],
      },
    };
  }

  if (isNavigate) {
    const route = mapNavigationRoute(lower);
    return {
      ...decision,
      intent: "navigate",
      confidence: 0.95,
      telemetry: { raw_text: rawText, matched_rule: "navigate" },
      action: { kind: "no_op", calls: [] },
      ui: {
        title: "Navigation",
        summary: `Opening ${route}.`,
        cta: { label: "Open", route: `#/${route}` },
      },
    };
  }

  if (executeMatch || rejectMatch || isScan || isSyncSales) {
    const calls = [];
    let matchedRule = "command.scan";
    let summary = "Ready to execute command.";
    if (executeMatch) {
      const id = executeMatch[1];
      calls.push({ method: "POST", path: `/strategy/execute_action/${id}`, body: {} });
      matchedRule = "command.strategy.execute";
      summary = `Execute strategy action ${id}.`;
    } else if (rejectMatch) {
      const id = rejectMatch[1];
      calls.push({ method: "POST", path: `/strategy/reject_action/${id}`, body: {} });
      matchedRule = "command.strategy.reject";
      summary = `Reject strategy action ${rejectMatch[1]}.`;
    } else if (isSyncSales) {
      calls.push({ method: "POST", path: "/gumroad/sync_sales", body: {} });
      matchedRule = "command.sync_sales";
      summary = "Sync Gumroad sales.";
    } else {
      calls.push({ method: "POST", path: "/scan/infoproduct", body: {} });
      matchedRule = "command.scan";
      summary = "Run infoproduct opportunity scan.";
    }

    const confidence = executeMatch || rejectMatch ? 0.98 : 0.9;
    return {
      ...decision,
      intent: "command",
      confidence,
      requires_confirmation: commandNeedsConfirmation(text, settings.chatMode, confidence),
      action: { kind: "api_call", calls },
      telemetry: { raw_text: rawText, matched_rule: matchedRule },
      ui: {
        title: "Command ready",
        summary,
        cta: { label: "Run", run: true },
      },
    };
  }

  if (isStatus || isOpps || isProposals || isLaunches || isStrategy) {
    let calls = [];
    let matchedRule = "query.status";
    let summary = "Pipeline query prepared.";
    let cta = null;
    if (isStatus) {
      calls = [{ method: "GET", path: "/state" }, { method: "GET", path: "/performance/summary" }];
      summary = `Mode: ${helpers.t(stateSnapshot.systemMode?.state, "unknown")}. Revenue: ${helpers.t(stateSnapshot.performanceSummary?.total_revenue, 0)}.`;
      cta = { label: "Open dashboard", route: "#/dashboard" };
      matchedRule = "query.status";
    } else if (isOpps) {
      calls = [{ method: "GET", path: "/opportunities" }];
      summary = `${(stateSnapshot.opportunities || []).length} opportunities loaded.`;
      cta = { label: "Open work", route: "#/work" };
      matchedRule = "query.opportunities";
    } else if (isProposals) {
      calls = [{ method: "GET", path: "/product_proposals" }];
      summary = `${(stateSnapshot.proposals || []).length} proposals/drafts loaded.`;
      cta = { label: "Open work", route: "#/work" };
      matchedRule = "query.proposals";
    } else if (isLaunches) {
      calls = [{ method: "GET", path: "/product_launches" }];
      summary = `${(stateSnapshot.launches || []).length} launches loaded.`;
      cta = { label: "Open work", route: "#/work" };
      matchedRule = "query.launches";
    } else {
      calls = [{ method: "GET", path: "/strategy/pending_actions" }, { method: "GET", path: "/strategy/recommendations" }];
      summary = `${(stateSnapshot.strategyPendingActions || []).length} pending strategy actions.`;
      cta = { label: "Open strategy", route: "#/strategy" };
      matchedRule = "query.strategy";
    }

    return {
      ...decision,
      intent: "query",
      confidence: 0.92,
      action: { kind: calls.length > 1 ? "multi_call" : "api_call", calls },
      telemetry: { raw_text: rawText, matched_rule: matchedRule },
      ui: {
        title: "Query ready",
        summary,
        cta,
      },
    };
  }

  return decision;
}

async function executeDecision(decision) {
  if (!decision) return;
  if (decision.intent === "navigate") {
    const route = decision.ui?.cta?.route;
    if (route) router.navigate(route.replace("#/", ""));
    state.chatCards.push({ id: `assistant-${Date.now()}`, type: "assistant", decision, card: { ...decision.ui, details: "Navigation applied." } });
    renderConversation();
    return;
  }

  if (decision.action.kind === "no_op") {
    state.chatCards.push({ id: `assistant-${Date.now()}`, type: "assistant", decision, card: decision.ui });
    renderConversation();
    return;
  }

  try {
    const callResults = [];
    for (const call of decision.action.calls || []) {
      const options = { method: call.method };
      if (call.method === "POST") options.body = JSON.stringify(call.body || {});
      const result = await api.fetchJson(call.path, options);
      callResults.push({ path: call.path, result });
    }

    await refreshLoop();
    if (decision.action.calls.some((call) => call.path.includes("/strategy/"))) {
      await loadStrategyData();
      await loadDashboardPendingActions();
    }

    state.chatCards.push({
      id: `assistant-${Date.now()}`,
      type: "assistant",
      decision,
      card: {
        title: decision.ui?.title || "Done",
        summary: `${decision.intent === "query" ? "Query completed" : "Command executed"}.`,
        details: helpers.t(callResults[0] ? JSON.stringify(callResults[0].result) : "OK", "OK"),
        cta: decision.ui?.cta,
      },
    });
  } catch (error) {
    state.chatCards.push({
      id: `assistant-${Date.now()}`,
      type: "assistant",
      decision,
      card: {
        title: "Execution error",
        summary: error.message,
      },
    });
  }
  renderConversation();
}

function renderControlCenter() {
  renderSystemStatus();
  renderActivityTimeline();
  renderCommandBar();
  renderConversation();
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
    const [systemData, eventData, memoryData, oppData, proposalData, launchData, planData, perfData, strategyData, pendingData, dailyLoopData] = await Promise.all([
      api.getState(),
      api.getRecentEvents(),
      api.getMemory(),
      api.getOpportunities(),
      api.getProductProposals(),
      api.getProductLaunches(),
      api.getProductPlans(),
      api.getPerformanceSummary(),
      api.getStrategyRecommendations(),
      api.getPendingStrategyActions(),
      api.getDailyLoopStatus(),
    ]);

    state.system = systemData || { state: "IDLE" };
    state.events = eventData.events || [];
    state.chatHistory = memoryData.chat_history || [];
    state.opportunities = oppData.items || [];
    state.proposals = proposalData.items || [];
    state.launches = launchData.items || [];
    state.plans = planData.items || [];
    state.performance = perfData || {};
    state.strategy = strategyData || {};
    const pendingActions = pendingData.items || pendingData.actions || pendingData.pending_actions || [];
    state.strategyPendingActions = pendingActions;
    state.dashboardView.pendingActions = pendingActions;
    state.dashboardView.loaded = true;
    state.dashboardView.loading = false;
    state.dashboardView.error = "";
    state.dailyLoop = dailyLoopData || state.dailyLoop;
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
  const traceItems = buildPipelineTrace({
    opportunities: state.opportunities,
    proposals: state.proposals,
    plans: state.plans,
    launches: state.launches,
  });
  const traceByKey = new Map(traceItems.map((item) => [String(item.key), item]));

  ui.pageContent.querySelectorAll("button[data-action='trace-filter']").forEach((button) => {
    button.addEventListener("click", () => {
      state.workView.traceFilter = helpers.t(button.dataset.filter, "all");
      router.render();
    });
  });

  ui.pageContent.querySelectorAll("button[data-action='trace-primary']").forEach((button) => {
    button.addEventListener("click", async () => {
      const item = traceByKey.get(String(button.dataset.key || ""));
      if (!item) return;
      const key = `trace-${item.key}`;
      if (!item.primaryAction?.run) {
        state.workView.messages[key] = "Done: review below in Work sections.";
        router.render();
        return;
      }
      state.workView.messages[key] = "Running...";
      router.render();
      await runWorkInlineAction(
        key,
        () => api.fetchJson(item.primaryAction.run.path, {
          method: item.primaryAction.run.method,
          body: JSON.stringify(item.primaryAction.run.body || {}),
        }),
        "Done"
      );
    });
  });

  ui.pageContent.querySelectorAll("button[data-action='trace-secondary']").forEach((button) => {
    button.addEventListener("click", async () => {
      const item = traceByKey.get(String(button.dataset.key || ""));
      if (!item) return;
      const action = item.secondaryActions?.[Number(button.dataset.secondaryIndex || "-1")];
      if (!action?.run) return;
      const key = `trace-${item.key}`;
      state.workView.messages[key] = "Running...";
      router.render();
      await runWorkInlineAction(
        key,
        () => api.fetchJson(action.run.path, {
          method: action.run.method,
          body: JSON.stringify(action.run.body || {}),
        }),
        "Done"
      );
    });
  });

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

  ui.pageContent.querySelectorAll("button[data-action='work-strategy-execute']").forEach((button) => {
    button.addEventListener("click", async () => {
      await runWorkInlineAction(
        `strategy-${button.dataset.id}`,
        () => api.executeStrategyAction(button.dataset.id),
        "Strategic action executed."
      );
      await loadWorkStrategyPendingActions();
      await loadDashboardPendingActions();
    });
  });

  ui.pageContent.querySelectorAll("button[data-action='work-strategy-reject']").forEach((button) => {
    button.addEventListener("click", async () => {
      await runWorkInlineAction(
        `strategy-${button.dataset.id}`,
        () => api.rejectStrategyAction(button.dataset.id),
        "Strategic action rejected."
      );
      await loadWorkStrategyPendingActions();
    });
  });

  ui.pageContent.querySelectorAll("button[data-action='work-strategy-toggle-analysis']").forEach((button) => {
    button.addEventListener("click", () => {
      const actionId = helpers.t(button.dataset.id, "");
      state.workView.expandedStrategicAnalyses[actionId] = !state.workView.expandedStrategicAnalyses[actionId];
      router.render();
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
  ui.pageContent.querySelectorAll("button[data-action='toggle-autonomy']").forEach((button) => {
    button.addEventListener("click", () => {
      state.autonomyEnabled = !state.autonomyEnabled;
      saveAutonomyEnabledState();
      if (state.currentRoute === "dashboard") {
        router.render();
      }
    });
  });

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

  ui.pageContent.querySelectorAll("button[data-action='dashboard-strategy-execute']").forEach((button) => {
    button.addEventListener("click", async () => {
      await runDashboardStrategyAction(
        () => api.executeStrategyAction(button.dataset.id),
        "Action executed successfully."
      );
    });
  });

  ui.pageContent.querySelectorAll("button[data-action='dashboard-strategy-reject']").forEach((button) => {
    button.addEventListener("click", async () => {
      await runDashboardStrategyAction(
        () => api.rejectStrategyAction(button.dataset.id),
        "Action rejected successfully."
      );
    });
  });
}

async function runDashboardStrategyAction(actionFn, successMessage) {
  try {
    await actionFn();
    state.dashboardView.feedback = successMessage;
    await loadDashboardPendingActions();
  } catch (error) {
    state.dashboardView.feedback = `Error: ${error.message}`;
    if (state.currentRoute === "dashboard") router.render();
  }
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

document.addEventListener("click", (e) => {
  const el = e.target.closest("[data-route]");
  if (!el) return;

  const route = el.dataset.route;
  if (route && location.hash !== route) {
    location.hash = route;
  }
});

ui.chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = ui.chatInput.value.trim();
  if (!input) return;

  const snapshot = getChatStateSnapshot();
  const decision = computeChatIntentDecision(input, snapshot, { chatMode: state.chatMode });
  state.chatCards.push({ id: `user-${Date.now()}`, type: "user", text: input });

  if (decision.requires_confirmation) {
    state.chatCards.push({
      id: `confirm-${Date.now()}`,
      type: "confirm",
      title: decision.ui?.title || "Confirm command",
      summary: decision.ui?.summary || "Do you want to execute this command?",
      decision,
    });
  } else {
    await executeDecision(decision);
  }

  ui.chatInput.value = "";
  renderConversation();
});

window.addEventListener("hashchange", () => router.render());

startRefreshLoop();
refreshLoop();
