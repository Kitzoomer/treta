const test = require('node:test');
const assert = require('node:assert/strict');
const { preserveOnFailure, buildDegradedBannerModel } = require('./degraded_mode.js');

test('preserveOnFailure keeps last-known-good data when fetch fails', () => {
  const current = [{ id: 'seed' }];
  const next = [];
  const result = preserveOnFailure(current, next, true);
  assert.equal(result, current);
  assert.deepEqual(result, [{ id: 'seed' }]);
});

test('buildDegradedBannerModel flags integrity endpoint 503', () => {
  const model = buildDegradedBannerModel({
    diagnostics: {
      backendConnected: true,
      integrity: { lastStatusCode: 503 },
      sliceHealth: {
        system: { stale: false, lastSuccessAt: Date.now() },
      },
    },
    refreshMs: 3000,
    now: Date.now(),
  });

  assert.equal(model.show, true);
  assert.match(model.message, /HTTP 503/);
});
