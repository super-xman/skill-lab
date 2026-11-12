/**
 * Template: wire these methods to real game state; do not ship placeholders.
 * Test hooks must be enabled only by an explicit ?test=1 flag.
 * Seeded scenes control game simulation time, camera, random sources and exposure.
 */
export function installGameDiagnostics(game) {
  if (new URLSearchParams(location.search).get('test') !== '1') return;
  window.__GAME_TEST__ = {
    version: 2,
    get ready() { return game.isPlayable; }, // after required generation/compilation
    get fatal() { return game.fatalError || null; },
    async setScene(id) {
      // Must implement overview/materials/combat/interior. Reset deterministic
      // fixtures, select camera, fix quality/dynamic resolution and settle effects.
      // combat must contain the agreed representative enemy/FX load.
      await game.testScenes.select(id);
    },
    metrics() {
      // Cached counters. No synchronous GPU readback here.
      // Sum all world, shadow, reflection and post passes for one complete frame.
      return {
        frame: game.frame,
        sceneId: game.testScenes.current,
        quality: game.quality.name,
        dynamicResolution: game.render.dynamicResolutionEnabled,
        internalWidth: game.render.width,
        internalHeight: game.render.height,
        drawCalls: game.render.frameCounters.drawCalls,
        submittedTriangles: game.render.frameCounters.triangles,
        enemiesAlive: game.enemies.aliveCount,
        effectsActive: game.fx.activeCount,
        estimatedTextureBytes: game.resources.estimatedTextureBytes,
        gpuRenderer: game.render.gpuRenderer
      };
    },
    async audit() {
      // Implement independent checks with observed counts/values, per validation.md.
      // Return {checks:[{id,status:'passed'|'failed'|'unverified',evidence:{...}}]}.
      // Never return unconditional success. A NaN, invalid normal, silent/clipped
      // sound, non-reproducible seed or missing path must fail its relevant check.
      return game.resourceAudit.run();
    },
    snapshot() {
      // Read-only, serializable state for tests: player position/health,
      // ammo/hit events, enemy state, objectives, game state, audio state.
      return game.snapshotForTests();
    },
    feedbackObservations() {
      // Store bounded raw observations from actual accepted inputs and completed
      // MAIN-CAMERA render passes; never derive renders by copying shots.
      // shots: [{id:'session-1/shot-42', acceptedAtMs:performance.now(),
      //          acceptedFrame:lastCompletedFrame, expectedFx:['muzzle','tracer']}]
      // renders: [{shotId:'session-1/shot-42', channel:'tracer',
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
