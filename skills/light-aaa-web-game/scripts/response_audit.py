"""Compare independently observed player-facing output to a project's declared outcomes."""
import math


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def named(value):
    return isinstance(value, str) and bool(value.strip())


def observable(value):
    return type(value) is bool or named(value) or number(value)


def rule_errors(rules):
    if not isinstance(rules, dict):
        return ['feedbackRules']
    errors = []
    if type(rules.get('minAcceptedActions')) is not int or rules['minAcceptedActions'] < 1:
        errors.append('feedbackRules.minAcceptedActions')
    channels = rules.get('channels')
    if not isinstance(channels, dict) or not channels:
        return errors + ['feedbackRules.channels']
    for name, rule in channels.items():
        if not named(name) or not isinstance(rule, dict):
            errors.append('feedbackRules.channels')
            continue
        expected = rule.get('expected')
        if (not named(rule.get('source')) or not isinstance(expected, dict) or not expected
                or not all(named(k) and observable(v) for k, v in expected.items())
                or rule.get('scope', 'shared') not in ('shared', 'per-action')
                or not number(rule.get('maxDelayMs')) or rule['maxDelayMs'] <= 0
                or not number(rule.get('holdMs', 0)) or rule.get('holdMs', 0) < 0
                or not number(rule.get('tolerance', 0)) or rule.get('tolerance', 0) < 0):
            errors.append('feedbackRules.channels.' + name)
    return errors


def matches(actual, target, tolerance):
    if number(target):
        return number(actual) and abs(actual - target) <= tolerance
    return type(actual) is type(target) and actual == target


def audit_response(payload, rules):
    gaps = rule_errors(rules)
    if gaps:
        return {'status': 'unverified', 'evidence': {'coverageGaps': gaps}}
    if not isinstance(payload, dict) or not all(isinstance(payload.get(k, []), list)
                                                for k in ('actions', 'observations')):
        return {'status': 'failed', 'evidence': {'defects': ['Malformed response observations']}}
    channels = rules['channels']
    required = {(name, condition) for name, rule in channels.items() for condition in rule['expected']}
    actions = {}
    defects = []
    for item in payload.get('actions', []):
        if (not isinstance(item, dict) or not named(item.get('id')) or item['id'] in actions
                or not named(item.get('condition')) or not number(item.get('acceptedAtMs')) or item['acceptedAtMs'] < 0):
            defects.append('Malformed or duplicate accepted action')
            continue
        actions[item['id']] = item
    # A later input can replace a shared display or mix. Samples taken afterwards
    # cannot establish how long the older state was visible or audible.
    replaced_at = {}
    next_input = {}
    for action in sorted(actions.values(), key=lambda a: a['acceptedAtMs'], reverse=True):
        for name, rule in channels.items():
            if rule.get('scope', 'shared') == 'shared' and action['condition'] in rule['expected']:
                if name in next_input:
                    replaced_at[action['id'], name] = next_input[name]
                next_input[name] = action['acceptedAtMs']
    observations = {}
    for item in payload.get('observations', []):
        if (not isinstance(item, dict) or not named(item.get('actionId')) or item['actionId'] not in actions
                or not named(item.get('channel')) or item['channel'] not in channels
                or not number(item.get('atMs')) or not observable(item.get('value'))):
            defects.append('Malformed observation or unknown action/channel')
            continue
        name, action = item['channel'], actions[item['actionId']]
        if (item.get('source') != channels[name]['source'] or item['atMs'] < action['acceptedAtMs']
                or action['condition'] not in channels[name]['expected']):
            defects.append(f"Wrong source, condition or timestamp: {item['actionId']}/{name}")
            continue
        observations.setdefault((item['actionId'], name), []).append(item)
    covered = set()
    max_delay = {}
    for action_id, action in actions.items():
        condition = action['condition']
        applicable = [name for name, rule in channels.items() if condition in rule['expected']]
        if not applicable:
            defects.append('Undeclared action condition: ' + condition)
        for name in applicable:
            rule = channels[name]
            covered.add((name, condition))
            label = f'{action_id}/{name}'
            samples = sorted(observations.get((action_id, name), []), key=lambda s: s['atMs'])
            if not samples:
                defects.append('Accepted action has no observed output: ' + label)
                continue
            end = replaced_at.get((action_id, name), math.inf)
            samples = [s for s in samples if s['atMs'] < end]
            if not samples:
                gaps.append('No observation before the next input on this channel: ' + label)
                continue
            target, tolerance = rule['expected'][condition], rule.get('tolerance', 0)
            start = next((i for i, s in enumerate(samples) if matches(s['value'], target, tolerance)), None)
            if start is None:
                defects.append('Observed output differs from expected: ' + label)
                continue
            first = samples[start]['atMs']
            delay = first - action['acceptedAtMs']
            max_delay[name] = max(delay, max_delay.get(name, 0))
            if delay > rule['maxDelayMs']:
                defects.append('Output arrived too late: ' + label)
            if rule.get('holdMs', 0) > 0:
                deadline = first + rule['holdMs']
                for s in samples[start + 1:]:
                    if not matches(s['value'], target, tolerance):
                        defects.append('Output did not persist: ' + label)
                        break
                    if s['atMs'] >= deadline:
                        break
                else:
                    gaps.append('Missing later observation of persistent output: ' + label)
    if len(actions) < rules['minAcceptedActions']:
        gaps.append('Insufficient accepted actions')
    gaps.extend(f'Unexercised condition: {name}/{condition}' for name, condition in sorted(required - covered))
    return {'status': 'failed' if defects else 'unverified' if gaps else 'passed',
            'evidence': {'acceptedActions': len(actions), 'maxDelayMs': max_delay,
                         'coverageGaps': gaps, 'defects': defects, 'observations': payload, 'limits': rules}}
