/**
 * Template: wire these methods to real game state; do not ship placeholders.
 * Test hooks must be enabled only by an explicit ?test=1 flag.
 * Seeded scenes control game simulation time, camera, random sources and exposure.
 */
export function installGameDiagnostics(game) {
  const query = new URLSearchParams(location.search);
  if (query.get('test') !== '1') return;
  let requestedScene = query.get('scene');
  let sceneError = null;
  const hooks = {
    version: 4,
    handlesSceneQuery: true,
    get ready() { return game.isPlayable && requestedScene === null; },
    get fatal() { return game.fatalError || sceneError || null; },
    async setScene(id) {
      // select() resolves only after the registered fixture is ready for real input.
      // Restore the starting state, clear old effects/input, and reject unknown IDs.
      await game.testScenes.select(id);
      if (game.testScenes.current !== id) throw new Error('Scene did not load: ' + id);
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
    // Optional for Web Audio recording: expose the actual mix node AFTER the
    // master volume/mute chain, already connected to the speaker destination.
    // audioOutput() { return game.audio.masterOutput; },
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
  window.__GAME_TEST__ = hooks;
  if (requestedScene !== null) {
    function enterWhenPlayable() {
      if (game.fatalError) return;
      if (!game.isPlayable) {
        requestAnimationFrame(enterWhenPlayable);
        return;
      }
      hooks.setScene(requestedScene)
        .catch(error => { sceneError = String(error); })
        .finally(() => { requestedScene = null; });
    }
    enterWhenPlayable();
  }
}
