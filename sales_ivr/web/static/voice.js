/* Browser voice loop: speech recognition in, speech synthesis out.
   The page owns the conversation; this module only hears and speaks. */

(function () {
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  function support() {
    if (!window.isSecureContext) {
      return {
        ok: false,
        reason:
          "Voice needs a secure page. Open this site at localhost, or use HTTPS. You can still type.",
      };
    }
    if (!Recognition) {
      return {
        ok: false,
        reason:
          "This browser can't hear speech. Use Chrome or Edge, or type your message instead.",
      };
    }
    if (!window.speechSynthesis || typeof SpeechSynthesisUtterance !== "function") {
      return {
        ok: false,
        reason: "This browser can listen, but it can't speak. You can still type.",
      };
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      return {
        ok: false,
        reason: "This browser can't use the microphone. You can still type.",
      };
    }
    return { ok: true, reason: "" };
  }

  function toSpeakable(text) {
    return String(text || "")
      .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
      .replace(/\*\*(.*?)\*\*/g, "$1")
      .replace(/[*_`#>]/g, "")
      .replace(/^\s*[-•]\s+/gm, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function chunkSpeech(text, maxLen) {
    const sentences = text.match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [text];
    const chunks = [];
    let buffer = "";
    sentences.forEach((sentence) => {
      const part = sentence.trim();
      if (!part) return;
      const next = buffer ? `${buffer} ${part}` : part;
      if (next.length > maxLen && buffer) {
        chunks.push(buffer);
        buffer = part;
      } else {
        buffer = next;
      }
    });
    if (buffer) chunks.push(buffer);
    return chunks;
  }

  function normalize(text) {
    return String(text || "")
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function voicesReady() {
    if (!window.speechSynthesis) return Promise.resolve();
    if (window.speechSynthesis.getVoices().length) return Promise.resolve();
    return new Promise((resolve) => {
      const timer = window.setTimeout(resolve, 400);
      window.speechSynthesis.addEventListener(
        "voiceschanged",
        () => {
          window.clearTimeout(timer);
          resolve();
        },
        { once: true }
      );
    });
  }

  function pickVoice() {
    const voices = window.speechSynthesis.getVoices() || [];
    const ranked = voices
      .map((voice) => {
        const name = voice.name || "";
        const lang = (voice.lang || "").toLowerCase();
        let score = 0;
        if (lang.startsWith("en-us")) score += 40;
        else if (lang.startsWith("en")) score += 15;
        if (/natural/i.test(name)) score += 30;
        if (/aria|jenny|guy|sonia|davis/i.test(name)) score += 20;
        if (/google us english/i.test(name)) score += 18;
        if (/samantha|zira/i.test(name)) score += 8;
        return { voice, score };
      })
      .sort((a, b) => b.score - a.score);
    return ranked.length && ranked[0].score > 0 ? ranked[0].voice : null;
  }

  function create(handlers) {
    const onStatus = handlers.onStatus || function () {};
    const onInterim = handlers.onInterim || function () {};
    let alive = true;
    let speaking = false;
    let interruptSpeak = null;
    let listenSession = null;
    let lastSpoken = "";

    function stopListening() {
      if (!listenSession) return;
      const session = listenSession;
      listenSession = null;
      session.cancel();
    }

    function speak(text) {
      const spoken = toSpeakable(text);
      lastSpoken = spoken;
      if (!alive || !spoken) return Promise.resolve();
      stopListening();
      if (interruptSpeak) interruptSpeak();

      return voicesReady().then(
        () =>
          new Promise((resolve) => {
        const chunks = chunkSpeech(spoken, 160);
        let index = 0;
        let settled = false;
        speaking = true;
        onStatus("speaking");

        const finish = () => {
          if (settled) return;
          settled = true;
          speaking = false;
          interruptSpeak = null;
          resolve();
        };

        interruptSpeak = () => {
          window.speechSynthesis.cancel();
          finish();
        };

        const sayNext = () => {
          if (!alive || settled) {
            finish();
            return;
          }
          if (index >= chunks.length) {
            finish();
            return;
          }
          const chunk = chunks[index];
          index += 1;
          const utterance = new SpeechSynthesisUtterance(chunk);
          const voice = pickVoice();
          if (voice) utterance.voice = voice;
          utterance.lang = "en-US";
          utterance.rate = 0.98;
          utterance.pitch = 1;
          let ended = false;
          const done = () => {
            if (ended || settled) return;
            ended = true;
            window.clearTimeout(watchdog);
            sayNext();
          };
          const watchdog = window.setTimeout(
            done,
            Math.min(14000, 1400 + chunk.length * 70)
          );
          utterance.onend = done;
          utterance.onerror = done;
          window.speechSynthesis.speak(utterance);
        };

        window.speechSynthesis.cancel();
        window.setTimeout(sayNext, 60);
      })
      );
    }

    function listen() {
      if (!alive) return Promise.resolve("");
      if (listenSession) listenSession.cancel();

      return new Promise((resolve, reject) => {
        let settled = false;
        let rec = null;
        let generation = 0;
        let restarts = 0;
        let finals = "";
        let interim = "";
        let silenceTimer = null;
        let emptyTimer = null;
        const startedAt = performance.now();

        const cleanup = () => {
          window.clearTimeout(silenceTimer);
          window.clearTimeout(emptyTimer);
          generation += 1;
          if (rec) {
            rec.onresult = null;
            rec.onerror = null;
            rec.onend = null;
            try {
              rec.abort();
            } catch (err) {
              /* already stopped */
            }
          }
          rec = null;
        };

        const finish = (text) => {
          if (settled) return;
          settled = true;
          listenSession = null;
          cleanup();
          onInterim("");
          resolve(String(text || "").replace(/\s+/g, " ").trim());
        };

        const fail = (code) => {
          if (settled) return;
          settled = true;
          listenSession = null;
          cleanup();
          const error = new Error(code || "speech");
          error.code = code || "speech";
          reject(error);
        };

        listenSession = {
          cancel: () => finish(""),
          commit: () => finish(`${finals} ${interim}`),
        };

        const armSilence = () => {
          window.clearTimeout(silenceTimer);
          silenceTimer = window.setTimeout(() => {
            finish(`${finals} ${interim}`);
          }, 2000);
        };

        const armEmpty = () => {
          window.clearTimeout(emptyTimer);
          emptyTimer = window.setTimeout(() => finish(""), 7000);
        };

        const startRecognizer = () => {
          if (settled || !alive) return;
          const gen = generation + 1;
          generation = gen;
          rec = new Recognition();
          rec.lang = "en-US";
          rec.continuous = true;
          rec.interimResults = true;
          rec.maxAlternatives = 1;
          rec.onresult = (event) => {
            if (gen !== generation || settled) return;
            window.clearTimeout(emptyTimer);
            let nextInterim = "";
            for (let i = event.resultIndex; i < event.results.length; i += 1) {
              const piece = event.results[i][0].transcript || "";
              if (event.results[i].isFinal) finals = `${finals} ${piece}`.trim();
              else nextInterim += piece;
            }
            interim = nextInterim.trim();
            onInterim(`${finals} ${interim}`.trim());
            if (performance.now() - startedAt > 28000) {
              finish(`${finals} ${interim}`);
              return;
            }
            armSilence();
          };
          rec.onerror = (event) => {
            if (gen !== generation || settled) return;
            const code = event.error || "speech";
            if (code === "no-speech" || code === "aborted") return;
            fail(code);
          };
          rec.onend = () => {
            if (gen !== generation || settled || !alive) return;
            const heard = `${finals} ${interim}`.trim();
            // Chrome often ends a phrase on a short pause, which cuts off phone
            // numbers. Keep the mic open and let the 2s silence timer decide.
            if (heard && !silenceTimer) armSilence();
            restarts += 1;
            if (!heard && restarts > 6) return;
            window.setTimeout(() => {
              if (gen === generation && !settled) startRecognizer();
            }, 40);
          };
          try {
            rec.start();
          } catch (err) {
            fail("start");
          }
        };

        onStatus("listening");
        armEmpty();
        startRecognizer();
      });
    }

    function stop() {
      alive = false;
      if (interruptSpeak) interruptSpeak();
      else window.speechSynthesis.cancel();
      stopListening();
    }

    function isEcho(heard) {
      const said = normalize(heard);
      const prior = normalize(lastSpoken);
      if (!said || !prior || said.length < 12) return false;
      return prior.includes(said) || said.includes(prior);
    }

    return {
      speak,
      listen,
      stop,
      isEcho,
      interrupt() {
        if (interruptSpeak) interruptSpeak();
      },
      commit() {
        if (listenSession) listenSession.commit();
      },
    };
  }

  if (window.speechSynthesis) window.speechSynthesis.getVoices();

  window.FirstpassVoice = { support, create, toSpeakable };
})();
