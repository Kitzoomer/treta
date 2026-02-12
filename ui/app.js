const stateEl = document.getElementById("current-state");
const lastDecisionEl = document.getElementById("last-decision");
const lastScoreEl = document.getElementById("last-score");
const lastReasoningEl = document.getElementById("last-reasoning");
const eventsListEl = document.getElementById("events-list");
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
  lastDecisionEl.textContent = payload.decision ?? "-";
  lastScoreEl.textContent = payload.score ?? "-";
  lastReasoningEl.textContent = payload.reasoning ?? "-";
}

async function refresh() {
  const [stateResponse, eventsResponse] = await Promise.all([
    fetch("/state"),
    fetch("/events"),
  ]);

  const stateData = await stateResponse.json();
  const eventsData = await eventsResponse.json();

  stateEl.textContent = stateData.state ?? "unknown";
  renderEvents(eventsData.events || []);
}

async function simulateOpportunity() {
  await fetch("/event", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      type: "EvaluateOpportunity",
      source: "dashboard",
      payload: {
        money: 8,
        growth: 6,
        energy: 3,
        health: 2,
        relationships: 5,
        risk: 2,
      },
    }),
  });

  await refresh();
}

simulateButton.addEventListener("click", async () => {
  await simulateOpportunity();
});

refresh();
