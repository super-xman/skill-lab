"""Validate raw action/render observations; these counters do not prove visible pixels."""
import math


def audit_feedback(payload, rules):
    """Observations must come from real input and the completed main render pass.

    shots: [{id, acceptedAtMs, acceptedFrame, expectedFx:[...]}]
    renders: [{shotId, channel, frame, presentedAtMs}]
    Rejected inputs (cooldown/reload/no ammo) are not accepted shots.
    """
    shots, renders = payload.get('shots', []), payload.get('renders', [])
    defects = []
    if not isinstance(shots, list) or not isinstance(renders, list):
        return {'status': 'failed', 'evidence': {'defects': ['Invalid raw observation arrays']}}
    seen = set()
    observed = {}
    def finite(value):
        return type(value) in (float, int) and math.isfinite(value)
    for render in renders:
        if (not isinstance(render, dict) or not isinstance(render.get('shotId'), str)
                or not isinstance(render.get('channel'), str)
                or type(render.get('frame')) is not int or render['frame'] < 0
                or not finite(render.get('presentedAtMs'))):
            defects.append('Malformed render observation')
            continue
        observed.setdefault((render['shotId'], render['channel']), []).append(render)
    missing, delays, required_pairs = [], [], 0
    for shot in shots:
        if (not isinstance(shot, dict) or not isinstance(shot.get('id'), str)
                or not shot['id'] or shot['id'] in seen
                or not finite(shot.get('acceptedAtMs'))
                or type(shot.get('acceptedFrame')) is not int):
            defects.append('Malformed or duplicate accepted shot')
            continue
        seen.add(shot['id'])
        expected = shot.get('expectedFx')
        required = rules['requiredChannels']
        if not isinstance(expected, list) or any(c not in expected for c in required):
            defects.append('Missing required channel declaration: ' + shot['id'])
        # Policy comes from the budget, not a per-shot opt-out chosen by the game.
        for channel in required:
            required_pairs += 1
            records = observed.get((shot['id'], channel), [])
            if any(r['frame'] <= shot['acceptedFrame'] or r['presentedAtMs'] < shot['acceptedAtMs'] for r in records):
                defects.append('Render predates input: ' + shot['id'] + '/' + channel)
            valid = [r for r in records if r['frame'] > shot['acceptedFrame'] and r['presentedAtMs'] >= shot['acceptedAtMs']]
            frames = sorted({r['frame'] for r in valid})
            if len(frames) < rules['minPresentedFrames']:
                missing.append({'shotId': shot['id'], 'channel': channel, 'frames': frames})
                continue
            first = min(valid, key=lambda r: r['frame'])
            delay = first['frame'] - shot['acceptedFrame']
            delays.append(delay)
            if delay > rules['maxFirstFrameDelay']:
                defects.append('Feedback starts too late: ' + shot['id'] + '/' + channel)
    if any(key[0] not in seen for key in observed):
        defects.append('Render has no accepted shot')
    count_ok = len(shots) >= rules['minAcceptedShots']
    evidence = {'acceptedShots': len(shots), 'requiredPairs': required_pairs,
                'missingPairs': missing, 'missingRate': len(missing) / required_pairs if required_pairs else None,
                'maxFirstFrameDelay': max(delays) if delays else None, 'defects': defects,
                'limits': rules, 'scope': 'main-pass submission only; pixel visibility requires reviewed frames/video'}
    status = 'failed' if missing or defects else 'passed' if count_ok else 'unverified'
    if not count_ok:
        evidence['coverageGap'] = 'Not enough accepted shots'
    return {'status': status, 'evidence': evidence}
