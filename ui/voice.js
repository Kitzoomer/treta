(function initTretaVoiceModule(globalScope) {
  const RecognitionCtor = globalScope.SpeechRecognition || globalScope.webkitSpeechRecognition;

  const state = {
    recognition: null,
    enabled: false,
    supported: Boolean(RecognitionCtor),
    shouldRestart: false,
    onCommand: null,
    onError: null,
  };

  const DIRECT_COMMAND_PREFIXES = ["lanza", "escanea", "estado", "plan", "estrategia"];

  function parseWakeCommand(rawTranscript) {
    const transcript = String(rawTranscript || "").trim();
    if (!transcript) return "";

    const lower = transcript.toLowerCase();
    const wakeIndex = lower.indexOf("treta");
    if (wakeIndex < 0) return "";

    const command = transcript.slice(wakeIndex + "treta".length).trim();
    if (!command) return "";

    const normalized = command.toLowerCase();
    const isSpecial = DIRECT_COMMAND_PREFIXES.some((prefix) => normalized.startsWith(prefix));
    if (isSpecial) return command;
    return command;
  }

  function speak(text) {
    if (!globalScope.speechSynthesis || !text) return;

    globalScope.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "es-ES";
    utterance.rate = 1;

    const voices = globalScope.speechSynthesis.getVoices() || [];
    const femaleVoice = voices.find((voice) => {
      const name = (voice.name || "").toLowerCase();
      return voice.lang?.toLowerCase().startsWith("es") && /(female|mujer|woman|zira|monica|paulina|helena|sofia)/.test(name);
    });
    const fallbackSpanishVoice = voices.find((voice) => voice.lang?.toLowerCase().startsWith("es"));

    utterance.voice = femaleVoice || fallbackSpanishVoice || null;
    globalScope.speechSynthesis.speak(utterance);
  }

  function handleRecognitionResult(event) {
    if (!state.onCommand) return;
    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      const result = event.results[i];
      if (!result.isFinal) continue;
      const transcript = result[0]?.transcript || "";
      const command = parseWakeCommand(transcript);
      if (!command) continue;
      state.onCommand(command, transcript);
    }
  }

  function buildRecognition() {
    if (!state.supported) return null;

    const recognition = new RecognitionCtor();
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.lang = "es-ES";

    recognition.onresult = handleRecognitionResult;

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

  function initVoiceMode({ onCommand, onError } = {}) {
    state.onCommand = typeof onCommand === "function" ? onCommand : null;
    state.onError = typeof onError === "function" ? onError : null;

    if (!state.supported) return { supported: false };

    if (!state.recognition) {
      state.recognition = buildRecognition();
    }

    return { supported: true };
  }

  function startListening() {
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

  function stopListening() {
    if (!state.supported || !state.recognition) return;
    state.enabled = false;
    state.shouldRestart = false;
    state.recognition.stop();
    if (globalScope.speechSynthesis) {
      globalScope.speechSynthesis.cancel();
    }
  }

  globalScope.TretaVoiceMode = {
    initVoiceMode,
    startListening,
    stopListening,
    speak,
    isSupported: () => state.supported,
  };
})(window);
