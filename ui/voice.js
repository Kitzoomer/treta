(function initTretaVoiceModule(globalScope) {
  const RecognitionCtor = globalScope.SpeechRecognition || globalScope.webkitSpeechRecognition;

  const state = {
    recognition: null,
    supported: Boolean(RecognitionCtor),
    enabled: false,
    shouldRestart: false,
    onTranscript: null,
    onError: null,
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

  function buildRecognition() {
    if (!state.supported) return null;
    const recognition = new RecognitionCtor();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "es-ES";

    recognition.onresult = (event) => {
      if (!state.onTranscript) return;
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        const text = String(result[0]?.transcript || "").trim();
        if (!text) continue;
        state.onTranscript({ text, isFinal: Boolean(result.isFinal) });
      }
    };

    recognition.onerror = (event) => {
      if (state.onError) state.onError(event.error || "unknown");
    };

    recognition.onend = () => {
      if (!state.enabled || !state.shouldRestart) return;
      try {
        recognition.start();
      } catch (_error) {
        if (state.onError) state.onError("restart_failed");
      }
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
