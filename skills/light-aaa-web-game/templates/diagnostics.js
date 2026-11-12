/**
 * Template: wire these methods to real game state; do not ship placeholders.
 * Test hooks must be enabled only by an explicit ?test=1 flag.
 * Seeded scenes control game simulation time, camera, random sources and exposure.
 */
export function installGameDiagnostics(game) {
  if (new URLSearchParams(location.search).get('test') !== '1') return;
  window.__GAME_TEST__ = {
    version: 3,
    get ready() { return game.isPlayable; }, // after required generation/compilation
    get fatal() { return game.fatalError || null; },
    async setScene(id) {
      // Implement the views in budgets.requiredScenes, including the representative
      // workload in benchmarkScene. Fix seed, camera, quality and internal resolution.
      await game.testScenes.select(id);
    },
    metrics() {
      // Cached counters. No synchronous GPU readback here.
      // WebGL totals include all world, shadow, reflection and post passes.
      // Canvas 2D projects can omit drawCalls and submittedTriangles.
      return {
        frame: game.frame,
        sceneId: game.testScenes.current,
        quality: game.quality.name,
        dynamicResolution: game.render.dynamicResolutionEnabled,
        internalWidth: game.render.width,
        internalHeight: game.render.height,
        drawCalls: game.render.frameCounters?.drawCalls,
        submittedTriangles: game.render.frameCounters?.triangles,
        // Counts from actual simulation/render state, keyed as in benchmarkLoad.
        workload: game.testScenes.measureWorkload(),
        estimatedTextureBytes: game.resources.estimatedTextureBytes,
        gpuRenderer: game.render.gpuRenderer
      };
    },
    async audit() {
      // Implement independent checks with observed counts/values, per validation.md.
      // Return {checks:[{id,status:'passed'|'failed'|'unverified',evidence:{...}}]}.
      // Never return unconditional success. A NaN, invalid normal, silent/clipped
      // sound, non-reproducible seed or unreachable goal must fail its relevant check.
      return game.resourceAudit.run();
    },
    snapshot() {
      // Expose the observable state needed to verify a real move and its outcome.
      return game.snapshotForTests();
    },
    feedbackObservations() {
      // Store bounded raw observations from actual accepted inputs and completed
      // main display passes. Collect renders independently of accepted inputs.
      // actions: [{id:'session-1/action-42', acceptedAtMs:performance.now(),
      //          acceptedFrame:lastCompletedFrame, expectedChannels:['result']}]
      // renders: [{actionId:'session-1/action-42', channel:'result',
      //            frame:completedFrame, presentedAtMs:performance.now()}]
      // Two different passes of the same frame count only once. Submission is
      // not proof of on-screen visibility. Capture and inspect final frames too.
      return game.feedbackLog.snapshot();
    },
    resourceCounts() {
      // Count actual live objects after a fully warmed, settled restart.
      // materials/listeners/audioNodes need project-owned registries; renderer
      // info.memory alone cannot count them. Do not estimate missing numbers.
      return game.resourceRegistry.counts();
    }
  };
}
