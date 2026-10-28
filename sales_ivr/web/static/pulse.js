const pulseFab = document.getElementById("pulseFab");
const pulsePanel = document.getElementById("pulsePanel");
const pulseGate = document.getElementById("pulseGate");
const pulsePassword = document.getElementById("pulsePassword");
const pulseError = document.getElementById("pulseError");
const pulseBody = document.getElementById("pulseBody");
const pulseClose = document.getElementById("pulseClose");
const pulseStats = document.getElementById("pulseStats");
const pulseAgents = document.getElementById("pulseAgents");
const pulseRecent = document.getElementById("pulseRecent");

const PASSWORD_KEY = "pulse-admin-password";
let pulseTimer = null;

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function money(amount) {
  const value = Number(amount) || 0;
  if (value >= 0.01) return `$${value.toFixed(2)}`;
  if (value === 0) return "$0.00";
  return `$${value.toFixed(6)}`;
}

function openPulse() {
  pulsePanel.hidden = false;
  const saved = sessionStorage.getItem(PASSWORD_KEY);
  if (saved) {
    loadPulse(saved);
    return;
  }
  pulseBody.hidden = true;
  pulseGate.hidden = false;
  pulsePassword.focus();
}

function closePulse() {
  pulsePanel.hidden = true;
  if (pulseTimer) {
    clearInterval(pulseTimer);
    pulseTimer = null;
  }
}

async function loadPulse(password) {
  const response = await fetch("/api/admin/pulse", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  if (response.status === 401) {
    sessionStorage.removeItem(PASSWORD_KEY);
    pulseBody.hidden = true;
    pulseGate.hidden = false;
    pulseError.hidden = false;
    return;
  }
  if (!response.ok) {
    throw new Error("Pulse could not load");
  }
  sessionStorage.setItem(PASSWORD_KEY, password);
  pulseError.hidden = true;
  pulseGate.hidden = true;
  pulseBody.hidden = false;
  renderPulse(await response.json());
  if (!pulseTimer) {
    pulseTimer = setInterval(() => {
      const current = sessionStorage.getItem(PASSWORD_KEY);
      if (current && !pulsePanel.hidden) loadPulse(current).catch(() => {});
    }, 8000);
  }
}

function renderPulse(data) {
  const cards = [
    ["Calls", data.call_count],
    ["Cost", money(data.cost_usd)],
    ["Tokens", data.total_tokens],
    ["Prompt / completion", `${data.prompt_tokens} / ${data.completion_tokens}`],
    ["Avg latency", `${data.avg_latency_ms} ms`],
    ["P95 latency", `${data.p95_latency_ms} ms`],
  ];
  pulseStats.innerHTML = cards
    .map(([label, value]) => `<div class="pulse-stat"><span>${label}</span><strong>${value}</strong></div>`)
    .join("");

  if (!data.agents.length) {
    pulseAgents.innerHTML = `<p class="pulse-empty">No AI calls yet. Start a quote and usage will show up here.</p>`;
    pulseRecent.innerHTML = "";
    return;
  }

  pulseAgents.innerHTML = `<table class="pulse-table">
    <thead><tr><th>Agent</th><th>Calls</th><th>Tokens</th><th>Cost</th><th>Latency</th></tr></thead>
    <tbody>
      ${data.agents
        .map(
          (agent) => `<tr>
            <td>${escapeHtml(agent.agent_name)}</td>
            <td>${agent.calls}</td>
            <td>${agent.prompt_tokens}/${agent.completion_tokens}</td>
            <td>${money(agent.cost_usd)}</td>
            <td>${agent.avg_latency_ms} ms</td>
          </tr>`
        )
        .join("")}
    </tbody>
  </table>`;

  pulseRecent.innerHTML = `<table class="pulse-table">
    <thead><tr><th>When</th><th>Agent</th><th>Model</th><th>Tokens</th><th>Cost</th></tr></thead>
    <tbody>
      ${data.recent
        .map((call) => {
          const when = new Date(call.at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
          return `<tr>
            <td>${when}</td>
            <td>${escapeHtml(call.agent_name)}</td>
            <td>${escapeHtml(call.model)}</td>
            <td>${call.total_tokens}</td>
            <td>${money(call.cost_usd)}</td>
          </tr>`;
        })
        .join("")}
    </tbody>
  </table>`;
}

pulseFab.addEventListener("click", () => {
  if (pulsePanel.hidden) openPulse();
  else closePulse();
});

pulseClose.addEventListener("click", closePulse);

pulseGate.addEventListener("submit", async (event) => {
  event.preventDefault();
  pulseError.hidden = true;
  try {
    await loadPulse(pulsePassword.value);
  } catch (err) {
    pulseError.hidden = false;
    pulseError.textContent = err.message;
  }
});
