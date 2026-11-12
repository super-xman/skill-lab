/**
 * Template: wire these methods to real game state; do not ship placeholders.
 * Test hooks must be enabled only by an explicit ?test=1 flag.
 * Seeded scenes control game simulation time, camera, random sources and exposure.
 */
export function installGameDiagnostics(game) {
  if (new URLSearchParams(location.search).get('test') !== '1') return;
  window.__GAME_TEST__ = {
    version: 4,
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
      // DOM, SVG and Canvas 2D omit WebGL counters. On-demand views only
      // need sceneId and workload here; the scenario measures input-to-output latency.
      if (game.renderMode === 'on-demand' && game.renderBackend !== 'webgl') {
        return {sceneId: game.testScenes.current, workload: game.testScenes.measureWorkload()};
      }
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
      // Correlate real inputs with independent reads of the player-facing output.
      // actions: [{id:'turn-1', condition:'first_choice', acceptedAtMs:100}]
      // observations: [{actionId:'turn-1', channel:'result', source:'visual',
      //                 atMs:116, value:'first'}]
      // For persistent output, read it again after the declared hold time.
      // For audio, sample the playback path; for DOM, read displayed content.
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
