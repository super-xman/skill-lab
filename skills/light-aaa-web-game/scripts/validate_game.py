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
from stability_audit import audit_stability

SKILL = Path(__file__).resolve().parents[1]
AUDITS = ['geometry', 'materials', 'audio', 'determinism', 'navigation']


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
    required = ['requiredMotionReviews', 'requiredExperienceGoals', 'feedbackRules', 'stabilityTargets']
    missing = [name for name in required if not budget.get(name)]
    valid = budget.get('schemaVersion', 1) >= 2 and not missing
    gate(report, 'validation_profile', 'passed' if valid else 'unverified',
         {'schemaVersion': budget.get('schemaVersion', 1), 'missingV2Fields': missing,
          'note': 'A v1 budget is historical coverage, not v2 acceptance. Merge new gates without relaxing existing limits.'})


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
GPU = """() => {
  const canvas=document.querySelector('[data-game-canvas]') || document.querySelector('#view') || document.querySelector('canvas');
  if(!canvas) return {renderer:'unknown',canvas:false};
  const gl=canvas.getContext('webgl2') || canvas.getContext('webgl');
  if(!gl) return {renderer:'unknown',canvas:true,webgl:false};
  const ext=gl.getExtension('WEBGL_debug_renderer_info');
  return {renderer:String(gl.getParameter(ext?ext.UNMASKED_RENDERER_WEBGL:gl.RENDERER)),
    version:gl.getParameter(gl.VERSION),identified:!!ext,canvas:true,webgl:true};
}"""


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
    try:
        with sync_playwright() as pw:
            launch = {'headless': not args.headed, 'args': ['--no-sandbox']}
            if args.browser:
                launch['executable_path'] = args.browser
            if args.software:
                launch['args'] += ['--use-angle=swiftshader', '--enable-unsafe-swiftshader']
            browser = pw.chromium.launch(**launch)
            report['browserVersion'] = browser.version
            context = browser.new_context(viewport=budget['viewport'], device_scale_factor=1,
                                          service_workers='block')
            page = context.new_page()
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
            page.wait_for_function('(' + ready + ') || window.__SKILL_BOOT_ERROR__', timeout=args.timeout * 1000)
            boot_ms = (time.perf_counter() - started) * 1000
            fatal = page.evaluate('window.__GAME_TEST__?.fatal || window.__fatal || window.__SKILL_BOOT_ERROR__ || null')
            gate(report, 'boot', 'failed' if fatal else 'passed', {'fatal': fatal, 'bootMs': round(boot_ms, 1)})
            if fatal:
                return
            gpu = page.evaluate(GPU)
            report['gpu'] = gpu
            hardware = bool(gpu.get('webgl')) and bool(gpu.get('identified')) and not args.software and not re.search(
                r'SwiftShader|llvmpipe|Software|softpipe|unknown', gpu['renderer'], re.I)
            gate(report, 'webgl', 'passed' if gpu.get('webgl') else 'failed', gpu)
            gate(report, 'hardware_boot_budget', ('passed' if boot_ms <= budget['bootMsMax'] else 'failed')
                 if hardware else 'unverified', {'bootMs': round(boot_ms, 1), 'max': budget['bootMsMax'],
                                                'hardware': hardware})
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
                gate(report, 'nonblank_' + scene_id, 'passed' if measures['lumaStdDev'] > 2 else 'failed', measures)
            gate(report, 'required_views', 'passed' if set(scenes) >= set(budget['requiredScenes']) else 'unverified', scenes)
            if has_contract:
                audit = page.evaluate('() => window.__GAME_TEST__.audit()')
            else:
                audit = {}
            measured_checks(report, 'resource_', audit, AUDITS)
            if has_contract:
                page.evaluate('(id) => window.__GAME_TEST__.setScene(id)', budget['benchmarkScene'])
            page.wait_for_timeout(budget['warmupSeconds'] * 1000)
            before = page.evaluate(METRICS)
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
            page.wait_for_function('window.__SKILL_SAMPLE__.done', timeout=args.timeout * 1000)
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
            load_ok = (after.get('enemiesAlive', -1) >= budget['benchmarkMinEnemies'] and
                       after.get('effectsActive', -1) >= budget['benchmarkMinEffects'])
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
            for metric, maximum in [('drawCalls', 'drawCallsMax'), ('submittedTriangles', 'submittedTrianglesMax')]:
                actual = after.get(metric)
                valid = isinstance(actual, (int, float)) and math.isfinite(actual) and actual > 0
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
            if budget.get('feedbackRules'):
                feedback = audit_feedback(gameplay.get('feedback', {}), budget['feedbackRules'])
                gate(report, 'action_feedback_submission', feedback['status'], feedback['evidence'])
            if budget.get('stabilityTargets'):
                stability = audit_stability(gameplay.get('stability', {}), budget['stabilityTargets'], report['artifact']['sha256'])
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
                             ['network_audit.py', 'feedback_audit.py', 'stability_audit.py']},
              'budgetSha256': sha(args.budget), 'budget': budget, 'gates': [], 'screenshots': [],
              'releaseStatus': 'unverified', 'visualReview': 'pending'}
    try:
        profile_check(budget, report)
        static_checks(args.html, budget, report)
        if args.static_only:
            gate(report, 'runtime', 'unverified', 'Static-only invocation')
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
