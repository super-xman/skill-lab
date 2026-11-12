#!/usr/bin/env python3
"""Evidence-producing single-file Web game validator. No aesthetic certification."""
import argparse
import gzip
import hashlib
import importlib.util
import json
import math
import re
import statistics
import threading
import time
from functools import partial
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, urlencode, urlsplit
from network_audit import NetworkAudit
from feedback_audit import audit_feedback
from response_audit import audit_response, rule_errors, number
from stability_audit import audit_stability

SKILL = Path(__file__).resolve().parents[1]
AUDITS = ['geometry', 'materials', 'audio', 'determinism', 'navigation']
BROWSER_INPUTS = {'mouse', 'keyboard', 'touch', 'pen'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def gate(report, name, status, evidence):
    report['gates'].append({'id': name, 'status': status, 'evidence': evidence})


def aggregate(gates):
    statuses = [x['status'] for x in gates]
    if 'failed' in statuses:
        return 'failed'
    return 'unverified' if not statuses or 'unverified' in statuses else 'passed'


def profile_check(budget, report):
    version = budget.get('schemaVersion', 1)
    required = ['requiredExperienceGoals', 'feedbackRules', 'stabilityTargets']
    if version < 4:
        required.append('requiredMotionReviews')
    missing = [name for name in required if not budget.get(name)]
    if version < 3:
        gate(report, 'validation_profile', 'passed' if version == 2 and not missing else 'unverified',
             {'schemaVersion': version, 'missingV2Fields': missing})
        return

    def names(value, allow_empty=False):
        return (isinstance(value, list) and (allow_empty or bool(value))
                and all(isinstance(n, str) and n.strip() for n in value))

    for key in ['requiredScenes', 'requiredMotionReviews', 'requiredGameplayChecks',
                'requiredResourceChecks', 'requiredExperienceGoals']:
        optional = version == 4 and key in ('requiredMotionReviews', 'requiredResourceChecks')
        if not names(budget.get(key), allow_empty=optional):
            missing.append(key)
    backends = ('webgl', 'canvas2d', 'dom', 'svg') if version == 4 else ('webgl', 'canvas2d')
    if budget.get('renderBackend', None if version == 4 else 'webgl') not in backends:
        missing.append('renderBackend')
    if budget.get('benchmarkScene') not in (budget.get('requiredScenes') or []):
        missing.append('benchmarkScene')
    targets = budget.get('benchmarkLoad')
    if not isinstance(targets, dict) or not targets or not all(
            name.strip() and type(value) in (int, float) and math.isfinite(value) and value > 0
            for name, value in targets.items()):
        missing.append('benchmarkLoad')
    feedback = budget.get('feedbackRules') or {}
    if version == 4:
        missing.extend(rule_errors(feedback))
        if budget.get('renderMode') not in ('continuous', 'on-demand'):
            missing.append('renderMode')
        channels = feedback.get('channels') if isinstance(feedback, dict) else None
        uses_visuals = isinstance(channels, dict) and any(isinstance(c, dict) and c.get('source') == 'visual'
                                                          for c in channels.values())
        if not names(budget.get('visualDimensions'), allow_empty=not uses_visuals):
            missing.append('visualDimensions')
        device = budget.get('device')
        if not isinstance(device, dict):
            device = {}
        methods = device.get('inputMethods')
        # Other devices can be measured by a project scenario on the appropriate platform.
        gameplay_checks = budget.get('requiredGameplayChecks')
        if not names(gameplay_checks):
            gameplay_checks = []
        if not names(methods) or any('input_' + m not in gameplay_checks for m in set(methods) - BROWSER_INPUTS):
            missing.append('device.inputMethods')
        if type(device.get('isMobile')) is not bool:
            missing.append('device.isMobile')
        if not number(device.get('deviceScaleFactor')) or device['deviceScaleFactor'] <= 0:
            missing.append('device.deviceScaleFactor')
        if not names((budget.get('stabilityTargets') or {}).get('trackedResources'), allow_empty=True):
            missing.append('stabilityTargets.trackedResources')
        growth = (budget.get('stabilityTargets') or {}).get('resourceGrowthMax', 0)
        if not number(growth) or growth < 0:
            missing.append('stabilityTargets.resourceGrowthMax')
        if not number(budget.get('visualScoreMin')) or not 1 <= budget['visualScoreMin'] <= 5:
            missing.append('visualScoreMin')
    else:
        if not names(feedback.get('requiredChannels')):
            missing.append('feedbackRules.requiredChannels')
        for key in ['minAcceptedActions', 'minPresentedFrames', 'maxFirstFrameDelay']:
            if type(feedback.get(key)) is not int or feedback[key] < 1:
                missing.append('feedbackRules.' + key)
    active = (budget.get('stabilityTargets') or {}).get('activePlaySeconds')
    if type(active) not in (int, float) or not math.isfinite(active) or active <= 0:
        missing.append('stabilityTargets.activePlaySeconds')
    gate(report, 'validation_profile', 'passed' if version in (3, 4) and not missing else 'unverified',
         {'schemaVersion': version, 'missingOrInvalid': sorted(set(missing))})


def benchmark_load(budget, metrics):
    """Compare a measured scene to its project's predeclared representative load."""
    if budget.get('schemaVersion', 1) >= 3:
        limits = budget.get('benchmarkLoad', {})
        observed = metrics.get('workload') or {}
    else:
        limits = {'enemiesAlive': budget['benchmarkMinEnemies'], 'effectsActive': budget['benchmarkMinEffects']}
        observed = metrics
    actual = {key: observed.get(key) for key in limits}
    meets_limits = bool(limits) and all(
        type(value) in (int, float) and math.isfinite(value) and value >= limits[key]
        for key, value in actual.items())
    return meets_limits, {'minimum': limits, 'observed': actual}


class AssetParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []
        self.style = False
        self.css = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'style':
            self.style = True
        if attrs.get('style'):
            self.css.append(attrs['style'])
        for name in ['src', 'srcset', 'poster', 'data']:
            value = attrs.get(name, '')
            if value and not value.startswith(('data:', 'blob:', '#')):
                self.refs.append({'tag': tag, 'attribute': name, 'value': value})
        if tag == 'link' and set(attrs.get('rel', '').lower().split()) & {
                'stylesheet', 'preload', 'modulepreload', 'icon', 'prefetch', 'preconnect',
                'dns-prefetch', 'manifest', 'apple-touch-icon'}:
            value = attrs.get('href', '')
            if value and not value.startswith(('data:', 'blob:', '#')):
                self.refs.append({'tag': tag, 'attribute': 'href', 'value': value})
        if tag in ['image', 'use', 'feimage']:
            for name in ['href', 'xlink:href']:
                value = attrs.get(name, '')
                if value and not value.startswith(('data:', 'blob:', '#')):
                    self.refs.append({'tag': tag, 'attribute': name, 'value': value})

    def handle_endtag(self, tag):
        if tag == 'style':
            self.style = False

    def handle_data(self, data):
        if self.style:
            self.css.append(data)


def static_checks(path, budget, report):
    raw = path.read_bytes()
    source = raw.decode('utf-8')
    parser = AssetParser()
    parser.feed(source)
    css = '\n'.join(parser.css)
    for value in re.findall(r'url\(\s*[\'\"]?([^\)\'\"]+)', css, re.I):
        if not value.startswith(('data:', 'blob:', '#')):
            parser.refs.append({'tag': 'css', 'value': value})
    for value in re.findall(r'@import\s+[\'\"]([^\'\"]+)', css, re.I):
        parser.refs.append({'tag': 'css-import', 'value': value})
    for value in re.findall(r'(?://[#@]|/\*[#@])\s*sourceMappingURL=([^\s*]+)', source):
        if not value.startswith(('data:', 'blob:')):
            parser.refs.append({'tag': 'source-map', 'value': value})
    report['artifact'] = {'path': str(path), 'sha256': sha(path), 'rawBytes': len(raw),
                          'gzipBytes': len(gzip.compress(raw, mtime=0)), 'gzipLevel': 9}
    for metric, limit in [('rawBytes', 'rawBytesMax'), ('gzipBytes', 'gzipBytesMax')]:
        actual = report['artifact'][metric]
        gate(report, metric, 'passed' if actual <= budget[limit] else 'failed',
             {'actual': actual, 'max': budget[limit]})
    gate(report, 'declared_resources_self_contained', 'failed' if parser.refs else 'passed', parser.refs)


def image_metrics(path):
    from PIL import Image, ImageStat
    with Image.open(path) as image:
        gray = image.convert('L')
        hist = gray.histogram()
        pixels = gray.width * gray.height
        return {'width': gray.width, 'height': gray.height,
                'lumaStdDev': round(ImageStat.Stat(gray).stddev[0], 3),
                'blackFraction': round(sum(hist[:5]) / pixels, 5),
                'whiteFraction': round(sum(hist[251:]) / pixels, 5),
                'entropy': round(gray.entropy(), 3)}


def percentile(values, p):
    values = sorted(values)
    index = (len(values) - 1) * p
    low = math.floor(index)
    return values[low] + (values[min(low + 1, len(values) - 1)] - values[low]) * (index - low)


def measured_checks(report, prefix, payload, required):
    items = payload.get('checks', []) if isinstance(payload, dict) else []
    index = {c.get('id'): c for c in items if isinstance(c, dict)}
    for name in required:
        check = index.get(name, {})
        status = check.get('status', 'unverified')
        evidence = check.get('evidence')
        if status not in ['passed', 'failed', 'unverified'] or not evidence:
            status = 'unverified'
        gate(report, prefix + name, status, evidence or 'Missing measured evidence')


METRICS = """() => {
  if(window.__GAME_TEST__) return window.__GAME_TEST__.metrics();
  const g=window.__G;
  if(!g) return {};
  return {frame:window.__frames, quality:g.quality?.name,
    drawCalls:g.renderer.info.render.calls,
    submittedTriangles:g.renderer.info.render.triangles,
    internalWidth:g.render.resolution.x, internalHeight:g.render.resolution.y,
    sceneId:'reference', dynamicResolution:null};
}"""
DEVICE_STATE = """() => ({dpr: devicePixelRatio, touchPoints: navigator.maxTouchPoints,
  coarsePointer: matchMedia('(pointer:coarse)').matches, viewport: [innerWidth, innerHeight]})"""
GPU = """options => {
  const backend = typeof options === 'string' ? options : options.backend;
  const canvas = document.querySelector('canvas[data-game-canvas]') || document.querySelector('canvas#view') || document.querySelector('canvas');
  const result = {backend, available: false, canvas: !!canvas, renderer: 'unknown', identified: false};
  if (backend === 'dom' || backend === 'svg') {
    const visible = el => {
      const box = el?.getBoundingClientRect();
      return !!(box?.width && box.height && getComputedStyle(el).visibility !== 'hidden');
    };
    const root = backend === 'svg' ? document.querySelector('svg[data-game-root]') || document.querySelector('svg')
      : document.querySelector('[data-game-root]') || document.querySelector('main') ||
        (visible(document.body) ? document.body : [...document.body.children].find(visible));
    result.available = visible(root);
    result.surface = root?.tagName || null;
  } else {
    if (!canvas || typeof canvas.getContext !== 'function') return result;
    if (backend === 'canvas2d') result.available = !!canvas.getContext('2d');
  }
  const separate = backend !== 'webgl';
  if (separate && options.onDemand) return result;
  const probe = separate ? document.createElement('canvas') : canvas;
  result.adapterSource = separate ? 'separate WebGL canvas' : 'game WebGL context';
  const gl = probe.getContext('webgl2') || probe.getContext('webgl');
  result.webgl = !!gl;
  if (!gl) return result;
  if (!separate) result.available = true;
  const ext = gl.getExtension('WEBGL_debug_renderer_info');
  result.renderer = String(gl.getParameter(ext ? ext.UNMASKED_RENDERER_WEBGL : gl.RENDERER));
  result.identified = !!ext;
  result.version = gl.getParameter(gl.VERSION);
  if (separate) gl.getExtension('WEBGL_lose_context')?.loseContext();
  return result;
}"""


def wait_for_observation(page, expression, timeout_seconds):
    # These fixed diagnostics expressions must also work under the shipped HTML's CSP.
    page.evaluate(f"""ms => new Promise((resolve, reject) => {{
      const deadline = performance.now() + ms;
      function check() {{
        if ({expression}) resolve(true);
        else if (performance.now() >= deadline) reject(new Error('Game observation timed out'));
        else setTimeout(check, 25);
      }}
      check();
    }})""", timeout_seconds * 1000)


def measure_frames(page, budget, report, before, has_contract, hardware, timeout):
    page.evaluate("""seconds => {
      window.__SKILL_SAMPLE__={done:false,ms:[]};
      let start=null,last=null;
      function tick(now) {
        if(start===null) start=now;
        if(last!==null) window.__SKILL_SAMPLE__.ms.push(now-last);
        last=now;
        if(now-start < seconds*1000) requestAnimationFrame(tick);
        else window.__SKILL_SAMPLE__.done=true;
      }
      requestAnimationFrame(tick);
    }""", budget['sampleSeconds'])
    wait_for_observation(page, 'window.__SKILL_SAMPLE__.done', timeout)
    samples = page.evaluate('window.__SKILL_SAMPLE__.ms')
    after = page.evaluate(METRICS)
    perf = {'samples': len(samples), 'meanMs': statistics.mean(samples) if samples else None,
            'before': before, 'after': after, 'hardware': hardware}
    if samples:
        perf.update({'fps': 1000 / statistics.mean(samples),
                     'p50Ms': percentile(samples, .5), 'p95Ms': percentile(samples, .95),
                     'p99Ms': percentile(samples, .99)})
    report['performance'] = perf
    advancing = isinstance(before.get('frame'), (int, float)) and isinstance(after.get('frame'), (int, float))
    gate(report, 'render_advances', ('passed' if after['frame'] > before['frame'] else 'failed')
         if advancing else 'unverified', {'before': before.get('frame'), 'after': after.get('frame')})
    frame_delta = after['frame'] - before['frame'] if advancing else 0
    load_ok, load_evidence = benchmark_load(budget, after)
    if budget.get('schemaVersion', 1) >= 3:
        started_loaded, start_evidence = benchmark_load(budget, before)
        load_ok = started_loaded and load_ok
        gate(report, 'representative_load', 'passed' if has_contract and load_ok else 'unverified',
             {'start': start_evidence, 'end': load_evidence})
    resolution_ok = (after.get('internalWidth', 0) >= budget['viewport']['width'] * budget['internalResolutionMinScale'] and
                     after.get('internalHeight', 0) >= budget['viewport']['height'] * budget['internalResolutionMinScale'])
    comparable = hardware and has_contract and load_ok and resolution_ok and frame_delta >= len(samples) * .9 and after.get('dynamicResolution') is False and (
        after.get('sceneId') == budget['benchmarkScene'] and after.get('quality') == budget['quality']
        and before.get('internalWidth') == after.get('internalWidth')
        and before.get('internalHeight') == after.get('internalHeight')
        and bool(after.get('internalWidth')) and bool(after.get('internalHeight')))
    enough = len(samples) >= budget['minFrameSamples']
    passed = enough and perf.get('fps', 0) >= budget['fpsMin'] and (
        perf.get('p95Ms', math.inf) <= budget['p95FrameMsMax'] and
        perf.get('p99Ms', math.inf) <= budget['p99FrameMsMax'])
    gate(report, 'hardware_frame_budget', ('passed' if passed else 'failed') if comparable else 'unverified', perf)
    return after


def browser_checks(args, budget, report, out):
    from playwright.sync_api import sync_playwright

    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *unused):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(args.html.parent)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = f'http://127.0.0.1:{server.server_port}'
    entry = origin + '/' + quote(args.html.name)
    errors, console_errors = [], []
    network = None
    version = budget.get('schemaVersion', 1)
    device = budget['device'] if version == 4 else {}
    methods = device.get('inputMethods', [])
    input_samples = set()
    try:
        with sync_playwright() as pw:
            launch = {'headless': not args.headed, 'args': ['--no-sandbox']}
            if args.browser:
                launch['executable_path'] = args.browser
            if args.software:
                launch['args'] += ['--use-angle=swiftshader', '--enable-unsafe-swiftshader']
            browser = pw.chromium.launch(**launch)
            report['browserVersion'] = browser.version
            context = browser.new_context(viewport=budget['viewport'], service_workers='block',
                                          device_scale_factor=device.get('deviceScaleFactor', 1),
                                          is_mobile=device.get('isMobile', False), has_touch='touch' in methods)
            page = context.new_page()
            if version == 4:
                def record_input(method, dpr, touch_points):
                    input_samples.add((method, dpr, touch_points))
                page.expose_function('__skillObservedInput', record_input)
                page.add_init_script("""for (const event of ['pointerdown', 'keydown', 'wheel']) {
                  addEventListener(event, e => {
                    if (!e.isTrusted) return;
                    const method = event === 'keydown' ? 'keyboard' : event === 'wheel' ? 'mouse' : e.pointerType;
                    if (method) window.__skillObservedInput(method, devicePixelRatio, navigator.maxTouchPoints);
                  }, {capture:true, passive:true});
                }""")
            page.set_default_timeout(args.timeout * 1000)
            page.add_init_script("window.__SKILL_BOOT_ERROR__=null; addEventListener('error', e => {window.__SKILL_BOOT_ERROR__=String(e.message || e.error || 'script error');});")
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.on('console', lambda m: console_errors.append(m.text) if m.type == 'error' else None)
            query = {'test': 1, 'seed': budget['seed'], 'q': budget['quality']}
            if args.adapter == 'reference':
                query['shot'] = 1
            entry_url = entry + '?' + urlencode(query)
            network = NetworkAudit(context, page, entry_url)
            started = time.perf_counter()
            page.goto(entry_url, wait_until='domcontentloaded')
            ready = ('window.__ready || window.__fatal' if args.adapter == 'reference' else
                     'window.__GAME_TEST__ && (window.__GAME_TEST__.ready || window.__GAME_TEST__.fatal)')
            wait_for_observation(page, '(' + ready + ') || window.__SKILL_BOOT_ERROR__', args.timeout)
            boot_ms = (time.perf_counter() - started) * 1000
            fatal = page.evaluate('window.__GAME_TEST__?.fatal || window.__fatal || window.__SKILL_BOOT_ERROR__ || null')
            gate(report, 'boot', 'failed' if fatal else 'passed', {'fatal': fatal, 'bootMs': round(boot_ms, 1)})
            if fatal:
                return
            backend = budget.get('renderBackend', 'webgl') if budget.get('schemaVersion', 1) >= 3 else 'webgl'
            gpu = page.evaluate(GPU, {'backend': backend, 'onDemand': version == 4 and budget['renderMode'] == 'on-demand'})
            report['gpu'] = gpu
            hardware = gpu['available'] and gpu['identified'] and not args.software and not device.get('isMobile') and not re.search(
                r'SwiftShader|llvmpipe|Software|softpipe|unknown', gpu['renderer'], re.I)
            renderer_gate = 'render_backend' if budget.get('schemaVersion', 1) >= 3 else 'webgl'
            gate(report, renderer_gate, 'passed' if gpu['available'] else 'failed', gpu)
            boot_status = 'passed' if boot_ms <= budget['bootMsMax'] else 'failed'
            gate(report, 'browser_boot_budget' if version == 4 else 'hardware_boot_budget',
                 boot_status if version == 4 or hardware else 'unverified',
                 {'bootMs': round(boot_ms, 1), 'max': budget['bootMsMax'], 'hardware': hardware})
            if version == 4:
                report['device'] = page.evaluate(DEVICE_STATE)
                report['device']['profile'] = device
            has_contract = page.evaluate('!!window.__GAME_TEST__')
            gate(report, 'diagnostics_contract', 'passed' if has_contract else 'unverified',
                 {'adapter': args.adapter, 'contractPresent': has_contract})
            scenes = budget['requiredScenes'] if has_contract else ['overview']
            for scene_id in scenes:
                if has_contract:
                    page.evaluate('(id) => window.__GAME_TEST__.setScene(id)', scene_id)
                page.evaluate('() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))')
                safe_id = re.sub(r'[^A-Za-z0-9_-]', '_', scene_id)
                screenshot = out / f'{safe_id}.png'
                page.screenshot(path=str(screenshot), timeout=args.timeout * 1000)
                measures = image_metrics(screenshot)
                report['screenshots'].append({'id': scene_id, 'path': str(screenshot),
                                              'sha256': sha(screenshot), 'metrics': measures})
                if version < 4:
                    gate(report, 'nonblank_' + scene_id, 'passed' if measures['lumaStdDev'] > 2 else 'failed', measures)
            gate(report, 'required_views', 'passed' if set(scenes) >= set(budget['requiredScenes']) else 'unverified', scenes)
            if has_contract:
                audit = page.evaluate('() => window.__GAME_TEST__.audit()')
            else:
                audit = {}
            resource_checks = (budget.get('requiredResourceChecks', []) if budget.get('schemaVersion', 1) >= 3
                               else AUDITS)
            measured_checks(report, 'resource_', audit, resource_checks)
            if has_contract:
                page.evaluate('(id) => window.__GAME_TEST__.setScene(id)', budget['benchmarkScene'])
            page.wait_for_timeout(budget['warmupSeconds'] * 1000)
            before = page.evaluate(METRICS)
            if version == 4 and budget['renderMode'] == 'on-demand':
                loaded, evidence = benchmark_load(budget, before)
                in_scene = before.get('sceneId') == budget['benchmarkScene']
                gate(report, 'representative_load', 'passed' if has_contract and in_scene and loaded else 'unverified',
                     {'scene': before.get('sceneId'), 'workload': evidence})
                report['performance'] = {'mode': 'on-demand', 'basis': 'action_response', 'benchmark': before}
                after = before
            else:
                after = measure_frames(page, budget, report, before, has_contract, hardware, args.timeout)
            if backend == 'webgl':
                for metric, maximum in [('drawCalls', 'drawCallsMax'), ('submittedTriangles', 'submittedTrianglesMax')]:
                    actual = after.get(metric)
                    valid = number(actual) and (actual >= 0 if version == 4 and metric == 'submittedTriangles' else actual > 0)
                    gate(report, metric, ('passed' if actual <= budget[maximum] else 'failed')
                         if valid and has_contract else 'unverified', {'actual': actual, 'max': budget[maximum],
                                                                     'scene': after.get('sceneId')})
            gameplay = {}
            if args.scenario_script:
                import inspect
                spec = importlib.util.spec_from_file_location('game_scenarios', args.scenario_script)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if 'artifacts_dir' in inspect.signature(module.run).parameters:
                    gameplay = module.run(page, artifacts_dir=out)
                else:
                    gameplay = module.run(page)
            measured_checks(report, 'gameplay_', gameplay, budget['requiredGameplayChecks'])
            if version == 4:
                actual = report['device']
                end = page.evaluate(DEVICE_STATE)
                observed = {sample[0] for sample in input_samples}
                samples = [{'method': m, 'dpr': d, 'touchPoints': t} for m, d, t in sorted(input_samples)]
                settings_match = all(abs(s['dpr'] - device['deviceScaleFactor']) < .01
                                     and ('touch' not in methods or s['touchPoints'] > 0)
                                     for s in [actual, *samples, end])
                custom = set(methods) - BROWSER_INPUTS
                statuses = {g['id']: g['status'] for g in report['gates']}
                project_inputs = {m: statuses.get('gameplay_input_' + m, 'unverified') for m in custom}
                confirmed = {m for m, status in project_inputs.items() if status == 'passed'}
                absent = sorted(set(methods) - observed - confirmed)
                wrong = not settings_match or 'failed' in project_inputs.values()
                gate(report, 'player_input', 'failed' if wrong else 'unverified' if absent else 'passed',
                     {'start': actual, 'end': end, 'atInput': samples, 'observed': sorted(observed),
                      'projectChecks': project_inputs, 'missing': absent})
            if budget.get('feedbackRules'):
                audit_fn = audit_response if version == 4 else audit_feedback
                feedback = audit_fn(gameplay.get('feedback', {}), budget['feedbackRules'])
                gate(report, 'action_response' if version == 4 else 'action_feedback_submission',
                     feedback['status'], feedback['evidence'])
            if budget.get('stabilityTargets'):
                stability = audit_stability(gameplay.get('stability', {}), budget['stabilityTargets'],
                                            report['artifact']['sha256'], budget['renderMode'] if version == 4 else None)
                gate(report, 'stability_contract', stability['status'], stability['evidence'])
            report['motionEvidence'] = []
            for capture in gameplay.get('captures', []):
                path = (out / capture['path']).resolve()
                if not path.is_relative_to(out) or not path.is_file():
                    raise ValueError('Motion evidence must be an existing file inside the validation output')
                if path.suffix.lower() not in ['.png', '.webm', '.mp4']:
                    raise ValueError('Motion evidence must be real PNG frames or a recorded video')
                report['motionEvidence'].append({'id': capture['id'], 'path': str(path), 'sha256': sha(path)})
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        net = network.result() if network else {'status': 'unverified', 'evidence': 'Browser network audit did not start'}
        report['requests'] = network.requests if network else []
        report['errors'] = {'page': errors, 'console': console_errors}
        gate(report, 'no_runtime_errors', 'failed' if errors or console_errors else 'passed', report['errors'])
        gate(report, 'offline_resources', net['status'], net['evidence'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('html', type=Path)
    parser.add_argument('--budget', type=Path, default=SKILL / 'templates/budgets.json')
    parser.add_argument('--out', type=Path, default=Path('artifacts/validation'))
    parser.add_argument('--browser', help='Optional Chromium executable')
    parser.add_argument('--software', action='store_true')
    parser.add_argument('--headed', action='store_true')
    parser.add_argument('--static-only', action='store_true')
    parser.add_argument('--adapter', choices=['standard', 'reference'], default='standard')
    parser.add_argument('--scenario-script', type=Path)
    parser.add_argument('--timeout', type=int, default=180)
    args = parser.parse_args()
    args.html = args.html.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    budget = json.loads(args.budget.read_text())
    report = {'schemaVersion': 1, 'validatorSha256': sha(Path(__file__)),
              'toolSha256': {name: sha(Path(__file__).with_name(name)) for name in
                             ['network_audit.py', 'feedback_audit.py', 'response_audit.py', 'stability_audit.py']},
              'budgetSha256': sha(args.budget), 'budget': budget, 'gates': [], 'screenshots': [],
              'releaseStatus': 'unverified', 'visualReview': 'pending'}
    try:
        profile_check(budget, report)
        static_checks(args.html, budget, report)
        if args.static_only:
            gate(report, 'runtime', 'unverified', 'Static-only invocation')
        elif budget.get('schemaVersion') == 4 and report['gates'][0]['status'] != 'passed':
            gate(report, 'runtime', 'unverified', 'Complete the declared project profile before running it')
        else:
            browser_checks(args, budget, report, out)
    except Exception as exc:
        gate(report, 'validator_execution', 'failed', {'type': type(exc).__name__, 'message': str(exc)})
    report['automatedStatus'] = aggregate(report['gates'])
    if report['automatedStatus'] == 'failed':
        report['releaseStatus'] = 'failed'
    path = out / 'report.json'
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    counts = {status: sum(g['status'] == status for g in report['gates'])
              for status in ['passed', 'failed', 'unverified']}
    print(json.dumps({'report': str(path), 'sha256': sha(path), 'automatedStatus': report['automatedStatus'],
                      'gates': counts, 'visualReview': 'pending'}, ensure_ascii=False))
    return {'passed': 0, 'failed': 2, 'unverified': 3}[report['automatedStatus']]


if __name__ == '__main__':
    raise SystemExit(main())
