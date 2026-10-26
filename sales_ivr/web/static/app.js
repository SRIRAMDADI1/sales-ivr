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
const voiceBtn = document.getElementById("voiceBtn");
const voiceToggle = document.getElementById("voiceToggle");
const voiceStage = document.getElementById("voiceStage");
const voiceStatus = document.getElementById("voiceStatus");
const voiceCaption = document.getElementById("voiceCaption");
const voiceOrb = document.getElementById("voiceOrb");
const voiceEnd = document.getElementById("voiceEnd");
const voiceType = document.getElementById("voiceType");
const chatPanel = document.querySelector(".chat-panel");

let sessionId = null;
let sessionChannel = "web_chat";
let lastResult = null;
let activeCall = null;
let callActive = false;
let voiceState = "idle";
let dropRest = false;
let voiceDone = Promise.resolve();
const STATUS_LABEL = {
  speaking: "I'm talking. Mic is off",
  listening: "Your turn",
  thinking: "One moment. Mic is off",
  idle: "Ready",
};
const ORB_LABEL = {
  speaking: "Assistant is speaking. Microphone is off.",
  listening: "Your turn. Microphone is on.",
  thinking: "Microphone is off.",
  idle: "Talk, or tap to interrupt",
};

const STEP_LABEL = {
  ready: "Ready",
  agent_online: "Here to help",
  preparing_quote: "Pricing your quote",
  quote_ready: "Quote ready",
  loading_quote: "Working on your quote",
};

function humanize(text) {
  return String(text)
    .replace(/\s*[—–]\s*/g, ", ")
    .replace(/,\s*,/g, ", ")
    .replace(/[ \t]{2,}/g, " ");
}

function showStep(step) {
  const key = String(step || "").trim().replaceAll(" ", "_");
  stepPill.textContent = STEP_LABEL[key] || humanize(String(step || "").replaceAll("_", " "));
}

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
  div.textContent = humanize(content).replace(/\*\*(.*?)\*\*/g, "$1");
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
    showStep("loading_quote");
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
    .map((item) => `<li>${escapeHtml(humanize(item))}</li>`)
    .join("");
  const nextSteps = (summary.next_steps || [])
    .map((item) => `<li>${escapeHtml(humanize(item))}</li>`)
    .join("");

  resultBody.innerHTML = `
    <div class="summary-card">
      <h3>${escapeHtml(humanize(summary.headline || "Your quote"))}</h3>
      ${quote ? `<p class="revision-label">Quote ${revision}</p>` : ""}
      <p class="summary-body">${escapeHtml(humanize(summary.body || result.customer_reply || ""))}</p>
      ${highlights ? `<ul class="summary-list">${highlights}</ul>` : ""}
      ${
        quote
          ? quote.premium_basis === "term"
            ? `<div class="metric quote"><span class="label">One-time price</span><span class="value">$${Number(quote.monthly).toFixed(2)}</span></div>
               <p class="summary-disclaimer">This covers the whole term, not a monthly bill.</p>`
            : `<div class="metric quote"><span class="label">Monthly estimate</span><span class="value">$${Number(quote.monthly).toFixed(2)}</span></div>
             <div class="metric"><span class="label">Yearly estimate</span><span class="value">$${Number(quote.annual).toFixed(2)}</span></div>`
          : ""
      }
      ${nextSteps ? `<p class="summary-label">Next steps</p><ul class="summary-list">${nextSteps}</ul>` : ""}
      ${summary.disclaimer ? `<p class="summary-disclaimer">${escapeHtml(humanize(summary.disclaimer))}</p>` : ""}
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

async function startChat(channel) {
  const mode = channel === "voice" ? "voice" : "web_chat";
  const res = await fetch(`/api/chat/start?channel=${mode}`, { method: "POST" });
  if (!res.ok) throw new Error("Could not start chat");
  const data = await res.json();
  sessionId = data.session_id;
  sessionChannel = mode;
  messagesEl.innerHTML = "";
  addBubble("assistant", data.reply);
  showStep(data.step);
  workspace.hidden = false;
  steps.hidden = true;
  newBtn.hidden = false;
  startBtn.hidden = true;
  voiceBtn.hidden = true;
  renderResult(null);
  if (mode !== "voice") input.focus();
  workspace.scrollIntoView({ behavior: "smooth", block: "start" });
  return data.reply;
}

async function sendMessage(message, channel) {
  const res = await fetch("/api/chat/message", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      message,
      channel: channel || "web_chat",
    }),
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

function setVoiceStatus(state, caption) {
  voiceState = state;
  voiceStage.dataset.state = state;
  voiceStatus.textContent = STATUS_LABEL[state] || state;
  voiceOrb.setAttribute("aria-label", ORB_LABEL[state] || ORB_LABEL.idle);
  if (caption !== undefined) voiceCaption.textContent = caption;
}

function showVoiceStage() {
  voiceStage.hidden = false;
  form.hidden = true;
  chatPanel.classList.add("voice-on");
  voiceOrb.focus();
}

function hideVoiceStage() {
  voiceStage.hidden = true;
  form.hidden = false;
  chatPanel.classList.remove("voice-on");
  voiceStage.dataset.state = "idle";
  voiceCaption.textContent = "";
  voiceStatus.textContent = "Ready";
}

function endVoice() {
  callActive = false;
  activeCall?.stop();
}

async function ensureMic() {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
  });
  stream.getTracks().forEach((track) => track.stop());
}

function wait(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function speakIfLive(text) {
  if (!callActive || !activeCall || !text || dropRest) return false;
  setVoiceStatus("speaking", "");
  await activeCall.speak(text);
  return callActive && !dropRest;
}

async function deliverTurn(message, channel) {
  addBubble("user", message);
  input.disabled = true;
  showTyping();
  setVoiceStatus(channel === "voice" ? "thinking" : voiceState, "");
  const data = await sendMessage(message, channel);
  hideTyping();
  addBubble("assistant", data.reply);
  showStep(data.step);
  if (channel === "voice") {
    sessionChannel = "voice";
    const spoke = await speakIfLive(data.reply);
    if (!spoke) return;
  }
  if (!data.pipeline_pending) return;

  setResultPanel("loading");
  const quoteTask = runQuote();
  if (channel === "voice") await speakIfLive("Give me a moment to price that.");
  showTyping();
  try {
    const quoteData = await quoteTask;
    hideTyping();
    addBubble("assistant", quoteData.reply);
    showStep(quoteData.step);
    if (quoteData.result) renderResult(quoteData.result);
    else restoreResultPanel();
    if (channel === "voice") await speakIfLive(quoteData.reply);
  } catch (quoteErr) {
    hideTyping();
    restoreResultPanel();
    const sorry = `Sorry, I couldn't finish the quote. ${quoteErr.message}`;
    addBubble("assistant", sorry);
    if (channel === "voice") await speakIfLive("Sorry, I couldn't finish that quote. Please try again.");
  }
}

async function runVoiceLoop(greeting) {
  if (callActive) return;
  let release = () => {};
  voiceDone = new Promise((resolve) => {
    release = resolve;
  });
  const support = window.FirstpassVoice.support();
  if (!support.ok) {
    addBubble("assistant", support.reason);
    release();
    return;
  }
  callActive = true;
  showVoiceStage();
  setVoiceStatus("thinking", "Allow the microphone if your browser asks.");
  try {
    await ensureMic();
  } catch (err) {
    addBubble(
      "assistant",
      "I can't use the microphone. Allow microphone access for this site, or type your message instead."
    );
    callActive = false;
    hideVoiceStage();
    release();
    return;
  }
  if (!callActive) {
    hideVoiceStage();
    release();
    return;
  }

  activeCall = window.FirstpassVoice.create({
    onStatus: (state) => {
      if (!callActive) return;
      setVoiceStatus(state);
    },
    onInterim: (text) => {
      if (!callActive || voiceState === "speaking") return;
      voiceCaption.textContent = text;
    },
  });

  try {
    if (greeting) await speakIfLive(greeting);
    let quietTurns = 0;
    let networkFails = 0;
    while (callActive) {
      dropRest = false;
      await wait(100);
      if (!callActive) break;
      let heard = "";
      try {
        setVoiceStatus("listening", "");
        heard = await activeCall.listen();
      } catch (err) {
        if (!callActive) break;
        if (err.code === "not-allowed") {
          addBubble(
            "assistant",
            "The microphone is blocked. Allow it for this site, or type instead."
          );
          break;
        }
        if (err.code === "network") {
          networkFails += 1;
          if (networkFails < 3) {
            await wait(500);
            continue;
          }
          addBubble(
            "assistant",
            "I can't reach speech recognition in this browser. Chrome or Edge usually can hear you. You can type instead."
          );
          break;
        }
        networkFails = 0;
        addBubble("assistant", "I lost the microphone for a moment. Starting to listen again.");
        continue;
      }
      if (!callActive) break;
      networkFails = 0;
      if (!heard || activeCall.isEcho(heard)) {
        quietTurns += 1;
        if (quietTurns === 2) {
          await speakIfLive("I'm still here. Tell me what you need whenever you're ready.");
        }
        if (quietTurns >= 8) {
          await speakIfLive("I'll stop listening for now. Tap the microphone when you want to talk again.");
          break;
        }
        continue;
      }
      quietTurns = 0;
      try {
        await deliverTurn(heard.slice(0, 2000), "voice");
      } catch (err) {
        hideTyping();
        const sorry = `Sorry, ${err.message}`;
        addBubble("assistant", sorry);
        await speakIfLive("Sorry, something went wrong. Please say that again.");
      }
    }
  } finally {
    callActive = false;
    activeCall?.stop();
    activeCall = null;
    hideVoiceStage();
    input.disabled = false;
    input.focus();
    release();
  }
}

startBtn.addEventListener("click", async () => {
  try {
    startBtn.disabled = true;
    endVoice();
    await startChat("web_chat");
  } catch (err) {
    alert(err.message);
  } finally {
    startBtn.disabled = false;
  }
});

voiceBtn.addEventListener("click", async () => {
  try {
    voiceBtn.disabled = true;
    endVoice();
    const greeting = sessionId && sessionChannel === "voice"
      ? null
      : await startChat("voice");
    await runVoiceLoop(greeting);
  } catch (err) {
    alert(err.message);
  } finally {
    voiceBtn.disabled = false;
  }
});

voiceToggle.addEventListener("click", async () => {
  if (!sessionId) return;
  voiceToggle.disabled = true;
  try {
    const greeting = "I'm listening. Tell me what you need, in your own words.";
    await runVoiceLoop(greeting);
  } catch (err) {
    addBubble("assistant", err.message);
  } finally {
    voiceToggle.disabled = false;
  }
});

voiceEnd.addEventListener("click", () => endVoice());
voiceType.addEventListener("click", () => endVoice());

voiceOrb.addEventListener("click", () => {
  if (!activeCall || !callActive) return;
  if (voiceState === "speaking" || voiceState === "thinking") {
    dropRest = true;
    activeCall.interrupt();
    return;
  }
  activeCall.commit();
});

newBtn.addEventListener("click", async () => {
  const restartVoice = callActive || sessionChannel === "voice";
  endVoice();
  await voiceDone;
  const greeting = await startChat(restartVoice ? "voice" : "web_chat");
  if (restartVoice) await runVoiceLoop(greeting);
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!sessionId || callActive) return;
  const message = input.value.trim();
  if (!message) return;
  input.value = "";
  try {
    input.disabled = true;
    await deliverTurn(message, "web_chat");
  } catch (err) {
    hideTyping();
    addBubble("assistant", `Sorry, ${err.message}`);
  } finally {
    hideTyping();
    input.disabled = false;
    if (!callActive) input.focus();
  }
});
