const workspace = document.getElementById("workspace");
const steps = document.getElementById("steps");
const messagesEl = document.getElementById("messages");
const resultEmpty = document.getElementById("resultEmpty");
const resultLoading = document.getElementById("resultLoading");
const resultBody = document.getElementById("resultBody");
const jsonDetails = document.getElementById("jsonDetails");
const sessionJson = document.getElementById("sessionJson");
const stepPill = document.getElementById("stepPill");
const startBtn = document.getElementById("startBtn");
const newBtn = document.getElementById("newBtn");
const form = document.getElementById("chatForm");
const input = document.getElementById("input");

let sessionId = null;
let lastResult = null;

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function addBubble(role, content) {
  const div = document.createElement("div");
  div.className = `bubble ${role}`;
  div.textContent = content.replace(/\*\*(.*?)\*\*/g, "$1");
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

function showTyping() {
  hideTyping();
  const el = document.createElement("div");
  el.className = "bubble assistant typing";
  el.id = "typingIndicator";
  el.setAttribute("aria-label", "Agent is typing");
  el.innerHTML = "<span></span><span></span><span></span>";
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function hideTyping() {
  document.getElementById("typingIndicator")?.remove();
}

const EDGE_WAIT_MS = 400;
let edgeLock = { dir: 0, since: 0 };

function relayWheelToPage(event, scroller) {
  const delta = event.deltaY;
  if (!delta) return;

  const maxScroll = scroller.scrollHeight - scroller.clientHeight;
  const canScroll = maxScroll > 1;
  const atTop = scroller.scrollTop <= 0;
  const atBottom = scroller.scrollTop >= maxScroll - 1;
  const towardTop = delta < 0;
  const atOutboundEdge =
    (towardTop && atTop) || (!towardTop && atBottom);

  // Still scrolling inside the chat — clear any edge wait.
  if (canScroll && !atOutboundEdge) {
    edgeLock = { dir: 0, since: 0 };
    return;
  }

  // No overflow yet: page scroll right away.
  if (!canScroll) {
    event.preventDefault();
    window.scrollBy({ top: delta, left: 0, behavior: "instant" });
    return;
  }

  // At an end: absorb wheel until the pause elapses, then hand off to the page.
  event.preventDefault();
  const dir = towardTop ? -1 : 1;
  const now = performance.now();
  if (edgeLock.dir !== dir) {
    edgeLock = { dir, since: now };
    return;
  }
  if (now - edgeLock.since < EDGE_WAIT_MS) return;
  window.scrollBy({ top: delta, left: 0, behavior: "instant" });
}

messagesEl.addEventListener(
  "wheel",
  (event) => relayWheelToPage(event, messagesEl),
  { passive: false }
);

function setResultPanel(mode) {
  resultEmpty.hidden = mode !== "empty";
  resultLoading.hidden = mode !== "loading";
  resultBody.hidden = mode !== "result";
  jsonDetails.hidden = mode !== "result";
  if (mode === "loading") {
    stepPill.textContent = "loading quote";
  }
}

function renderResult(result) {
  if (!result) {
    lastResult = null;
    setResultPanel("empty");
    return;
  }
  lastResult = result;
  setResultPanel("result");

  const summary = result.customer_summary || {};
  const quote = result.quote;
  const revision = Number(result.quote_revision || 1);
  const highlights = (summary.highlights || [])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");
  const nextSteps = (summary.next_steps || [])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");

  resultBody.innerHTML = `
    <div class="summary-card">
      <h3>${escapeHtml(summary.headline || "Your latest pass")}</h3>
      ${quote ? `<p class="revision-label">Pass ${String(revision).padStart(2, "0")}</p>` : ""}
      <p class="summary-body">${escapeHtml(summary.body || result.customer_reply || "")}</p>
      ${highlights ? `<ul class="summary-list">${highlights}</ul>` : ""}
      ${
        quote
          ? `<div class="metric quote"><span class="label">Estimated monthly</span><span class="value">$${Number(quote.monthly).toFixed(2)}</span></div>
             <div class="metric"><span class="label">Estimated annual</span><span class="value">$${Number(quote.annual).toFixed(2)}</span></div>`
          : ""
      }
      ${nextSteps ? `<p class="summary-label">Next steps</p><ul class="summary-list">${nextSteps}</ul>` : ""}
      ${summary.disclaimer ? `<p class="summary-disclaimer">${escapeHtml(summary.disclaimer)}</p>` : ""}
    </div>
  `;

  sessionJson.textContent = JSON.stringify(
    {
      session_json: result.session_json,
      status: result.status,
      intent: result.intent,
      product_id: result.product_id,
      quote: result.quote,
      handoff: result.handoff,
      llm_calls: result.llm_calls,
      total_tokens: result.total_tokens,
      quote_revision: result.quote_revision,
      conversation_context: result.conversation_context,
    },
    null,
    2
  );
}

function restoreResultPanel() {
  if (lastResult) renderResult(lastResult);
  else setResultPanel("empty");
}

async function startChat() {
  const res = await fetch("/api/chat/start", { method: "POST" });
  if (!res.ok) throw new Error("Could not start chat");
  const data = await res.json();
  sessionId = data.session_id;
  messagesEl.innerHTML = "";
  addBubble("assistant", data.reply);
  stepPill.textContent = data.step.replaceAll("_", " ");
  workspace.hidden = false;
  steps.hidden = true;
  newBtn.hidden = false;
  startBtn.hidden = true;
  renderResult(null);
  input.focus();
  workspace.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function sendMessage(message) {
  const res = await fetch("/api/chat/message", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Message failed");
  }
  return res.json();
}

async function runQuote() {
  const res = await fetch("/api/chat/quote", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Quote failed");
  }
  return res.json();
}

startBtn.addEventListener("click", async () => {
  try {
    startBtn.disabled = true;
    await startChat();
  } catch (err) {
    alert(err.message);
  } finally {
    startBtn.disabled = false;
  }
});

newBtn.addEventListener("click", async () => {
  await startChat();
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!sessionId) return;
  const message = input.value.trim();
  if (!message) return;
  input.value = "";
  addBubble("user", message);
  try {
    input.disabled = true;
    showTyping();
    const data = await sendMessage(message);
    hideTyping();
    addBubble("assistant", data.reply);
    stepPill.textContent = data.step.replaceAll("_", " ");

    // Loading screen only when the agent actually queued a quote pass.
    if (!data.pipeline_pending) return;

    setResultPanel("loading");
    showTyping();
    try {
      const quoteData = await runQuote();
      hideTyping();
      addBubble("assistant", quoteData.reply);
      stepPill.textContent = quoteData.step.replaceAll("_", " ");
      if (quoteData.result) renderResult(quoteData.result);
      else restoreResultPanel();
    } catch (quoteErr) {
      hideTyping();
      restoreResultPanel();
      addBubble("assistant", `Sorry — could not finish the quote. ${quoteErr.message}`);
    }
  } catch (err) {
    hideTyping();
    addBubble("assistant", `Sorry — ${err.message}`);
  } finally {
    hideTyping();
    input.disabled = false;
    input.focus();
  }
});
