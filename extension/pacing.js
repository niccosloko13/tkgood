/* Shared conservative timing. Never changes document visibility or browser identity. */
(() => {
  const settings=Object.freeze({pollMs:1000,settleMs:2000,cooldownMs:2500,readTimeoutMs:25000,
    searchTimeoutMs:25000,transportAttempts:3,stableSamples:2,stabilityAttempts:8,
    queryStabilityMaxSamples:26,searchRouteGraceMs:3000});
  const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
  globalThis.ProductHunterPacing=Object.freeze({settings,sleep});
})();
