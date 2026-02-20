(function initTretaVoiceModule(globalScope) {
  const RecognitionCtor = globalScope.SpeechRecognition || globalScope.webkitSpeechRecognition;
  const WAKE_WORD = "treta";
  const COMMAND_WAIT_MS = 5000;

  const state = {
    recognition: null,
    supported: Boolean(RecognitionCtor),
    enabled: false,
    shouldRestart: false,
    onTranscript: null,
    onError: null,
    waitingForCommand: false,
    waitingTimer: null,
  };

  function speak(text) {
    if (!globalScope.speechSynthesis || !text) return;
    globalScope.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "es-ES";
    utterance.rate = 1;
    globalScope.speechSynthesis.speak(utterance);
  }

  function stopTts() {
    if (globalScope.speechSynthesis) globalScope.speechSynthesis.cancel();
  }

  function clearWaitingState() {
    state.waitingForCommand = false;
    if (state.waitingTimer) {
      globalScope.clearTimeout(state.waitingTimer);
      state.waitingTimer = null;
    }
  }

  function startWaitingForCommand() {
    clearWaitingState();
    state.waitingForCommand = true;
    state.waitingTimer = globalScope.setTimeout(() => {
      clearWaitingState();
    }, COMMAND_WAIT_MS);
  }

  function emitCommand(command) {
    if (!state.onTranscript || !command) return;
    console.log("[VOICE] command:", command);
    state.onTranscript({ text: `${WAKE_WORD} ${command}`, isFinal: true });
    clearWaitingState();
  }

  function processFinalTranscript(transcript) {
    if (!transcript) return;

    const wakeIndex = transcript.indexOf(WAKE_WORD);
    if (wakeIndex >= 0) {
      const wakeSegments = transcript.split(WAKE_WORD);
      const command = wakeSegments
        .slice(1)
        .join(WAKE_WORD)
        .replace(/^\s*[,.:-]?\s*/, "")
        .trim();

      if (command) {
        emitCommand(command);
      } else {
        startWaitingForCommand();
      }
      return;
    }

    if (state.waitingForCommand) {
      emitCommand(transcript);
    }
  }

  function buildRecognition() {
    if (!state.supported) return null;
    const recognition = new RecognitionCtor();
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.lang = "es-ES";

    recognition.onresult = (event) => {
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        if (!result?.isFinal) continue;
        if (!result?.[0]?.transcript) continue;
        const transcript = result[0].transcript.trim().toLowerCase();
        if (!transcript) continue;
        console.log("[VOICE] heard:", transcript);
        processFinalTranscript(transcript);
      }
    };

    recognition.onerror = (event) => {
      if (state.onError) state.onError(event.error || "unknown");
      if (!state.enabled || !state.shouldRestart) return;
      globalScope.setTimeout(() => {
        try {
          recognition.start();
        } catch (_error) {
          if (state.onError) state.onError("restart_failed");
        }
      }, 250);
    };

    recognition.onend = () => {
      if (!state.enabled || !state.shouldRestart) return;
      globalScope.setTimeout(() => {
        try {
          recognition.start();
        } catch (_error) {
          if (state.onError) state.onError("restart_failed");
        }
      }, 250);
    };

    return recognition;
  }

  function initVoiceMode({ onTranscript, onError } = {}) {
    state.onTranscript = typeof onTranscript === "function" ? onTranscript : null;
    state.onError = typeof onError === "function" ? onError : null;

    if (!state.supported) return { supported: false };
    if (!state.recognition) state.recognition = buildRecognition();
    return { supported: true };
  }

  function startVoice() {
    if (!state.supported || !state.recognition) return false;
    state.enabled = true;
    state.shouldRestart = true;
    try {
      state.recognition.start();
      return true;
    } catch (_error) {
      if (state.onError) state.onError("start_failed");
      return false;
    }
  }

  function stopVoice() {
    if (!state.supported || !state.recognition) return;
    state.enabled = false;
    state.shouldRestart = false;
    clearWaitingState();
    state.recognition.stop();
    stopTts();
  }

  globalScope.TretaVoiceMode = {
    initVoiceMode,
    startVoice,
    stopVoice,
    speak,
    stopTts,
    isSupported: () => state.supported,
  };
})(window);
