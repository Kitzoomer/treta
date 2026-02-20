(function initTretaVoiceModule(globalScope) {
  const RecognitionCtor = globalScope.SpeechRecognition || globalScope.webkitSpeechRecognition;
  const WAKE_WORD = "treta";
  const COMMAND_WAIT_MS = 5000;

  let onTranscript = null;
  let onError = null;

  let voiceEnabled = false;
  let waitingForCommand = false;
  let waitingTimer = null;
  let isRecognitionStarted = false;
  let restartTimer = null;

  const recognition = RecognitionCtor ? new RecognitionCtor() : null;

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
    waitingForCommand = false;
    if (waitingTimer) {
      globalScope.clearTimeout(waitingTimer);
      waitingTimer = null;
    }
  }

  function sendToBackend(text) {
    if (!text || !onTranscript) return;
    onTranscript({ text: `${WAKE_WORD} ${text}`.trim(), isFinal: true });
  }

  function clearRestartTimer() {
    if (restartTimer) {
      globalScope.clearTimeout(restartTimer);
      restartTimer = null;
    }
  }

  function scheduleRestart(reasonLabel) {
    if (!recognition || !voiceEnabled || isRecognitionStarted || restartTimer) return;
    restartTimer = globalScope.setTimeout(() => {
      restartTimer = null;
      if (!voiceEnabled || isRecognitionStarted) return;
      try {
        recognition.start();
      } catch (error) {
        console.warn(reasonLabel, error);
      }
    }, 300);
  }

  if (recognition) {
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.lang = "es-ES";

    recognition.onstart = () => {
      isRecognitionStarted = true;
    };

    recognition.onresult = (event) => {
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        if (!event.results[i].isFinal) continue;

        const transcript = event.results[i][0].transcript.trim().toLowerCase();
        if (!transcript) continue;

        console.log("[VOICE] heard:", transcript);

        if (transcript.includes(WAKE_WORD)) {
          const after = transcript.split(WAKE_WORD)[1]?.trim();

          if (after) {
            sendToBackend(after);
            clearWaitingState();
          } else {
            clearWaitingState();
            waitingForCommand = true;
            waitingTimer = globalScope.setTimeout(() => {
              waitingForCommand = false;
              waitingTimer = null;
            }, COMMAND_WAIT_MS);
          }
        } else if (waitingForCommand) {
          sendToBackend(transcript);
          clearWaitingState();
        }
      }
    };

    recognition.onend = () => {
      isRecognitionStarted = false;
      if (!voiceEnabled) return;
      scheduleRestart("[VOICE] restart blocked:");
    };

    recognition.onerror = (event) => {
      isRecognitionStarted = false;
      console.warn("[VOICE] error:", event?.error);
      if (onError) onError(event?.error || "unknown");
      if (!voiceEnabled) return;
      scheduleRestart("[VOICE] restart after error blocked:");
    };
  }

  function initVoiceMode({ onTranscript: transcriptHandler, onError: errorHandler } = {}) {
    onTranscript = typeof transcriptHandler === "function" ? transcriptHandler : null;
    onError = typeof errorHandler === "function" ? errorHandler : null;
    return { supported: Boolean(recognition) };
  }

  function startListening() {
    if (!recognition || voiceEnabled) return false;
    voiceEnabled = true;
    clearRestartTimer();
    try {
      recognition.start();
    } catch (error) {
      console.warn("[VOICE] initial start failed:", error);
    }
    return true;
  }

  function stopListening() {
    if (!recognition) return;
    voiceEnabled = false;
    clearWaitingState();
    clearRestartTimer();
    try {
      recognition.stop();
    } catch (error) {
      console.warn("[VOICE] stop failed:", error);
    }
  }

  globalScope.TretaVoiceMode = {
    initVoiceMode,
    startListening,
    stopListening,
    startVoice: startListening,
    stopVoice: stopListening,
    speak,
    stopTts,
    isSupported: () => Boolean(recognition),
  };
})(window);
