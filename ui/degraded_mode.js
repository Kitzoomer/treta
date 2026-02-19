(function initTretaDegradedMode(globalScope) {
  function preserveOnFailure(currentValue, nextValue, failed) {
    if (failed) return currentValue;
    if (nextValue === undefined || nextValue === null) return currentValue;
    return nextValue;
  }

  function buildDegradedBannerModel({ diagnostics, refreshMs, now = Date.now() }) {
    const staleThresholdMs = Math.max(Number(refreshMs) || 0, 1) * 2;
    const staleSlices = Object.entries(diagnostics.sliceHealth || {})
      .filter(([, info]) => {
        if (!info?.stale) return false;
        if (!info?.lastSuccessAt) return true;
        return now - info.lastSuccessAt > staleThresholdMs;
      })
      .map(([slice, info]) => ({
        slice,
        lastSuccessAt: info.lastSuccessAt || null,
      }));

    const integrityCode = Number(diagnostics.integrity?.lastStatusCode || 0);
    const integrityUnhealthy = Number.isFinite(integrityCode) && integrityCode > 0 && integrityCode !== 200;

    const reasons = [];
    if (!diagnostics.backendConnected) reasons.push("backend disconnected");
    if (integrityUnhealthy) reasons.push(`integrity check HTTP ${integrityCode}`);
    if (staleSlices.length) reasons.push(`stale slices: ${staleSlices.map((item) => item.slice).join(", ")}`);

    const show = reasons.length > 0;
    return {
      show,
      reasons,
      staleSlices,
      message: show ? `Degraded mode active: ${reasons.join(" · ")}.` : "",
    };
  }

  const api = {
    preserveOnFailure,
    buildDegradedBannerModel,
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
  globalScope.TretaDegradedMode = api;
})(typeof window !== 'undefined' ? window : globalThis);
