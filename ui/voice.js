(function initTretaVoiceModule(globalScope) {
  const RecognitionCtor = globalScope.SpeechRecognition || globalScope.webkitSpeechRecognition;

  let onTranscript = null;
  let voiceEnabled = false;

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

  function sendToBackend(text) {
    if (!text || !onTranscript) return;
    onTranscript({ text, isFinal: true });
  }

  if (recognition) {
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.lang = "es-ES";

    recognition.onresult = (event) => {
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        if (!event.results[i].isFinal) continue;

        const transcript = event.results[i][0].transcript.trim();
        if (!transcript) continue;

        console.log("[VOICE]", transcript);
        sendToBackend(transcript);
      }
    };

    recognition.onend = () => {
      if (voiceEnabled) {
        globalScope.setTimeout(() => recognition.start(), 300);
      }
    };

    recognition.onerror = (event) => {
      console.warn("VOICE ERROR:", event.error);
    };
  }

  function initVoiceMode({ onTranscript: transcriptHandler } = {}) {
    onTranscript = typeof transcriptHandler === "function" ? transcriptHandler : null;
    return { supported: Boolean(recognition) };
  }

  function startListening() {
    if (!recognition) return false;
    if (!voiceEnabled) {
      voiceEnabled = true;
      recognition.start();
    }
    return true;
  }

  function stopListening() {
    if (!recognition) return;
    voiceEnabled = false;
    recognition.stop();
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
