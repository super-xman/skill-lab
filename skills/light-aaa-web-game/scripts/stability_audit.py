"""Compute release gates from observations collected by the project test driver."""
import math


def audit_stability(payload, rules, artifact_sha):
    failures, gaps = [], []
    def number(x):
        return type(x) in (int, float) and math.isfinite(x) and x >= 0
    starts = payload.get('coldStarts', [])
    contexts = set()
    if len(starts) < rules['independentColdStarts']:
        gaps.append('Too few independent cold starts')
    for item in starts:
        identity = item.get('contextId')
        if not identity or identity in contexts:
            failures.append('Cold starts must use distinct fresh browser contexts')
        contexts.add(identity)
        if item.get('artifactSha256') != artifact_sha:
            failures.append('Cold-start artifact mismatch')
        for key in ['readyFrame', 'runtimeErrors', 'extraNetworkRequests']:
            if not number(item.get(key)):
                gaps.append('Missing cold-start measurement: ' + key)
        if item.get('readyFrame', 0) < 1 or item.get('runtimeErrors', 0) or item.get('extraNetworkRequests', 0):
            failures.append('Cold-start failure or extra request')
    cycles = payload.get('restarts', [])
    if len(cycles) < rules['restartCycles']:
        gaps.append('Too few restart cycles')
    resources = ['geometries', 'textures', 'materials', 'audioNodes', 'listeners', 'activeEffects']
    baseline = payload.get('warmedBaseline', {})
    if any(not number(baseline.get(key)) for key in resources):
        gaps.append('Missing post-warmup resource baseline')
    for item in cycles:
        if item.get('state') != 'playing':
            failures.append('Restart does not restore playing state')
        before, after = item.get('shotsBefore'), item.get('shotsAfter')
        if not number(before) or not number(after):
            gaps.append('Missing actual shot counts after restart')
        elif after != before + 1:
            failures.append('First shot after restart is missing or duplicated')
        settled = item.get('settledResources', {})
        for key in resources:
            if not number(settled.get(key)) or not number(baseline.get(key)):
                gaps.append('Missing settled resource count: ' + key)
            elif settled[key] > baseline[key] + rules['postWarmupGpuResourceGrowthMax']:
                failures.append('Resource growth after restart: ' + key)
    soak = payload.get('soak', {})
    for key, target in [('wallSeconds', 'soakWallSeconds'), ('combatSeconds', 'sustainedCombatSeconds')]:
        if not number(soak.get(key)) or soak[key] < rules[target]:
            gaps.append('Insufficient observed duration: ' + key)
    if not number(soak.get('renderedFrames')) or soak['renderedFrames'] <= 0:
        gaps.append('Missing continuously rendered frames')
    for key in ['runtimeErrors', 'extraNetworkRequests']:
        if not number(soak.get(key)):
            gaps.append('Missing soak measurement: ' + key)
        elif soak[key] > 0:
            failures.append('Soak failure: ' + key)
    caps = payload.get('frameCapsTested', [])
    if not set(rules['testFrameCaps']).issubset(caps):
        gaps.append('Missing deliberate frame-cadence variants')
    capacity, accepted = payload.get('effectPoolCapacity'), payload.get('poolReuseAcceptedShots')
    if not number(capacity) or capacity < 1 or not number(accepted) or accepted < capacity * rules['effectPoolReuseFactor']:
        gaps.append('Effect-pool reuse coverage is insufficient')
    return {'status': 'failed' if failures else 'unverified' if gaps else 'passed',
            'evidence': {'failures': sorted(set(failures)), 'coverageGaps': sorted(set(gaps)),
                         'observations': payload, 'limits': rules}}
