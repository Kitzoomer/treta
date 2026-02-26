const CONFIG = {
  routes: ["home", "dashboard", "work", "profile", "game", "strategy", "reddit-ops", "decision-intelligence", "settings"],
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
  focusMode: "treta_focus_mode",
};

let focusModeEnabled = localStorage.getItem(STORAGE_KEYS.focusMode) !== "false";

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
  revenueSummary: null,
  dailyLoop: {
    phase: "IDLE",
    summary: "System operating normally.",
    next_action_label: "No Immediate Action",
    route: null,
    timestamp: null,
  },
  redditConfig: {
    pain_threshold: 60,
    pain_keywords: [],
    commercial_keywords: [],
    enable_engagement_boost: true,
  },
  redditScanResult: {
    analyzed: 0,
    qualified: 0,
    posts: [],
  },
  systemIntegrity: {
    status: "unknown",
  },
  redditLastScan: {
    message: "No scan executed yet.",
  },
  redditSignals: [],
  redditTodayPlan: {
    generated_at: null,
    signals: [],
    summary: "",
  },
  strategyDecision: {
    primary_focus: "unknown",
    confidence: 0,
    actions: [],
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
  redditDailyActions: [],
  settingsFeedback: {
    message: "",
    tone: "ok",
  },
  diagnostics: {
    showPanel: false,
    lastRefreshAt: {
      system: null,
      reddit: null,
      strategy: null,
      revenue: null,
    },
    lastApiErrors: {
      system: "",
      reddit: "",
      strategy: "",
      revenue: "",
    },
    sliceHealth: {
      system: { stale: false, lastSuccessAt: null, staleSince: null },
      reddit: { stale: false, lastSuccessAt: null, staleSince: null },
      strategy: { stale: false, lastSuccessAt: null, staleSince: null },
      revenue: { stale: false, lastSuccessAt: null, staleSince: null },
    },
    integrity: {
      lastStatusCode: 0,
      lastSuccessAt: null,
      lastError: "",
    },
    backendConnected: false,
    showDashboardMore: false,
  },
  routeBanner: {
    message: "",
    tone: "warn",
  },
  expandedTimelineEvents: {},
  debugMode: localStorage.getItem(STORAGE_KEYS.debug) === "true",
  refreshMs: Number(localStorage.getItem(STORAGE_KEYS.refreshMs) || CONFIG.defaultRefreshMs),
  profile: loadProfileState(),
  autonomyEnabled: localStorage.getItem(STORAGE_KEYS.autonomyEnabled) === "true",
  chatMode: localStorage.getItem(STORAGE_KEYS.chatMode) === "auto" ? "auto" : "manual",
  voiceEnabled: false,
  speakEnabled: true,
  voiceSupported: false,
  voiceStatusMessage: "",
  voiceAwaitingCommand: false,
  chatLoading: false,
  pendingVoiceConfirmation: null,
  currentRoute: CONFIG.defaultRoute,
  homeView: {
    focusModeActive: true,
  },
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
  redditOpsView: {
    selectedProposalId: "",
    copyByProposalId: {},
    messages: {},
    postingFormByProposalId: {},
    posts: [],
  },
  timerId: null,
};

function setHomeFocusMode(active) {
  focusModeEnabled = Boolean(active);
  state.homeView.focusModeActive = focusModeEnabled;
  localStorage.setItem(STORAGE_KEYS.focusMode, focusModeEnabled ? "true" : "false");
  const shouldEnableFocusMode = state.currentRoute === "home" && state.homeView.focusModeActive;
  document.body.classList.toggle("focus-mode-active", shouldEnableFocusMode);
}

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

const degradedMode = window.TretaDegradedMode || {
  preserveOnFailure(currentValue, nextValue, failed) {
    if (failed) return currentValue;
    if (nextValue === undefined || nextValue === null) return currentValue;
    return nextValue;
  },
  buildDegradedBannerModel() {
    return { show: false, reasons: [], staleSlices: [], message: "" };
  },
};

const voiceMode = window.TretaVoiceMode || null;

function normalizeEnvelopeItems(payload) {
  if (!payload || typeof payload !== "object") return [];
  if (Array.isArray(payload.items)) return payload.items;
  if (Array.isArray(payload.data)) return payload.data;
  if (Array.isArray(payload.data?.items)) return payload.data.items;
  return [];
}

function normalizeEnvelopeObject(payload) {
  if (!payload || typeof payload !== "object") return {};
  if (payload.data && typeof payload.data === "object") return payload.data;
  return payload;
}

async function renderStrategicDashboard(options = { mode: "full" }) {
  const mode = options?.mode === "focus" ? "focus" : "full";
  setHomeFocusMode(mode === "focus");

  let dashboardRoot = ui.pageContent.querySelector(".strategic-dashboard");
  if (!dashboardRoot) {
    ui.pageContent.innerHTML = `
      <div class="strategic-dashboard">
        <section class="focus-mode-switch">
          <button id="home-focus-mode" class="secondary-btn">Volver a Modo Enfoque</button>
          <button id="home-complete-mode" class="secondary-btn">Modo completo</button>
        </section>
        <section class="hero">
          <h1>Esto es lo que puedes vender esta semana.</h1>
          <p>Basado en lo que los creadores están preguntando ahora mismo.</p>
        </section>

        <section class="pain-overview">
          <h2>Oportunidad actual</h2>
          <strong id="dashboard-dominant-pain">Cargando señal dominante…</strong>
          <ul id="dashboard-top-pains">
            <li>Cargando señales…</li>
          </ul>
        </section>

        <section class="next-step">
          <h2>👉 Acción recomendada</h2>
          <p>Convierte este problema en una plantilla vendible:</p>
          <p>Producto recomendado: <span id="dashboard-recommended-product">Calculando producto recomendado…</span></p>
          <button id="create-offer-btn" data-route="#/work">Crear oferta ahora</button>
        </section>

        <section class="revenue-summary" data-focus-collapse>
          <h2>Progreso del negocio</h2>
          <p>Total ventas: <span id="dashboard-total-sales">—</span></p>
          <p>Total ingresos: <span id="dashboard-total-revenue">—</span></p>
          <p>Categoría más rentable: <span id="dashboard-top-category">—</span></p>
        </section>

        <details class="system-details" data-focus-collapse>
          <summary>System details</summary>
          <section class="stack">
            <p><strong>Daily loop:</strong> ${helpers.escape(helpers.t(state.dailyLoop?.phase, "IDLE"))}</p>
            <p><strong>Backend:</strong> <span class="badge ${state.diagnostics.backendConnected ? "ok" : "error"}">${state.diagnostics.backendConnected ? "CONNECTED" : "DISCONNECTED"}</span></p>
          </section>
          <section class="reddit-authority">
            <h2>🗣 Cómo hablar de esto en Reddit</h2>
            <ul>
              <li>Explica cómo resolver este problema paso a paso.</li>
              <li>Responde a 3 hilos esta semana aportando valor.</li>
              <li>Comparte tu plantilla solo cuando alguien lo pida.</li>
            </ul>
          </section>
        </details>
      </div>
    `;
    dashboardRoot = ui.pageContent.querySelector(".strategic-dashboard");
  }

  const collapsedSections = ui.pageContent.querySelectorAll("[data-focus-collapse]");
  collapsedSections.forEach((section) => {
    section.classList.toggle("dashboard-collapsed", mode === "focus");
  });

  const focusModeButton = document.getElementById("home-focus-mode");
  const completeModeButton = document.getElementById("home-complete-mode");
  if (focusModeButton) {
    focusModeButton.classList.toggle("dashboard-mode-active", mode === "focus");
    focusModeButton.classList.toggle("dashboard-hidden", mode === "focus");
    focusModeButton.onclick = () => renderStrategicDashboard({ mode: "focus" });
  }
  if (completeModeButton) {
    completeModeButton.classList.toggle("dashboard-mode-active", mode === "full");
    completeModeButton.classList.toggle("dashboard-hidden", mode !== "focus");
    completeModeButton.onclick = () => renderStrategicDashboard({ mode: "full" });
  }

  const dominantPainNode = document.getElementById("dashboard-dominant-pain");
  const recommendedProductNode = document.getElementById("dashboard-recommended-product");
  const topPainsNode = document.getElementById("dashboard-top-pains");
  const totalSalesNode = document.getElementById("dashboard-total-sales");
  const totalRevenueNode = document.getElementById("dashboard-total-revenue");
  const topCategoryNode = document.getElementById("dashboard-top-category");

  if (dominantPainNode) dominantPainNode.textContent = "Cargando señal dominante…";
  if (recommendedProductNode) recommendedProductNode.textContent = "Calculando producto recomendado…";
  if (topPainsNode) topPainsNode.innerHTML = "<li>Cargando señales…</li>";
  if (totalSalesNode) totalSalesNode.textContent = "—";
  if (totalRevenueNode) totalRevenueNode.textContent = "—";
  if (topCategoryNode) topCategoryNode.textContent = "—";

  try {
    const [demandPayload, suggestionsPayload, painsPayload, launchesSummaryPayload] = await Promise.all([
      api.fetchJson("/creator/demand"),
      api.fetchJson("/creator/product_suggestions"),
      api.fetchJson("/creator/pains"),
      api.fetchJson("/creator/launches/summary"),
    ]);

    const demandItems = normalizeEnvelopeItems(demandPayload);
    const suggestionItems = normalizeEnvelopeItems(suggestionsPayload);
    const painItems = normalizeEnvelopeItems(painsPayload);
    const launchesSummary = normalizeEnvelopeObject(launchesSummaryPayload);

    const demandByStrength = { strong: 3, moderate: 2, weak: 1 };
    const dominantPain = [...demandItems].sort((left, right) => {
      const leftStrength = demandByStrength[helpers.normalizeStatus(left.demand_strength)] || 0;
      const rightStrength = demandByStrength[helpers.normalizeStatus(right.demand_strength)] || 0;
      if (leftStrength !== rightStrength) return rightStrength - leftStrength;
      return Number(right.launch_priority_score || 0) - Number(left.launch_priority_score || 0);
    })[0] || painItems[0] || null;

    const dominantPainLabel = dominantPain?.pain_category || dominantPain?.pain || "Sin categoría dominante aún";
    const dominantPainKey = helpers.normalizeStatus(dominantPain?.pain_category || dominantPain?.pain || "");

    const associatedSuggestion = suggestionItems.find((item) => {
      const itemPain = helpers.normalizeStatus(item.pain_category || item.pain || "");
      return dominantPainKey && dominantPainKey === itemPain;
    }) || suggestionItems[0] || null;

    const topPains = [...demandItems]
      .sort((left, right) => Number(right.launch_priority_score || 0) - Number(left.launch_priority_score || 0))
      .slice(0, 3);

    const categoryRevenue = launchesSummary?.categories && typeof launchesSummary.categories === "object"
      ? launchesSummary.categories
      : {};
    const topCategoryByRevenue = launchesSummary?.top_category_by_revenue
      || Object.entries(categoryRevenue).sort((left, right) => Number((right[1] || {}).revenue || 0) - Number((left[1] || {}).revenue || 0))[0]?.[0]
      || "N/A";

    if (dominantPainNode) dominantPainNode.textContent = dominantPainLabel;
    if (recommendedProductNode) {
      recommendedProductNode.textContent = associatedSuggestion?.suggested_product || "Pendiente de sugerencia";
    }
    if (topPainsNode) {
      topPainsNode.innerHTML = topPains.length
        ? topPains.map((item) => `<li><strong>${helpers.escape(item.pain_category || "N/A")}</strong> · prioridad ${helpers.escape(helpers.t(item.launch_priority_score, "0"))} · ${helpers.escape(helpers.t(item.demand_strength, "unknown"))}</li>`).join("")
        : "<li>Sin datos todavía.</li>";
    }
    if (totalSalesNode) totalSalesNode.textContent = helpers.escape(helpers.t(launchesSummary?.total_sales, 0));
    if (totalRevenueNode) totalRevenueNode.textContent = helpers.escape(helpers.t(launchesSummary?.total_revenue, 0));
    if (topCategoryNode) topCategoryNode.textContent = topCategoryByRevenue;
  } catch (_error) {
    if (dominantPainNode) dominantPainNode.textContent = "No se pudo identificar el pain dominante ahora.";
    if (recommendedProductNode) recommendedProductNode.textContent = "No se pudo cargar el producto sugerido.";
    if (topPainsNode) topPainsNode.innerHTML = "<li class=\"empty\">No se pudo cargar el dashboard estratégico en este momento.</li>";
  }
}

async function renderFocusMode() {
  return renderStrategicDashboard({ mode: "focus" });
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
  getRevenueSummary() {
    return this.fetchJson("/revenue/summary");
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
  getRedditConfig() {
    return this.fetchJson("/reddit/config");
  },
  saveRedditConfig(payload) {
    return this.fetchJson("/reddit/config", { method: "POST", body: JSON.stringify(payload) });
  },
  runRedditScan() {
    return this.fetchJson("/reddit/run_scan", { method: "POST", body: JSON.stringify({}) });
  },
  getSystemIntegrity() {
    return this.fetchJson("/system/integrity");
  },
  async getSystemIntegrityStatus() {
    const response = await fetch("/system/integrity", { headers: { "Content-Type": "application/json" } });
    const text = await response.text();
    let data = {};
    if (text) {
      try {
        data = JSON.parse(text);
      } catch (_error) {
        data = { raw: text };
      }
    }
    return { ok: response.ok, statusCode: response.status, data };
  },
  getRedditLastScan() {
    return this.fetchJson("/reddit/last_scan");
  },
  getRedditSignals(limit = 50) {
    return this.fetchJson(`/reddit/signals?limit=${encodeURIComponent(limit)}`);
  },
  getRedditTodayPlan() {
    return this.fetchJson("/reddit/today_plan");
  },
  getRedditDailyActions(limit = 5) {
    return this.fetchJson(`/reddit/daily_actions?limit=${encodeURIComponent(limit)}`);
  },
  getStrategyDecision() {
    return this.fetchJson("/strategy/decide");
  },
  markRedditPosted(payload) {
    return this.fetchJson("/reddit/mark_posted", { method: "POST", body: JSON.stringify(payload) });
  },
  getRedditPosts() {
    return this.fetchJson("/reddit/posts");
  },
  sendConversationMessage(text, source = "text") {
    return this.fetchJson("/conversation/message", { method: "POST", body: JSON.stringify({ text, source }) });
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
  formatTimestamp(value) {
    if (!value) return "Never";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "Never";
    return date.toLocaleTimeString();
  },
  isCoreSlice(slice) {
    return ["system", "reddit", "strategy", "revenue"].includes(slice);
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
    const isReadyForExecution = proposalStatus === "ready_to_launch";
    const isReadyForLaunch = proposalStatus === "ready_for_review";

    let primaryAction = { label: "View details", route: "#/work", run: null };
    if (proposalId && proposalStatus === "draft") {
      primaryAction = { label: "Approve", route: "#/work", run: { method: "POST", path: `/product_proposals/${proposalId}/approve`, body: {} } };
    } else if (proposalId && proposalStatus === "approved" && !plan) {
      primaryAction = { label: "Build plan", route: "#/work", run: { method: "POST", path: "/product_plans/build", body: { proposal_id: proposalId } } };
    } else if (proposalId && plan && isReadyForExecution && !["launched", "archived"].includes(proposalStatus)) {
      primaryAction = { label: "Mark ready", route: "#/work", run: { method: "POST", path: `/product_proposals/${proposalId}/ready`, body: {} } };
    } else if (proposalId && isReadyForLaunch && !launch) {
      primaryAction = { label: "Launch", route: "#/work", run: { method: "POST", path: `/product_proposals/${proposalId}/launch`, body: {} } };
    } else if (launch?.id && launchStatus && launchStatus !== "active") {
      primaryAction = { label: "Set status active", route: "#/work", run: { method: "POST", path: `/product_launches/${launch.id}/status`, body: { status: "active" } } };
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

function renderLifecycleTrace({ hasOpportunity, hasProposal, isBuilding, isReady, isLaunched, hasStrategyPending }) {
  const steps = [
    { label: "Opportunity", done: hasOpportunity },
    { label: "Proposal", done: hasProposal },
    { label: "Build", done: isBuilding || isReady || isLaunched },
    { label: "Launch", done: isLaunched },
    { label: "Strategy", done: hasStrategyPending },
  ];

  return `
    <div class="lifecycle-trace">
      ${steps.map((step) => `
        <span class="lifecycle-step ${step.done ? "done" : "pending"}">
          ${step.done ? "✔" : "•"} ${step.label}
        </span>
      `).join("")}
    </div>
  `;
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

  const launchReadyItems = launches.filter((launch) => helpers.normalizeStatus(launch.status) !== "active");
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
  const hasLaunchReady = launches.some((launch) => helpers.normalizeStatus(launch.status) !== "active");
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
  normalizeRoute(route) {
    const raw = helpers.t(route, "").trim().toLowerCase();
    if (!raw) return "#/home";
    if (raw.startsWith("#/")) return `#/${raw.slice(2).replace(/^\/+/, "")}`;
    if (raw.startsWith("#")) return `#/${raw.slice(1).replace(/^\/+/, "")}`;
    return `#/${raw.replace(/^\/+/, "")}`;
  },
  normalizeRouteHash(route) {
    return this.normalizeRoute(route);
  },
  resolveRoute() {
    const normalized = this.normalizeRoute(window.location.hash || "");
    const route = normalized.slice(2);
    if (CONFIG.routes.includes(route)) return { route, valid: true };
    return { route: CONFIG.defaultRoute, valid: false, attempted: normalized };
  },
  navigate(route) {
    window.location.hash = this.normalizeRoute(route);
  },
  render() {
    const resolution = this.resolveRoute();
    state.currentRoute = resolution.route;
    document.body.dataset.route = state.currentRoute;
    document.body.classList.toggle("focus-mode-active", state.currentRoute === "home" && state.homeView.focusModeActive);
    renderNavigation();
    if (state.currentRoute === "home") return views.loadHome();
    if (state.currentRoute === "dashboard") return views.loadDashboard();
    if (state.currentRoute === "work") return views.loadWork();
    if (state.currentRoute === "profile") return views.loadProfile();
    if (state.currentRoute === "game") return views.loadGame();
    if (state.currentRoute === "strategy") return views.loadStrategy();
    if (state.currentRoute === "reddit-ops") return views.loadRedditOps();
    if (state.currentRoute === "decision-intelligence") return views.loadDecisionIntelligence();
    return views.loadSettings();
  },
};

const views = {
  shell(title, subtitle, body) {
    const phase = helpers.t(state.dailyLoop?.phase, "IDLE").toUpperCase();
    ui.pageContent.innerHTML = `
      <div class="card" style="margin-bottom: 12px; padding: 10px 14px;">
        <strong>Daily Loop Phase:</strong> <span class="badge info">${helpers.escape(phase)}</span>
        <span style="margin-left: 10px;">Backend: <span class="badge ${state.diagnostics.backendConnected ? "ok" : "error"}">${state.diagnostics.backendConnected ? "CONNECTED" : "DISCONNECTED"}</span></span>
      </div>
      ${renderRouteBanner()}
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
    const savedFocusMode = localStorage.getItem(STORAGE_KEYS.focusMode);
    focusModeEnabled = savedFocusMode !== "false";
    if (focusModeEnabled) {
      return renderFocusMode();
    }
    return renderStrategicDashboard();
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

    const degradedBanner = degradedMode.buildDegradedBannerModel({
      diagnostics: state.diagnostics,
      refreshMs: state.refreshMs,
    });
    const renderDegradedModeBanner = () => {
      if (!degradedBanner.show) return "";
      const staleDetails = degradedBanner.staleSlices.map((item) => {
        const lastSuccess = helpers.formatTimestamp(item.lastSuccessAt);
        return `<li><strong>${helpers.escape(item.slice)}:</strong> stale · last successful ${helpers.escape(lastSuccess)}</li>`;
      }).join("");
      return `
        <article class="card degraded-banner">
          <h3>Operator Limited mode</h3>
          <p>${helpers.escape(degradedBanner.message)}</p>
          ${staleDetails ? `<ul class="mission-actionable-list">${staleDetails}</ul>` : ""}
          <div class="card-actions wrap">
            <button data-action="dashboard-force-refresh">Scan again</button>
            <button class="secondary-btn" data-action="dashboard-run-integrity">Run system check</button>
          </div>
        </article>
      `;
    };

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
            <div class="metric"><span>Revenue potential</span><strong>${helpers.escape(helpers.t(topStrategicAction?.expected_impact_score, "-"))}</strong></div>
          </section>
        </article>
      `;
    };

    const renderRevenueSummary = () => {
      const summary = state.revenueSummary;
      if (!summary) {
        return `<p><strong>Revenue:</strong> unavailable</p>`;
      }
      const totals = summary.totals || {};
      const trackedRevenue = Number(totals.revenue || 0).toFixed(2);
      const trackedSales = Number(totals.sales || 0);
      const bySubreddit = summary.by_subreddit && typeof summary.by_subreddit === "object" ? summary.by_subreddit : {};
      const topSubreddit = Object.entries(bySubreddit)
        .sort((left, right) => Number((right[1] || {}).revenue || 0) - Number((left[1] || {}).revenue || 0))[0]?.[0];

      return `
        <p><strong>Revenue (tracked):</strong> $${helpers.escape(trackedRevenue)} — ${helpers.escape(trackedSales)} sales</p>
        ${topSubreddit ? `<p><strong>Top subreddit:</strong> ${helpers.escape(topSubreddit)}</p>` : ""}
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
                  <span class="dashboard-risk-badge ${helpers.riskBadgeClass(risk)}">Execution risk: ${helpers.escape(risk)}</span>
                </div>
                <p><strong>Action type:</strong> ${helpers.escape(actionType)}</p>
                <p><strong>Revenue potential:</strong> ${helpers.escape(impactScore)}</p>
                <div class="card-actions">
                  <div>
                    <button data-action="dashboard-strategy-execute" data-id="${helpers.escape(item.id)}">Launch</button>
                    <p class="control-helper">Publishes the offer and starts tracking revenue.</p>
                  </div>
                  <div>
                    <button class="secondary-btn" data-action="dashboard-strategy-reject" data-id="${helpers.escape(item.id)}">Skip for now</button>
                    <p class="control-helper">Keeps the opportunity for later review.</p>
                  </div>
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
    const integrityStatusRaw = helpers.normalizeStatus(state.systemIntegrity?.status || "unknown");
    const integrityStatusLabel = integrityStatusRaw === "critical"
      ? "error"
      : ["healthy", "warning", "error"].includes(integrityStatusRaw)
        ? integrityStatusRaw
        : "unknown";
    const integrityTone = integrityStatusLabel === "healthy"
      ? "ok"
      : integrityStatusLabel === "warning"
        ? "warn"
        : integrityStatusLabel === "error"
          ? "error"
          : "info";
    const lastScanHasData = Number.isFinite(Number(state.redditLastScan?.analyzed)) || Number.isFinite(Number(state.redditLastScan?.qualified));
    const lastScanAnalyzed = Number(state.redditLastScan?.analyzed || 0);
    const lastScanQualified = Number(state.redditLastScan?.qualified || 0);
    const lastScanTimestamp = state.redditLastScan?.timestamp || state.redditLastScan?.last_scan_at || state.redditLastScan?.scanned_at;
    const lastScanDate = lastScanTimestamp ? new Date(lastScanTimestamp).toLocaleString() : "-";
    const strategyDecision = state.strategyDecision || {};
    const strategyDecisionLabel = helpers.t(strategyDecision.primary_focus, "unknown").replaceAll("_", " ");
    const strategyDecisionScore = helpers.t(strategyDecision.confidence, "-");
    const strategyDecisionActionLabel = helpers.t(strategyDecision.actions?.[0]?.type, "No immediate action").replaceAll("_", " ");

    const redditSignals = Array.isArray(state.redditSignals) ? state.redditSignals : [];
    const painThreshold = Number(
      state.redditLastScan?.pain_threshold
      || state.redditConfig?.pain_threshold
      || 0,
    );
    const intentDistribution = redditSignals.reduce((acc, signal) => {
      const intent = helpers.t(signal.intent, signal.intent_level || signal.intent_type || "unknown");
      acc[intent] = (acc[intent] || 0) + 1;
      return acc;
    }, {});
    const urgencyDistribution = redditSignals.reduce((acc, signal) => {
      const urgency = helpers.t(signal.urgency, signal.urgency_level || "unknown");
      acc[urgency] = (acc[urgency] || 0) + 1;
      return acc;
    }, {});
    const getSignalPainScore = (signal) => Number(signal.pain_score ?? signal.opportunity_score ?? signal.score ?? 0);
    const topSignals = [...redditSignals]
      .sort((left, right) => getSignalPainScore(right) - getSignalPainScore(left))
      .slice(0, 5);
    const hasFeedbackAdjustedSignals = redditSignals.some((signal) => {
      const hasAdjustmentField = signal.performance_adjustment !== undefined
        && signal.performance_adjustment !== null
        && signal.performance_adjustment !== "";
      const reasoning = helpers.normalizeStatus(signal.reasoning || "");
      const adjustedByReasoning = reasoning.includes("adapted")
        || reasoning.includes("boosted")
        || reasoning.includes("reduced");
      return hasAdjustmentField || adjustedByReasoning;
    });
    const todayPlan = state.redditTodayPlan || {};
    const todayPlanSignals = Array.isArray(todayPlan.signals) ? todayPlan.signals.length : 0;
    const renderDistribution = (distribution) => {
      const rows = Object.entries(distribution)
        .sort(([leftKey], [rightKey]) => leftKey.localeCompare(rightKey))
        .map(([label, count]) => `<li>${helpers.escape(label)}: ${helpers.escape(count)}</li>`)
        .join("");
      return rows || "<li class='muted-note'>No signals yet.</li>";
    };
    const renderTopSignals = () => {
      if (!topSignals.length) return "<p class='empty'>No Reddit signals available.</p>";
      return `
        <div class="dashboard-strategy-list">
          ${topSignals.map((signal) => {
            const title = helpers.t(signal.title, signal.post_text || signal.post_title || "Untitled");
            const trimmedTitle = title.length > 88 ? `${title.slice(0, 85)}…` : title;
            const subreddit = helpers.t(signal.subreddit, "-");
            const painScore = getSignalPainScore(signal);
            const intent = helpers.t(signal.intent, signal.intent_level || signal.intent_type || "-");
            const urgency = helpers.t(signal.urgency, signal.urgency_level || "-");
            const adjustment = signal.performance_adjustment;
            const adjustmentLabel = adjustment === undefined || adjustment === null || adjustment === ""
              ? "-"
              : adjustment;
            return `
              <article class="dashboard-strategy-card">
                <div class="dashboard-strategy-meta">
                  <span class="badge info">Pain: ${helpers.escape(painScore)}</span>
                  <span class="dashboard-risk-badge risk-neutral">r/${helpers.escape(subreddit)}</span>
                </div>
                <p><strong>Title:</strong> ${helpers.escape(trimmedTitle)}</p>
                <p><strong>Intent:</strong> ${helpers.escape(intent)} · <strong>Urgency:</strong> ${helpers.escape(urgency)}</p>
                <p><strong>Performance adjustment:</strong> ${helpers.escape(adjustmentLabel)}</p>
              </article>
            `;
          }).join("")}
        </div>
      `;
    };

    this.shell("Dashboard", "Operational summary and next best action", `
      <section class="os-dashboard">
        ${renderDegradedModeBanner()}
        ${renderGlobalStatus()}
        ${renderAutonomyControls()}
        <article class="card">
          <h3>System Coherence</h3>
          <p><strong>Integrity:</strong> <span class="badge ${integrityTone}">${helpers.escape(integrityStatusLabel.toUpperCase())}</span></p>
          <div class="card-actions wrap dashboard-operator-actions">
            <button data-action="dashboard-force-refresh">Scan again</button>
            <button class="secondary-btn" data-action="dashboard-run-integrity">Run system check</button>
          </div>
          ${lastScanHasData
    ? `<p><strong>Last scan:</strong> analyzed ${helpers.escape(lastScanAnalyzed)} · qualified ${helpers.escape(lastScanQualified)}</p>
             <p><strong>Last scan date:</strong> ${helpers.escape(lastScanDate)}</p>`
    : "<p><strong>Last scan:</strong> No scan yet</p>"}
          <p><strong>Decision:</strong> ${helpers.escape(strategyDecisionLabel)}</p>
          <p><strong>Decision score:</strong> ${helpers.escape(strategyDecisionScore)}</p>
          <p><strong>Action label:</strong> ${helpers.escape(strategyDecisionActionLabel)}</p>
        </article>
        <div id="attention-block"></div>
        ${renderRevenueFocus()}

        <article class="card">
          <h3>Backend</h3>
          <p><strong>Status:</strong> <span class="badge ${state.diagnostics.backendConnected ? "ok" : "error"}">${state.diagnostics.backendConnected ? "CONNECTED" : "DISCONNECTED"}</span></p>
          ${renderRevenueSummary()}
          <p class="muted-note">Preview mode without backend will show disconnected status.</p>
        </article>

        <article class="card os-strategic-actions" id="dashboard-strategic-actions">
          <h3>🧠 STRATEGIC ACTIONS</h3>
          ${strategyError}
          ${strategyFeedback}
          ${renderStrategicCompact()}
        </article>

        <article class="card" id="dashboard-reddit-engine-status">
          <h3>REDDIT ENGINE STATUS</h3>
          <p><strong>Scan Summary:</strong> analyzed ${helpers.escape(lastScanAnalyzed)} · qualified ${helpers.escape(lastScanQualified)} · pain threshold ${helpers.escape(painThreshold)}</p>
          <section class="card-grid cols-2">
            <div>
              <h4>Intent Distribution</h4>
              <ul>${renderDistribution(intentDistribution)}</ul>
            </div>
            <div>
              <h4>Urgency Distribution</h4>
              <ul>${renderDistribution(urgencyDistribution)}</ul>
            </div>
          </section>
          <p><strong>Today plan:</strong> ${helpers.escape(todayPlanSignals)} signals ${todayPlan.generated_at ? `· generated ${helpers.escape(new Date(todayPlan.generated_at).toLocaleString())}` : ""}</p>
          <p><strong>Feedback adjustments detected:</strong> <span class="badge ${hasFeedbackAdjustedSignals ? "warn" : "info"}">${hasFeedbackAdjustedSignals ? "YES" : "NO"}</span></p>
          <h4>Top 5 Signals (pain score)</h4>
          ${renderTopSignals()}
        </article>

        <article class="card">
          <details class="system-details">
            <summary>System details</summary>
            <div class="card-actions wrap">
              <button data-action="dashboard-toggle-more" class="secondary-btn">${state.diagnostics.showDashboardMore ? "Hide" : "Show"} More Observability</button>
              <button data-action="dashboard-toggle-diagnostics" class="secondary-btn">${state.diagnostics.showPanel ? "Hide" : "Show"} Diagnostics</button>
            </div>
            ${state.diagnostics.showDashboardMore ? `
              <div class="stack">
                <p><strong>Today plan summary:</strong> ${helpers.escape(helpers.t(state.redditTodayPlan?.summary, "No plan yet."))}</p>
                <p><strong>Daily actions count:</strong> ${helpers.escape((state.redditDailyActions || []).length)}</p>
                <p><strong>Top 5 signals exposed:</strong> ${(state.redditSignals || []).slice(0, 5).map((item) => helpers.escape(helpers.t(item.title, item.post_title || "Untitled"))).join(" · ") || "-"}</p>
              </div>
            ` : ""}
            ${state.diagnostics.showPanel ? renderDiagnosticsPanel() : ""}
          </details>
        </article>
      </section>
    `);
    renderMissionControl(state.dailyLoop);
    bindDashboardActions();
    if (!dashboardView.loading && !dashboardView.loaded) {
      loadDashboardPendingActions();
    }
  },

  async loadDecisionIntelligence() {
    const component = window.TretaDecisionIntelligence;
    if (!component || typeof component.render !== "function") {
      this.shell(
        "Decision Intelligence",
        "Latest strategic decisions and execution signals.",
        '<section class="card"><p class="error">Decision Intelligence component is unavailable.</p></section>'
      );
      return;
    }

    await component.render({ target: ui.pageContent, api });
  },

  loadWork() {
    const transitionLabels = {
      approve: "Approve",
      reject: "Skip for now",
      ready: "Mark Ready",
      launch: "Launch",
    };

    const transitionHelpers = {
      approve: "Moves this proposal into the build stage.",
      reject: "Keeps the opportunity for later review.",
      launch: "Publishes the offer and starts tracking revenue.",
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

    const renderNextActionBlock = (statusLabel, nextActionLabel) => `
      <div style="margin: 8px 0 10px; padding: 8px 10px; border-left: 3px solid rgba(99, 102, 241, 0.5); background: rgba(99, 102, 241, 0.08); border-radius: 6px;">
        <p class="muted-note" style="margin: 0;"><strong>Status:</strong> ${helpers.escape(statusLabel)}</p>
        <p style="margin: 4px 0 0;"><strong>Next Action:</strong> ${helpers.escape(nextActionLabel)}</p>
      </div>
    `;

    const renderOpportunityCard = (item) => {
      return `
        <article class="card row-item">
          <h4>${helpers.escape(helpers.t(item.title, item.id))}</h4>
          ${renderLifecycleTrace({
            hasOpportunity: true,
            hasProposal: false,
            isBuilding: false,
            isReady: false,
            isLaunched: false,
            hasStrategyPending,
          })}
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
        const helperText = transitionHelpers[transition] || "";
        return `
          <div>
            <button class="secondary-btn" data-action="proposal" data-transition="${helpers.escape(transition)}" data-id="${helpers.escape(proposalId)}">
              ${helpers.escape(transitionLabels[transition] || helpers.statusLabel(transition))}
            </button>
            ${helperText ? `<p class="control-helper">${helpers.escape(helperText)}</p>` : ""}
          </div>
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
          ${renderLifecycleTrace({
            hasOpportunity: true,
            hasProposal: true,
            isBuilding: statusLabel === "Building",
            isReady: statusLabel === "Ready to Launch",
            isLaunched: false,
            hasStrategyPending,
          })}
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
    const hasStrategyPending = state.strategyPendingActions.length > 0;

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
          ${renderLifecycleTrace({
            hasOpportunity: true,
            hasProposal: true,
            isBuilding: false,
            isReady: false,
            isLaunched: true,
            hasStrategyPending,
          })}
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
        <style>
          .lifecycle-trace {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin: 6px 0 10px 0;
            font-size: 12px;
            opacity: 0.85;
          }

          .lifecycle-step.done {
            color: #6cff8f;
          }

          .lifecycle-step.pending {
            color: #666;
          }
        </style>
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
    const redditConfig = state.redditConfig || {};
    const redditScan = state.redditScanResult || { posts: [] };
    const bySubreddit = redditScan.by_subreddit || {};
    const bySubredditRows = Object.entries(bySubreddit).map(([subreddit, count]) => `<li>${helpers.t(subreddit, "-")}: ${Number(count || 0)}</li>`).join("");
    const scanRows = (redditScan.posts || []).map((post) => `
      <tr>
        <td>${helpers.t(post.title, "-")}</td>
        <td>${helpers.t(post.subreddit, "-")}</td>
        <td>${Number(post.pain_score || 0)}</td>
        <td>${helpers.t(post.intent_type, "-")}</td>
        <td>${helpers.t(post.urgency_level, "-")}</td>
      </tr>
    `).join("");

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
      </section>

      <section class="card">
        <h3>Reddit Intelligence Settings</h3>
        <div class="settings-grid">
          <label>Pain Threshold <input id="reddit-pain-threshold" type="number" min="0" max="100" value="${Number(redditConfig.pain_threshold || 60)}"></label>
          <label>Engagement boost <input id="reddit-engagement-boost" type="checkbox" ${redditConfig.enable_engagement_boost ? "checked" : ""}></label>
          <label>Pain Keywords (comma separated)
            <textarea id="reddit-pain-keywords" rows="4">${(redditConfig.pain_keywords || []).join(", ")}</textarea>
          </label>
          <label>Subreddits (comma separated)
            <textarea id="reddit-subreddits" rows="4">${(redditConfig.subreddits || ["UGCcreators", "freelance", "ContentCreators", "smallbusiness"]).join(", ")}</textarea>
          </label>
          <label>Commercial Keywords (comma separated)
            <textarea id="reddit-commercial-keywords" rows="4">${(redditConfig.commercial_keywords || []).join(", ")}</textarea>
          </label>
        </div>
        <div class="card-actions wrap">
          <button id="reddit-save-settings">Save Settings</button>
          <button id="reddit-run-scan">Run Scan Now</button>
        </div>
        <section id="settings-response" class="result-box ${state.settingsFeedback.tone === "error" ? "error" : ""}">${helpers.escape(state.settingsFeedback.message || "Ready.")}</section>
        <section class="result-box">
          <strong>Scan Result</strong>
          <div>Analyzed: ${Number(redditScan.analyzed || 0)} | Qualified: ${Number(redditScan.qualified || 0)}</div>
          <div>By subreddit:</div>
          <ul>${bySubredditRows || '<li class="muted-note">No subreddit counts yet.</li>'}</ul>
          <div class="work-table-wrap">
            <table class="work-table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Subreddit</th>
                  <th>Pain Score</th>
                  <th>Intent</th>
                  <th>Urgency</th>
                </tr>
              </thead>
              <tbody>
                ${scanRows || '<tr><td colspan="5" class="muted-note">No scan results yet.</td></tr>'}
              </tbody>
            </table>
          </div>
        </section>
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

    document.getElementById("reddit-save-settings")?.addEventListener("click", async () => {
      const payload = {
        pain_threshold: Number(document.getElementById("reddit-pain-threshold")?.value || 60),
        pain_keywords: String(document.getElementById("reddit-pain-keywords")?.value || "").split(",").map((item) => item.trim()).filter(Boolean),
        commercial_keywords: String(document.getElementById("reddit-commercial-keywords")?.value || "").split(",").map((item) => item.trim()).filter(Boolean),
        enable_engagement_boost: Boolean(document.getElementById("reddit-engagement-boost")?.checked),
        subreddits: String(document.getElementById("reddit-subreddits")?.value || "").split(",").map((item) => item.trim()).filter(Boolean),
      };
      await runAction(async () => {
        const updated = await api.saveRedditConfig(payload);
        state.redditConfig = updated;
        state.settingsFeedback = { message: "Settings saved successfully.", tone: "ok" };
        return updated;
      }, ACTION_TARGETS.settings);
      router.render();
      window.setTimeout(() => {
        state.settingsFeedback = { message: "", tone: "ok" };
        if (state.currentRoute === "settings") router.render();
      }, 3000);
    });

    document.getElementById("reddit-run-scan")?.addEventListener("click", async () => {
      await runAction(async () => {
        const result = await api.runRedditScan();
        state.redditScanResult = result;
        state.redditLastScan = result;
        state.settingsFeedback = { message: "Scan completed.", tone: "ok" };
        return result;
      }, ACTION_TARGETS.settings);
      await refreshLoop();
      router.render();
      window.setTimeout(() => {
        state.settingsFeedback = { message: "", tone: "ok" };
        if (state.currentRoute === "settings") router.render();
      }, 3000);
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
                  <div class="metric"><span>Reference ID</span><strong>${escapedActionId}</strong></div>
                  <div class="metric"><span>action_type</span><strong>${helpers.escape(helpers.t(item.action_type, "unknown"))}</strong></div>
                  <div class="metric"><span>priority</span><strong><span class="badge ${helpers.priorityBadgeClass(item.priority)}">${helpers.escape(helpers.t(item.priority, "unknown"))}</span></strong></div>
                  <div class="metric"><span>Execution risk</span><strong><span class="badge ${helpers.riskBadgeClass(item.risk_level)}">${helpers.escape(helpers.t(item.risk_level, "unknown"))}</span></strong></div>
                  <div class="metric"><span>Revenue potential</span><strong>${helpers.escape(helpers.t(item.expected_impact_score, "-"))}</strong></div>
                  <div class="metric"><span>auto_executable</span><strong>${item.auto_executable ? "true" : "false"}</strong></div>
                </section>
                <div class="card-actions wrap" style="margin-top: 12px;">
                  <div>
                    <button data-action="strategy-execute" data-id="${actionId}">Launch</button>
                    <p class="control-helper">Publishes the offer and starts tracking revenue.</p>
                  </div>
                  <div>
                    <button class="secondary-btn" data-action="strategy-reject" data-id="${actionId}">Skip for now</button>
                    <p class="control-helper">Keeps the opportunity for later review.</p>
                  </div>
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
            <div class="metric"><span>Execution risk</span><strong>${helpers.t(recommendation.risk_level, "Risk not specified")}</strong></div>
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
          <details class="system-details">
            <summary>System details</summary>
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
          </details>
        </article>
      </section>
    `);

    bindStrategyActions();
    if (!strategyView.loading && !strategyView.loaded) {
      loadStrategyData();
    }
  },

  loadRedditOps() {
    const pendingProposals = state.proposals.filter((item) => ["ready_to_launch", "ready_for_review"].includes(helpers.normalizeStatus(item.status)));
    const view = state.redditOpsView;
    const selectedProposalId = view.selectedProposalId;
    const selectedProposal = pendingProposals.find((item) => String(item.id) === String(selectedProposalId));
    const selectedCopy = view.copyByProposalId[selectedProposalId] || selectedProposal?.execution_package || null;
    const redditPost = selectedCopy?.reddit_post || {};
    const copySections = [
      { label: "Reddit Post Title", value: helpers.t(redditPost.title, "") },
      { label: "Reddit Post Body", value: helpers.t(redditPost.body, "") },
      { label: "Short Pitch", value: helpers.t(selectedCopy?.short_pitch, "") },
      { label: "Gumroad Description", value: helpers.t(selectedCopy?.gumroad_description, "") },
      { label: "Pricing Strategy", value: helpers.t(selectedCopy?.pricing_strategy, "") },
    ];

    const renderPendingCard = (item) => {
      const proposalId = helpers.t(item.id, "");
      return `
        <article class="card row-item">
          <h4>${helpers.escape(helpers.t(item.product_name, proposalId))}</h4>
          <p><strong>Audience:</strong> ${helpers.escape(helpers.t(item.target_audience, "-"))}</p>
          <p><strong>Price Suggestion:</strong> ${helpers.escape(helpers.t(item.price_suggestion, "-"))}</p>
          <p><strong>Status:</strong> <span class="badge ${helpers.badgeClass(item.status)}">${helpers.escape(helpers.statusLabel(item.status))}</span></p>
          <p><strong>Confidence:</strong> ${helpers.escape(helpers.t(item.confidence, "-"))}</p>
          <div class="card-actions work-secondary-actions">
            <button class="secondary-btn" data-action="reddit-ops-view-copy" data-id="${helpers.escape(proposalId)}">View Copy</button>
            <button class="secondary-btn" data-action="reddit-ops-approve" data-id="${helpers.escape(proposalId)}">Approve</button>
            <button class="secondary-btn" data-action="reddit-ops-reject" data-id="${helpers.escape(proposalId)}">Skip for now</button>
          </div>
          ${view.messages[`proposal-${proposalId}`] ? `<p class="muted-note">${helpers.escape(view.messages[`proposal-${proposalId}`])}</p>` : ""}
        </article>
      `;
    };

    const form = view.postingFormByProposalId[selectedProposalId] || {
      subreddit: "",
      post_url: "",
      upvotes: "",
      comments: "",
    };

    this.shell("Reddit Ops", "Opportunity → Proposal → Launch Copy → Approve → Mark Posted → Track", `
      <section class="work-execution">
        <article class="card work-section">
          <header class="work-section-header">
            <h3>A) Pending Launch Actions</h3>
          </header>
          <section class="work-status-group">
            ${pendingProposals.length ? pendingProposals.map(renderPendingCard).join("") : "<p class='empty'>No proposals pending launch actions.</p>"}
          </section>
        </article>

        <article class="card work-section">
          <header class="work-section-header">
            <h3>B) Launch Package</h3>
          </header>
          ${selectedProposalId ? `
            <p class="muted-note">Proposal selected: <strong>${helpers.escape(selectedProposalId)}</strong></p>
            <div class="work-copy-grid">
              ${copySections.map((section) => `
                <article class="copy-block">
                  <header>
                    <h4>${helpers.escape(section.label)}</h4>
                    <button class="secondary-btn" data-action="reddit-ops-copy" data-id="${helpers.escape(selectedProposalId)}" data-copy-value="${encodeURIComponent(section.value)}">Copy</button>
                  </header>
                  <textarea readonly rows="5">${helpers.escape(section.value)}</textarea>
                </article>
              `).join("")}
            </div>
          ` : "<p class='empty'>Select a proposal and click “View Copy”.</p>"}
          ${view.messages[`copy-${selectedProposalId}`] ? `<p class="muted-note">${helpers.escape(view.messages[`copy-${selectedProposalId}`])}</p>` : ""}
        </article>

        <article class="card work-section">
          <header class="work-section-header">
            <h3>C) Mark As Posted</h3>
          </header>
          ${selectedProposalId ? `
            <div class="card-actions">
              <button class="secondary-btn" data-action="reddit-ops-show-posted-form" data-id="${helpers.escape(selectedProposalId)}">Mark as Posted</button>
            </div>
            ${view.postingFormByProposalId[selectedProposalId]?.visible ? `
              <div class="settings-grid" style="margin-top: 10px;">
                <label>Subreddit<input data-reddit-ops-input="subreddit" data-id="${helpers.escape(selectedProposalId)}" value="${helpers.escape(form.subreddit)}" /></label>
                <label>Post URL<input data-reddit-ops-input="post_url" data-id="${helpers.escape(selectedProposalId)}" value="${helpers.escape(form.post_url)}" /></label>
                <label>Manual Upvotes (optional)<input type="number" data-reddit-ops-input="upvotes" data-id="${helpers.escape(selectedProposalId)}" value="${helpers.escape(form.upvotes)}" /></label>
                <label>Manual Comments (optional)<input type="number" data-reddit-ops-input="comments" data-id="${helpers.escape(selectedProposalId)}" value="${helpers.escape(form.comments)}" /></label>
              </div>
              <div class="card-actions" style="margin-top: 10px;">
                <button class="btn" data-action="reddit-ops-mark-posted" data-id="${helpers.escape(selectedProposalId)}">Save Posted Link</button>
              </div>
            ` : ""}
            ${view.messages[`posted-${selectedProposalId}`] ? `<p class="muted-note">${helpers.escape(view.messages[`posted-${selectedProposalId}`])}</p>` : ""}
          ` : "<p class='empty'>Select a proposal to mark as posted.</p>"}
        </article>

        <article class="card work-section">
          <header class="work-section-header">
            <h3>D) Recent Posts</h3>
          </header>
          ${view.posts.length ? `
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>Subreddit</th>
                    <th>Date</th>
                    <th>Upvotes</th>
                    <th>Comments</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  ${view.posts.map((item) => `
                    <tr>
                      <td>${helpers.escape(helpers.t(item.product_name, item.proposal_id))}</td>
                      <td>${helpers.escape(helpers.t(item.subreddit, "-"))}</td>
                      <td>${helpers.escape(helpers.t(item.date, item.created_at || "-"))}</td>
                      <td>${helpers.escape(helpers.t(item.upvotes, 0))}</td>
                      <td>${helpers.escape(helpers.t(item.comments, 0))}</td>
                      <td><span class="badge ${helpers.badgeClass(item.status)}">${helpers.escape(helpers.statusLabel(item.status || "open"))}</span></td>
                    </tr>
                  `).join("")}
                </tbody>
              </table>
            </div>
          ` : "<p class='empty'>No tracked reddit posts yet.</p>"}
        </article>

        <article class="card"><h3>Action output</h3><section id="reddit-ops-response" class="result-box">Ready.</section></article>
      </section>
    `);
    bindRedditOpsActions();
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
  const primaryNav = [
    { route: "home", label: "Home" },
    { route: "work", label: "Opportunities" },
    { route: "reddit-ops", label: "Offers" },
    { route: "dashboard", label: "Revenue" },
    { route: "strategy", label: "System" },
    { route: "decision-intelligence", label: "Decision Intelligence" },
    { route: "settings", label: "Settings" },
  ];

  const isSystemActive = ["strategy", "dashboard"].includes(active);

  ui.pageNav.innerHTML = `
    ${primaryNav.map((item) => `<button class="nav-btn ${item.route === active ? "active" : ""}" data-route="#/${item.route}">${item.label}</button>`).join("")}
    <details class="nav-system-details" ${isSystemActive ? "open" : ""}>
      <summary>System details</summary>
      <div class="nav-system-content">
        <button class="nav-btn secondary-btn ${active === "dashboard" ? "active" : ""}" data-route="#/dashboard">Diagnostics &amp; Integrity</button>
        <button class="nav-btn secondary-btn ${active === "strategy" ? "active" : ""}" data-route="#/strategy">Telemetry &amp; Daily Loop</button>
      </div>
      <p class="muted-note">Advanced status panels, logs, and operational diagnostics.</p>
    </details>
  `;
}

function log(role, message) {
  if (!state.debugMode) return;
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

      if (item.text) {
        const text = helpers.escape(helpers.t(item.text, ""));
        return `
          <article class="chat-message assistant">
            <div class="chat-role">assistant</div>
            <div>${text}</div>
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
  title.innerHTML = `Conversation <span class="chat-mode-toggle"><button type="button" class="secondary-btn ${state.chatMode === "manual" ? "active" : ""}" data-action="chat-mode" data-mode="manual">Manual</button><button type="button" class="secondary-btn ${state.chatMode === "auto" ? "active" : ""}" data-action="chat-mode" data-mode="auto">Auto</button><button type="button" class="secondary-btn voice-toggle ${state.voiceEnabled ? "active" : ""}" data-action="voice-toggle">Voice Mode: ${state.voiceEnabled ? "ON" : "OFF"}</button><button type="button" class="secondary-btn ${state.speakEnabled ? "active" : ""}" data-action="speak-toggle">Speak: ${state.speakEnabled ? "ON" : "OFF"}</button><span class="voice-indicator ${state.voiceEnabled ? "on" : "off"}" aria-label="Voice mode status"></span></span>`;

  const existingBanner = ui.chatPanel.querySelector(".voice-support-banner");
  if (existingBanner) existingBanner.remove();
  if (!state.voiceSupported) {
    const banner = document.createElement("p");
    banner.className = "voice-support-banner";
    banner.textContent = "Voice not supported in this browser";
    ui.chatPanel.insertBefore(banner, ui.chatHistory);
  }

  const existingStatus = ui.chatPanel.querySelector(".voice-status");
  if (existingStatus) existingStatus.remove();
  if (state.voiceStatusMessage) {
    const status = document.createElement("p");
    status.className = "voice-status";
    status.textContent = state.voiceStatusMessage;
    ui.chatPanel.insertBefore(status, ui.chatHistory);
  }

  title.querySelectorAll("button[data-action='chat-mode']").forEach((button) => {
    button.addEventListener("click", () => {
      state.chatMode = button.dataset.mode === "auto" ? "auto" : "manual";
      saveChatModeState();
      renderCommandBar();
    });
  });

  title.querySelector("button[data-action='voice-toggle']")?.addEventListener("click", () => {
    setVoiceEnabled(!state.voiceEnabled);
  });

  title.querySelector("button[data-action='speak-toggle']")?.addEventListener("click", () => {
    state.speakEnabled = !state.speakEnabled;
    if (!state.speakEnabled && voiceMode) voiceMode.stopTts();
    renderCommandBar();
  });
}

function startVoice() {
  if (!voiceMode) return false;
  return voiceMode.startVoice();
}

function stopVoice() {
  if (!voiceMode) return;
  voiceMode.stopVoice();
}

function setVoiceEnabled(enabled) {
  if (!state.voiceSupported || !voiceMode) {
    state.voiceEnabled = false;
    state.voiceStatusMessage = "Voice not supported in this browser";
    renderCommandBar();
    return;
  }

  state.voiceEnabled = Boolean(enabled);
  state.voiceAwaitingCommand = false;
  if (state.voiceEnabled) {
    const started = startVoice();
    state.voiceStatusMessage = started ? "Listening for wake word: Treta" : "No se pudo iniciar el micrófono";
    if (!started) state.voiceEnabled = false;
  } else {
    stopVoice();
    state.pendingVoiceConfirmation = null;
    state.voiceStatusMessage = "Voice mode OFF";
  }
  renderCommandBar();
}

function setChatLoading(isLoading) {
  state.chatLoading = Boolean(isLoading);
  if (ui.chatInput) ui.chatInput.disabled = state.chatLoading;
  const submitButton = ui.chatForm?.querySelector("button[type='submit']");
  if (submitButton) {
    submitButton.disabled = state.chatLoading;
    submitButton.textContent = state.chatLoading ? "Sending..." : "Send";
  }
}

function handleAssistantResponse(text) {
  const reply = helpers.t(text, "I couldn't process that.");
  state.chatCards.push({ id: `assistant-${Date.now()}`, type: "assistant", text: `Treta: ${reply}` });
  if (state.voiceEnabled && voiceMode) voiceMode.speak(reply);
  renderConversation();
}

async function submitUserMessage(rawText, { source = "text" } = {}) {
  const input = helpers.t(rawText, "").trim();
  if (!input || state.chatLoading) return;

  const labelPrefix = source === "voice" ? "(heard) " : "";
  state.chatCards.push({ id: `user-${Date.now()}`, type: "user", text: `${labelPrefix}${input}` });
  renderConversation();

  setChatLoading(true);
  try {
    const response = await api.sendConversationMessage(input, source);
    handleAssistantResponse(helpers.t(response.reply_text, "No response from assistant."));
  } catch (error) {
    handleAssistantResponse(`Error: ${error.message}`);
  } finally {
    setChatLoading(false);
  }
}

async function onTranscript(payload) {
  const transcript = helpers.t(payload?.text, "").trim();
  if (!transcript) return;
  const lower = transcript.toLowerCase();

  let commandText = "";
  const wakeIndex = lower.indexOf("treta");
  if (wakeIndex >= 0) {
    const afterWake = transcript.slice(wakeIndex + "treta".length).replace(/^\s*[,.:-]?\s*/, "").trim();
    if (afterWake) {
      commandText = afterWake;
      state.voiceAwaitingCommand = false;
    } else {
      state.voiceAwaitingCommand = true;
      state.voiceStatusMessage = "Wake word detectada. Esperando comando...";
      renderCommandBar();
      return;
    }
  } else if (state.voiceAwaitingCommand && payload?.isFinal) {
    commandText = transcript;
    state.voiceAwaitingCommand = false;
  }

  if (!commandText || !payload?.isFinal) return;

  await submitUserMessage(commandText, { source: "voice" });
}

function initVoiceIntegration() {
  if (!voiceMode) {
    state.voiceSupported = false;
    state.voiceStatusMessage = "Voice not supported in this browser";
    return;
  }

  const voiceInit = voiceMode.initVoiceMode({
    onTranscript,
    onError: (errorCode) => {
      state.voiceStatusMessage = `Voice error: ${errorCode}`;
      if (errorCode === "not-allowed" || errorCode === "service-not-allowed") {
        state.voiceEnabled = false;
      }
      renderCommandBar();
    },
  });

  state.voiceSupported = Boolean(voiceInit?.supported);
  if (!state.voiceSupported) {
    state.voiceEnabled = false;
    state.voiceStatusMessage = "Voice not supported in this browser";
  }
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
  let spokenResponse = "";
  if (!decision) return;
  if (decision.intent === "navigate") {
    const route = decision.ui?.cta?.route;
    if (route) router.navigate(route.replace("#/", ""));
    state.chatCards.push({ id: `assistant-${Date.now()}`, type: "assistant", decision, card: { ...decision.ui, details: "Navigation applied." } });
    spokenResponse = decision.ui?.summary || "";
    renderConversation();
    return spokenResponse;
  }

  if (decision.action.kind === "no_op") {
    state.chatCards.push({ id: `assistant-${Date.now()}`, type: "assistant", decision, card: decision.ui });
    spokenResponse = decision.ui?.summary || "";
    renderConversation();
    return spokenResponse;
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

    const backendResponse = helpers.t(callResults[0] ? JSON.stringify(callResults[0].result) : "OK", "OK");
    state.chatCards.push({
      id: `assistant-${Date.now()}`,
      type: "assistant",
      decision,
      card: {
        title: decision.ui?.title || "Done",
        summary: `${decision.intent === "query" ? "Query completed" : "Command executed"}.`,
        details: backendResponse,
        cta: decision.ui?.cta,
      },
    });
    spokenResponse = backendResponse;
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
    spokenResponse = `Error: ${error.message}`;
  }
  renderConversation();
  return spokenResponse;
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
  const markSliceSuccess = (slice) => {
    const now = Date.now();
    state.diagnostics.lastRefreshAt[slice] = now;
    state.diagnostics.lastApiErrors[slice] = "";
    state.diagnostics.sliceHealth[slice] = {
      stale: false,
      lastSuccessAt: now,
      staleSince: null,
    };
  };

  const markSliceFailure = (slice, errorMessage) => {
    const previous = state.diagnostics.sliceHealth[slice] || {};
    state.diagnostics.lastApiErrors[slice] = errorMessage;
    state.diagnostics.sliceHealth[slice] = {
      stale: true,
      lastSuccessAt: previous.lastSuccessAt || null,
      staleSince: previous.staleSince || Date.now(),
    };
  };

  const sliceCalls = {
    system: async () => {
      const [systemData, eventData, memoryData, oppData, proposalData, launchData, planData, perfData, dailyLoopData, systemIntegrityResult] = await Promise.all([
        api.getState(),
        api.getRecentEvents(),
        api.getMemory(),
        api.getOpportunities(),
        api.getProductProposals(),
        api.getProductLaunches(),
        api.getProductPlans(),
        api.getPerformanceSummary(),
        api.getDailyLoopStatus(),
        api.getSystemIntegrityStatus(),
      ]);
      state.system = degradedMode.preserveOnFailure(state.system, systemData || { state: "IDLE" }, false);
      state.events = degradedMode.preserveOnFailure(state.events, eventData?.events || [], false);
      state.chatHistory = degradedMode.preserveOnFailure(state.chatHistory, memoryData?.chat_history || [], false);
      state.opportunities = degradedMode.preserveOnFailure(state.opportunities, oppData?.items || [], false);
      state.proposals = degradedMode.preserveOnFailure(state.proposals, proposalData?.items || [], false);
      state.launches = degradedMode.preserveOnFailure(state.launches, launchData?.items || [], false);
      state.plans = degradedMode.preserveOnFailure(state.plans, planData?.items || [], false);
      state.performance = degradedMode.preserveOnFailure(state.performance, perfData || {}, false);
      state.dailyLoop = degradedMode.preserveOnFailure(state.dailyLoop, dailyLoopData || state.dailyLoop, false);

      state.diagnostics.integrity.lastStatusCode = Number(systemIntegrityResult.statusCode || 0);
      if (systemIntegrityResult.ok) {
        state.systemIntegrity = degradedMode.preserveOnFailure(state.systemIntegrity, systemIntegrityResult.data || state.systemIntegrity, false);
        state.diagnostics.integrity.lastSuccessAt = Date.now();
        state.diagnostics.integrity.lastError = "";
      } else {
        const integrityMessage = systemIntegrityResult.data?.error || `HTTP ${systemIntegrityResult.statusCode}`;
        state.diagnostics.integrity.lastError = integrityMessage;
        state.diagnostics.lastApiErrors.system = `integrity limited mode: ${integrityMessage}`;
      }

      markSliceSuccess("system");
      state.diagnostics.backendConnected = true;
    },
    strategy: async () => {
      const [strategyData, pendingData, strategyDecisionData] = await Promise.all([
        api.getStrategyRecommendations(),
        api.getPendingStrategyActions(),
        api.getStrategyDecision(),
      ]);
      state.strategy = degradedMode.preserveOnFailure(state.strategy, strategyData || {}, false);
      const pendingActions = pendingData?.items || pendingData?.actions || pendingData?.pending_actions || [];
      state.strategyPendingActions = degradedMode.preserveOnFailure(state.strategyPendingActions, pendingActions, false);
      state.dashboardView.pendingActions = degradedMode.preserveOnFailure(state.dashboardView.pendingActions, pendingActions, false);
      state.dashboardView.loaded = true;
      state.dashboardView.loading = false;
      state.dashboardView.error = "";
      state.strategyDecision = degradedMode.preserveOnFailure(state.strategyDecision, strategyDecisionData || state.strategyDecision, false);
      markSliceSuccess("strategy");
    },
    revenue: async () => {
      const revenueSummaryData = await api.getRevenueSummary();
      const normalized = revenueSummaryData?.totals
        ? revenueSummaryData
        : (revenueSummaryData?.ok ? revenueSummaryData.data : null);
      state.revenueSummary = degradedMode.preserveOnFailure(state.revenueSummary, normalized, false);
      markSliceSuccess("revenue");
    },
    reddit: async () => {
      const [redditConfigData, redditLastScanData, redditSignalsData, redditTodayPlanData, redditDailyActionsData, redditPostsData] = await Promise.all([
        api.getRedditConfig(),
        api.getRedditLastScan(),
        api.getRedditSignals(50),
        api.getRedditTodayPlan(),
        api.getRedditDailyActions(5),
        api.getRedditPosts(),
      ]);
      state.redditConfig = degradedMode.preserveOnFailure(state.redditConfig, redditConfigData || state.redditConfig, false);
      state.redditLastScan = degradedMode.preserveOnFailure(state.redditLastScan, redditLastScanData || state.redditLastScan, false);
      state.redditSignals = degradedMode.preserveOnFailure(state.redditSignals, redditSignalsData?.items || [], false);
      state.redditTodayPlan = degradedMode.preserveOnFailure(state.redditTodayPlan, redditTodayPlanData || state.redditTodayPlan, false);
      state.redditDailyActions = degradedMode.preserveOnFailure(state.redditDailyActions, Array.isArray(redditDailyActionsData) ? redditDailyActionsData : [], false);
      state.redditOpsView.posts = degradedMode.preserveOnFailure(state.redditOpsView.posts, redditPostsData?.items || [], false);
      markSliceSuccess("reddit");
    },
  };

  for (const [slice, task] of Object.entries(sliceCalls)) {
    try {
      await task();
    } catch (error) {
      markSliceFailure(slice, error.message);
      if (slice === "system") {
        state.diagnostics.backendConnected = false;
      }
      log("system", `${slice} refresh error: ${error.message}`);
    }
  }

  renderControlCenter();
  renderTelemetry();
  router.render();
}

function bindRedditOpsActions() {
  const responseBox = document.getElementById("reddit-ops-response");

  ui.pageContent.querySelectorAll("button[data-action='reddit-ops-approve']").forEach((button) => {
    button.addEventListener("click", async () => {
      const proposalId = button.dataset.id;
      await runAction(() => api.fetchJson(`/product_proposals/${proposalId}/approve`, { method: "POST", body: JSON.stringify({}) }), "reddit-ops-response");
      state.redditOpsView.messages[`proposal-${proposalId}`] = "Proposal approved.";
      router.render();
    });
  });

  ui.pageContent.querySelectorAll("button[data-action='reddit-ops-reject']").forEach((button) => {
    button.addEventListener("click", async () => {
      const proposalId = button.dataset.id;
      await runAction(() => api.fetchJson(`/product_proposals/${proposalId}/reject`, { method: "POST", body: JSON.stringify({}) }), "reddit-ops-response");
      state.redditOpsView.messages[`proposal-${proposalId}`] = "Proposal rejected.";
      router.render();
    });
  });

  ui.pageContent.querySelectorAll("button[data-action='reddit-ops-view-copy']").forEach((button) => {
    button.addEventListener("click", async () => {
      const proposalId = helpers.t(button.dataset.id, "");
      state.redditOpsView.selectedProposalId = proposalId;
      try {
        const proposal = await api.fetchJson(`/product_proposals/${proposalId}`);
        if (proposal?.execution_package) {
          state.redditOpsView.copyByProposalId[proposalId] = proposal.execution_package;
        }
      } catch (_error) {
        state.redditOpsView.messages[`copy-${proposalId}`] = "Unable to refresh copy from backend.";
      }
      router.render();
    });
  });

  ui.pageContent.querySelectorAll("button[data-action='reddit-ops-copy']").forEach((button) => {
    button.addEventListener("click", async () => {
      const proposalId = helpers.t(button.dataset.id, "");
      const raw = decodeURIComponent(button.dataset.copyValue || "");
      try {
        await navigator.clipboard.writeText(raw);
        state.redditOpsView.messages[`copy-${proposalId}`] = "Copied to clipboard.";
      } catch (_error) {
        state.redditOpsView.messages[`copy-${proposalId}`] = "Clipboard unavailable in this environment.";
      }
      router.render();
    });
  });

  ui.pageContent.querySelectorAll("button[data-action='reddit-ops-show-posted-form']").forEach((button) => {
    button.addEventListener("click", () => {
      const proposalId = helpers.t(button.dataset.id, "");
      const current = state.redditOpsView.postingFormByProposalId[proposalId] || {};
      state.redditOpsView.postingFormByProposalId[proposalId] = { ...current, visible: true };
      router.render();
    });
  });

  ui.pageContent.querySelectorAll("button[data-action='reddit-ops-mark-posted']").forEach((button) => {
    button.addEventListener("click", async () => {
      const proposalId = helpers.t(button.dataset.id, "");
      const subreddit = helpers.t(ui.pageContent.querySelector(`input[data-reddit-ops-input='subreddit'][data-id='${proposalId}']`)?.value, "").trim();
      const postUrl = helpers.t(ui.pageContent.querySelector(`input[data-reddit-ops-input='post_url'][data-id='${proposalId}']`)?.value, "").trim();
      const upvotesRaw = helpers.t(ui.pageContent.querySelector(`input[data-reddit-ops-input='upvotes'][data-id='${proposalId}']`)?.value, "").trim();
      const commentsRaw = helpers.t(ui.pageContent.querySelector(`input[data-reddit-ops-input='comments'][data-id='${proposalId}']`)?.value, "").trim();

      state.redditOpsView.postingFormByProposalId[proposalId] = {
        visible: true,
        subreddit,
        post_url: postUrl,
        upvotes: upvotesRaw,
        comments: commentsRaw,
      };

      const payload = {
        proposal_id: proposalId,
        subreddit,
        post_url: postUrl,
      };
      if (upvotesRaw !== "") payload.upvotes = Number(upvotesRaw);
      if (commentsRaw !== "") payload.comments = Number(commentsRaw);

      await runAction(() => api.markRedditPosted(payload), "reddit-ops-response");
      state.redditOpsView.messages[`posted-${proposalId}`] = "Post tracked successfully.";
      router.render();
    });
  });

  if (responseBox && !responseBox.textContent.trim()) {
    responseBox.textContent = "Ready.";
  }
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

function renderRouteBanner() {
  if (!state.routeBanner.message) return "";
  return `<div class="card" style="margin-bottom: 12px; padding: 10px 14px;">
    <strong>Route notice:</strong> <span class="badge ${helpers.escape(state.routeBanner.tone)}">${helpers.escape(state.routeBanner.tone.toUpperCase())}</span>
    <p>${helpers.escape(state.routeBanner.message)}</p>
  </div>`;
}

function renderDiagnosticsPanel() {
  const refreshRows = ["system", "reddit", "strategy", "revenue"]
    .map((slice) => `<li>${helpers.escape(slice)}: ${helpers.escape(helpers.formatTimestamp(state.diagnostics.lastRefreshAt[slice]))}</li>`)
    .join("");
  const errorRows = ["system", "reddit", "strategy", "revenue"]
    .map((slice) => `<li>${helpers.escape(slice)}: ${helpers.escape(state.diagnostics.lastApiErrors[slice] || "none")}</li>`)
    .join("");
  return `
    <section class="stack">
      <p><strong>Last refresh by slice</strong></p>
      <ul>${refreshRows}</ul>
      <p><strong>Last API errors</strong></p>
      <ul>${errorRows}</ul>
    </section>
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

  ui.pageContent.querySelectorAll("button[data-action='dashboard-toggle-more']").forEach((button) => {
    button.addEventListener("click", () => {
      state.diagnostics.showDashboardMore = !state.diagnostics.showDashboardMore;
      router.render();
    });
  });

  ui.pageContent.querySelectorAll("button[data-action='dashboard-toggle-diagnostics']").forEach((button) => {
    button.addEventListener("click", () => {
      state.diagnostics.showPanel = !state.diagnostics.showPanel;
      router.render();
    });
  });

  ui.pageContent.querySelectorAll("button[data-action='dashboard-force-refresh']").forEach((button) => {
    button.addEventListener("click", async () => {
      state.dashboardView.feedback = "Force refresh requested…";
      if (state.currentRoute === "dashboard") router.render();
      await refreshLoop();
      state.dashboardView.feedback = "Force refresh completed.";
      if (state.currentRoute === "dashboard") router.render();
    });
  });

  ui.pageContent.querySelectorAll("button[data-action='dashboard-run-integrity']").forEach((button) => {
    button.addEventListener("click", async () => {
      await runIntegrityNow();
    });
  });
}

async function runIntegrityNow() {
  try {
    const integrityResult = await api.getSystemIntegrityStatus();
    state.diagnostics.integrity.lastStatusCode = integrityResult.statusCode;
    state.systemIntegrity = integrityResult.data || state.systemIntegrity;
    if (integrityResult.ok) {
      state.diagnostics.integrity.lastSuccessAt = Date.now();
      state.diagnostics.integrity.lastError = "";
      state.dashboardView.feedback = "Integrity check completed.";
    } else {
      const message = integrityResult.data?.error || `HTTP ${integrityResult.statusCode}`;
      state.diagnostics.integrity.lastError = message;
      state.dashboardView.feedback = `Integrity check limited mode: ${message}`;
    }
  } catch (error) {
    state.diagnostics.integrity.lastError = error.message;
    state.dashboardView.feedback = `Integrity check failed: ${error.message}`;
  }
  if (state.currentRoute === "dashboard") router.render();
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

  const normalizedRoute = router.normalizeRouteHash(el.dataset.route || "");
  if (normalizedRoute && location.hash !== normalizedRoute) {
    location.hash = normalizedRoute;
  }
});

ui.chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = ui.chatInput.value.trim();
  if (!input) return;

  await submitUserMessage(input, { source: "text" });
  ui.chatInput.value = "";
  renderConversation();
});

initVoiceIntegration();

const initialResolution = router.resolveRoute();
if (!initialResolution.valid) {
  state.routeBanner = { message: `Route ${initialResolution.attempted || ""} not found. Redirected to home.`, tone: "warn" };
  router.navigate(CONFIG.defaultRoute);
  window.setTimeout(() => {
    state.routeBanner.message = "";
    if (state.currentRoute === CONFIG.defaultRoute) router.render();
  }, 3000);
}

window.addEventListener("hashchange", () => {
  const resolution = router.resolveRoute();
  if (!resolution.valid) {
    state.routeBanner = { message: `Route ${resolution.attempted || ""} not found. Redirected to home.`, tone: "warn" };
    router.navigate(CONFIG.defaultRoute);
    window.setTimeout(() => {
      state.routeBanner.message = "";
      if (state.currentRoute === CONFIG.defaultRoute) router.render();
    }, 3000);
    return;
  }
  router.render();
});

startRefreshLoop();
refreshLoop();
