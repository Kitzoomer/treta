const stateEl = document.getElementById("current-state");
const lastDecisionEl = document.getElementById("last-decision");
const lastScoreEl = document.getElementById("last-score");
const lastReasoningEl = document.getElementById("last-reasoning");
const eventsListEl = document.getElementById("events-list");
const opportunitiesListEl = document.getElementById("opportunities-list");
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

async function refresh() {
  const [stateResponse, eventsResponse, opportunitiesResponse] = await Promise.all([
    fetch("/state"),
    fetch("/events"),
    fetch("/opportunities"),
  ]);

  const stateData = await stateResponse.json();
  const eventsData = await eventsResponse.json();
  const opportunitiesData = await opportunitiesResponse.json();

  stateEl.textContent = stateData.state ?? "unknown";
  renderEvents(eventsData.events || []);
  renderOpportunities(opportunitiesData.items || []);
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
