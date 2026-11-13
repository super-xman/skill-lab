"""Run selected project checks against named, locally restored game scenes."""
import importlib.util
import math
from urllib.parse import urlencode

from network_audit import NetworkAudit


def load_driver(path):
    spec = importlib.util.spec_from_file_location('game_scenarios', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def planned_cases(config, requested):
    if not isinstance(config, dict) or not config:
        raise ValueError('Declare focusedChecks in the project budget')
    unknown = set(requested) - config.keys()
    if unknown:
        raise ValueError('Unknown focus: ' + ', '.join(sorted(unknown)))
    plan = []
    for focus in dict.fromkeys(requested):
        cases = config[focus]
        if not isinstance(cases, list) or not cases:
            raise ValueError('No cases declared for ' + focus)
        scenes = set()
        for case in cases:
            scene = case.get('scene') if isinstance(case, dict) else None
            checks = case.get('checks') if isinstance(case, dict) else None
            if (not isinstance(scene, str) or not scene.strip() or scene in scenes
                    or not isinstance(checks, list) or not checks
                    or not all(isinstance(key, str) and key.strip() for key in checks)
                    or len(set(checks)) != len(checks)):
                raise ValueError('Each case needs a distinct scene and named checks in ' + focus)
            scenes.add(scene)
            plan.append((focus, scene, checks))
    return plan


def compare(actual, expected, operator='eq'):
    """Compare a project observation with its documented acceptance criterion."""
    numeric = all(type(v) in (int, float) and math.isfinite(v) for v in (actual, expected))
    if operator == 'eq' and numeric:
        return actual == expected
    if operator == 'eq':
        return type(actual) is type(expected) and actual == expected
    if operator not in ('gte', 'lte'):
        raise ValueError('Unknown comparison: ' + operator)
    if not numeric:
        raise ValueError('An ordered measurement needs finite numbers')
    return actual >= expected if operator == 'gte' else actual <= expected


def assertion_gates(payload, names):
    readings = payload.get('observations', {}) if isinstance(payload, dict) else {}
    if not isinstance(readings, dict):
        raise ValueError('observations must map check names to measurements')
    gates = []
    for name in names:
        reading = readings.get(name)
        if (not isinstance(reading, dict) or reading.get('actual') is None
                or reading.get('expected') is None):
            status = 'unverified'
        else:
            status = 'passed' if compare(reading['actual'], reading['expected'],
                                         reading.get('op', 'eq')) else 'failed'
        gates.append({'id': name, 'status': status, 'evidence': reading or 'Missing measurement'})
    return gates


def capture_files(payload, case_dir, digest):
    files = []
    for name in payload.get('captures', []):
        path = (case_dir / name).resolve()
        if not path.is_relative_to(case_dir) or not path.is_file() or not path.stat().st_size:
            raise ValueError('Capture must be a nonempty file from this case: ' + str(name))
        files.append({'path': str(path), 'sha256': digest(path)})
    return files


def run_cases(browser, entry, args, budget, report, run_dir, wait_ready, digest, aggregate):
    plan = planned_cases(budget.get('focusedChecks'), args.focus)
    driver = load_driver(args.scenario_script)
    run = getattr(driver, 'run_focused', None)
    if not callable(run):
        raise ValueError('Scenario script must implement run_focused(page, focus, scene, artifacts_dir)')
    device = budget.get('device', {})
    for index, (focus, scene, checks) in enumerate(plan):
        case_dir = run_dir / f'case-{index + 1}'
        case_dir.mkdir()
        query = {'test': 1, 'scene': scene, 'seed': budget['seed'], 'q': budget['quality']}
        url = entry + '?' + urlencode(query)
        case = {'focus': focus, 'scene': scene, 'query': urlencode(query), 'checks': [], 'captures': []}
        report['cases'].append(case)
        context = browser.new_context(viewport=budget['viewport'], service_workers='block',
                                      device_scale_factor=device.get('deviceScaleFactor', 1),
                                      is_mobile=device.get('isMobile', False),
                                      has_touch='touch' in device.get('inputMethods', []))
        errors = []
        network = None
        try:
            page = context.new_page()
            page.set_default_timeout(args.timeout * 1000)
            page.add_init_script("""addEventListener('error', e => {
              window.__SKILL_BOOT_ERROR__ = String(e.message || e.error || 'script error');
            });""")
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
            network = NetworkAudit(context, page, url)
            page.goto(url, wait_until='domcontentloaded')
            wait_ready(page, 'window.__GAME_TEST__?.ready || window.__GAME_TEST__?.fatal || window.__SKILL_BOOT_ERROR__', args.timeout)
            fatal = page.evaluate('window.__GAME_TEST__?.fatal || window.__SKILL_BOOT_ERROR__ || null')
            if fatal:
                raise ValueError(str(fatal))
            # Older games have setScene() but do not consume scene= at startup.
            if not page.evaluate('window.__GAME_TEST__.handlesSceneQuery === true'):
                page.evaluate('id => window.__GAME_TEST__.setScene(id)', scene)
            actual = page.evaluate('window.__GAME_TEST__.metrics().sceneId')
            case['observedScene'] = actual
            if actual != scene:
                raise ValueError(f'Requested scene {scene!r}, observed {actual!r}')
            payload = run(page, focus, scene, case_dir)
            if not isinstance(payload, dict):
                raise ValueError('run_focused must return observations')
            case['checks'].extend(assertion_gates(payload, checks))
            case['captures'] = capture_files(payload, case_dir, digest)
        except Exception as exc:
            case['checks'].append({'id': 'case_execution', 'status': 'failed', 'evidence': str(exc)})
        finally:
            if network is not None:
                case['checks'].append({'id': 'offline_resources', **network.result()})
            context.close()
        case['checks'].append({'id': 'no_runtime_errors', 'status': 'failed' if errors else 'passed',
                               'evidence': errors})
        case['status'] = aggregate(case['checks'])
        report['gates'].append({'id': focus + '/' + scene, 'status': case['status'],
                                'evidence': {'case': index + 1}})
