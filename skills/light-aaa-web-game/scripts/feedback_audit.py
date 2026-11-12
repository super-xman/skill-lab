"""Match accepted player actions to observations from the completed main render pass."""
import math


def audit_feedback(payload, rules):
    legacy = 'minAcceptedShots' in rules and 'minAcceptedActions' not in rules
    id_key = 'shotId' if legacy else 'actionId'
    expected_key = 'expectedFx' if legacy else 'expectedChannels'
    count_key = 'acceptedShots' if legacy else 'acceptedActions'
    minimum = rules.get('minAcceptedShots' if legacy else 'minAcceptedActions')
    channels = rules.get('requiredChannels')
    if not channels or type(minimum) is not int or minimum < 1:
        return {'status': 'unverified', 'evidence': {'coverageGap': 'Missing feedback channels or sample target'}}

    actions = payload.get('shots' if legacy else 'actions', [])
    renders = payload.get('renders', [])
    if not isinstance(actions, list) or not isinstance(renders, list):
        return {'status': 'failed', 'evidence': {'defects': ['Invalid raw observation arrays']}}

    def finite(value):
        return type(value) in (float, int) and math.isfinite(value)

    seen, observed, defects = set(), {}, []
    for render in renders:
        if (not isinstance(render, dict) or not isinstance(render.get(id_key), str)
                or not isinstance(render.get('channel'), str)
                or type(render.get('frame')) is not int or render['frame'] < 0
                or not finite(render.get('presentedAtMs'))):
            defects.append('Malformed render observation')
            continue
        observed.setdefault((render[id_key], render['channel']), []).append(render)
    missing, delays, required_pairs = [], [], 0
    for action in actions:
        if (not isinstance(action, dict) or not isinstance(action.get('id'), str)
                or not action['id'] or action['id'] in seen
                or not finite(action.get('acceptedAtMs')) or type(action.get('acceptedFrame')) is not int):
            defects.append('Malformed or duplicate accepted action')
            continue
        action_id = action['id']
        seen.add(action_id)
        expected = action.get(expected_key)
        if not isinstance(expected, list) or any(c not in expected for c in channels):
            defects.append('Missing required channel declaration: ' + action_id)
        for channel in channels:
            required_pairs += 1
            records = observed.get((action_id, channel), [])
            valid = [r for r in records if r['frame'] > action['acceptedFrame']
                     and r['presentedAtMs'] >= action['acceptedAtMs']]
            if len(valid) != len(records):
                defects.append('Render predates input: ' + action_id + '/' + channel)
            frames = sorted({r['frame'] for r in valid})
            if len(frames) < rules['minPresentedFrames']:
                missing.append({id_key: action_id, 'channel': channel, 'frames': frames})
                continue
            delay = frames[0] - action['acceptedFrame']
            delays.append(delay)
            if delay > rules['maxFirstFrameDelay']:
                defects.append('Feedback starts too late: ' + action_id + '/' + channel)
    if any(key[0] not in seen for key in observed):
        defects.append('Render has no accepted action')
    evidence = {count_key: len(actions), 'requiredPairs': required_pairs, 'missingPairs': missing,
                'missingRate': len(missing) / required_pairs if required_pairs else None,
                'maxFirstFrameDelay': max(delays) if delays else None, 'defects': defects,
                'limits': rules, 'scope': 'main-pass submission only; pixel visibility requires reviewed frames/video'}
    if len(actions) < minimum:
        evidence['coverageGap'] = 'Not enough accepted actions'
    status = 'failed' if missing or defects else 'unverified' if len(actions) < minimum else 'passed'
    return {'status': status, 'evidence': evidence}
