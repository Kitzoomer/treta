const stateEl = document.getElementById("current-state");
const lastDecisionEl = document.getElementById("last-decision");
const lastScoreEl = document.getElementById("last-score");
const lastReasoningEl = document.getElementById("last-reasoning");
const eventsListEl = document.getElementById("events-list");
const opportunitiesListEl = document.getElementById("opportunities-list");
const productProposalsListEl = document.getElementById("product-proposals-list");
const simulateButton = document.getElementById("simulate-opportunity");

function renderEvents(events) {
  eventsListEl.innerHTML = "";

  if (!events.length) {
    const empty = document.createElement("li");
    empty.textContent = "No events yet.";
    eventsListEl.appendChild(empty);
    return;
  }

  for (const event of events) {
    const item = document.createElement("li");
    item.textContent = `${event.timestamp} · ${event.type} (${event.source})`;
    eventsListEl.appendChild(item);
  }

  const lastDecisionEvent = [...events]
    .reverse()
    .find((event) => event.type === "OpportunityEvaluated");

  if (!lastDecisionEvent) {
    return;
  }

  const payload = lastDecisionEvent.payload || {};
  const decisionPayload = payload.decision || payload;
  lastDecisionEl.textContent = decisionPayload.decision ?? "-";
  lastScoreEl.textContent = decisionPayload.score ?? "-";
  lastReasoningEl.textContent = decisionPayload.reasoning ?? "-";
}

function renderOpportunities(items) {
  opportunitiesListEl.innerHTML = "";
  const recent = [...items].slice(-10).reverse();

  if (!recent.length) {
    const empty = document.createElement("li");
    empty.textContent = "No opportunities detected yet.";
    opportunitiesListEl.appendChild(empty);
    return;
  }

  for (const item of recent) {
    const li = document.createElement("li");
    const decision = item.decision || {};
    const score = decision.score != null ? `score=${decision.score}` : "score=-";
    const outcome = decision.decision != null ? `decision=${decision.decision}` : "decision=-";
    li.textContent = `${item.title} [${item.status}] · ${score} · ${outcome}`;
    opportunitiesListEl.appendChild(li);
  }
}

function renderProductProposals(items) {
  productProposalsListEl.innerHTML = "";
  const recent = [...items].slice(0, 5);

  if (!recent.length) {
    const empty = document.createElement("li");
    empty.textContent = "No product proposals generated yet.";
    productProposalsListEl.appendChild(empty);
    return;
  }

  for (const item of recent) {
    const li = document.createElement("li");
    li.textContent = `${item.product_name} · €${item.price_suggestion} · ${item.target_audience} · confidence=${item.confidence} · ${item.reasoning}`;
    productProposalsListEl.appendChild(li);
  }
}

async function refresh() {
  const [stateResponse, eventsResponse, opportunitiesResponse, proposalsResponse] = await Promise.all([
    fetch("/state"),
    fetch("/events"),
    fetch("/opportunities"),
    fetch("/product_proposals"),
  ]);

  const stateData = await stateResponse.json();
  const eventsData = await eventsResponse.json();
  const opportunitiesData = await opportunitiesResponse.json();
  const proposalsData = await proposalsResponse.json();

  stateEl.textContent = stateData.state ?? "unknown";
  renderEvents(eventsData.events || []);
  renderOpportunities(opportunitiesData.items || []);
  renderProductProposals(proposalsData.items || []);
}

async function simulateOpportunity() {
  const id = `demo-${Date.now()}`;
  await fetch("/event", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      type: "OpportunityDetected",
      source: "dashboard",
      payload: {
        id,
        source: "dashboard",
        title: "Demo opportunity",
        summary: "Simulated from dashboard",
        opportunity: {
          money: 8,
          growth: 6,
          energy: 3,
          health: 2,
          relationships: 5,
          risk: 2,
        },
      },
    }),
  });

  await fetch("/opportunities/evaluate", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ id }),
  });

  await refresh();
}

simulateButton.addEventListener("click", async () => {
  await simulateOpportunity();
});

refresh();
