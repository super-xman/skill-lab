#!/usr/bin/env python3
"""Exercise scene jumps and detect wrong output in a small playable browser fixture."""
import argparse
import json
import math
import struct
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from urllib.parse import parse_qs

from finalize_review import finalize
from scene_checks import assertion_gates, planned_cases
from scene_probes import hit_target, record_mix
from validate_game import SKILL


PAGE = """<!doctype html><html lang="zh"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><link rel="icon" href="data:,">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:">
<style>button{min-width:6em;height:3em} #pause{position:relative;width:max-content}
#block{position:absolute;inset:0;background:silver} [hidden]{display:none}</style>
<main id="game" tabindex="0"><button id="sound">开启声音</button><button id="mute">静音</button>
<button id="bell">呼叫渡船</button><p id="position"></p>
<div id="pause" hidden><button id="resume">继续</button><span id="block" hidden>遮挡</span></div></main>
<script type="module">
DIAGNOSTICS
const byId = id => document.getElementById(id);
const defect = 'FAULT', floorNames = ['雪地', '木板'];
let current = 'title', position = 0, steps = 0, audio, output, timer = null, muted = false;
function paint() {
  byId('position').textContent = floorNames[Number(position >= 3)] + ' ' + position;
  byId('pause').hidden = current !== 'pause-long';
  byId('block').hidden = defect !== 'ui';
}
function play(hz) {
  if (!audio) return;
  const voice = audio.createOscillator(), env = audio.createGain(), now = audio.currentTime;
  voice.frequency.value = hz;
  env.gain.setValueAtTime(0.14, now);
  env.gain.exponentialRampToValueAtTime(0.0001, now + 0.17);
  voice.connect(env).connect(output);
  voice.onended = () => { voice.disconnect(); env.disconnect(); };
  voice.start(now);
  voice.stop(now + 0.18);
}
function stop() { clearInterval(timer); timer = null; }
function move() {
  position++;
  steps++;
  play(position < 3 || defect === 'steps' ? 330 : 880);
  paint();
  if (position >= 8) { current = 'pause-long'; stop(); paint(); }
}
byId('sound').onclick = async () => {
  if (!audio) { audio = new AudioContext(); output = audio.createGain(); output.connect(audio.destination); }
  await audio.resume();
  byId('sound').textContent = '已开启';
};
byId('mute').onclick = () => { muted = !muted; output.gain.value = muted && defect !== 'audio' ? 0 : 1; };
byId('bell').onclick = () => play(660);
byId('resume').onclick = () => { current = 'walk'; paint(); byId('game').focus(); };
addEventListener('keydown', e => {
  if (e.code === 'ArrowRight' && current !== 'pause-long' && timer === null) {
    move(); timer = setInterval(move, 260);
  }
});
addEventListener('keyup', e => { if (e.code === 'ArrowRight') stop(); });
const game = {
  get isPlayable() { return true; }, renderMode: 'on-demand', renderBackend: 'dom',
  testScenes: {
    get current() { return current; },
    async select(id) {
      if (!['signal-deck','surface-walk','pause-long'].includes(id)) throw Error('Unknown scene ' + id);
      await new Promise(resolve => setTimeout(resolve, 15));
      current = id; stop(); position = id === 'pause-long' ? 8 : 0; steps = 0; paint();
    },
    measureWorkload() { return {}; }
  },
  snapshotForTests() { return {steps, position}; }
};
paint();
installGameDiagnostics(game);
if (window.__GAME_TEST__) window.__GAME_TEST__.audioOutput = () => output;
</script></html>"""


GROUPS = {
    'audio': [{'scene': 'signal-deck', 'checks': ['bell_audible', 'mute_at_output']}],
    'footsteps': [{'scene': 'surface-walk', 'checks': ['surface_change', 'quiet_at_rest']}],
    'ui': [{'scene': 'pause-long', 'checks': ['resume_reachable', 'focus_restored']}],
}


def measure_recording(path):
    """Peak and tone from the first non-silent part of this controlled tone fixture."""
    with wave.open(str(path), 'rb') as wav:
        frames = wav.readframes(wav.getnframes())
        samples = struct.unpack(f'<{len(frames) // 2}h', frames)[::wav.getnchannels()]
        rate = wav.getframerate()
    start = next((i for i, sample in enumerate(samples) if abs(sample) > 150), None)
    if start is None:
        return {'peak': max(map(abs, samples), default=0) / 32768, 'hz': 0}
    part = samples[start:start + round(rate * .045)]
    crossings = sum(a <= 0 < b for a, b in zip(part, part[1:]))
    return {'peak': max(map(abs, samples)) / 32768, 'hz': round(crossings * rate / len(part))}


def run_focused(page, focus, scene, artifacts_dir):
    observations, captures = {}, []

    def wav(name, action=None):
        filename = name + '.wav'
        with record_mix(page, artifacts_dir / filename):
            page.wait_for_timeout(180)
            if action:
                action()
            page.wait_for_timeout(420)
        captures.append(filename)
        return measure_recording(artifacts_dir / filename)

    def step():
        page.keyboard.down('ArrowRight')
        page.wait_for_timeout(55)
        page.keyboard.up('ArrowRight')

    if focus in ('audio', 'footsteps'):
        page.get_by_role('button', name='开启声音').click()
        page.get_by_role('button', name='已开启').wait_for()
    if focus == 'audio':
        bell = page.get_by_role('button', name='呼叫渡船')
        active = wav('bell', bell.click)
        page.get_by_role('button', name='静音').click()
        quiet = wav('muted', bell.click)
        observations['bell_audible'] = {'actual': active['peak'], 'expected': .025, 'op': 'gte'}
        observations['mute_at_output'] = {'actual': quiet['peak'], 'expected': .004, 'op': 'lte'}
    elif focus == 'footsteps':
        readings = [wav(f'step-{i}', step) for i in range(4)]
        frequencies = [r['hz'] for r in readings]
        # The controlled fixture promises two specific, repeatable tones.
        correct = all(math.isclose(f, hz, abs_tol=65) for f, hz in zip(frequencies, [330, 330, 880, 880]))
        observations['surface_change'] = {'actual': correct, 'expected': True, 'frequenciesHz': frequencies}
        observations['quiet_at_rest'] = {'actual': wav('rest')['peak'], 'expected': .004, 'op': 'lte'}
    elif focus == 'ui':
        resume = page.get_by_role('button', name='继续')
        hit = hit_target(resume)
        observations['resume_reachable'] = {'actual': hit['insideViewport'] and hit['receivesCenter'],
                                            'expected': True, 'target': hit}
        page.screenshot(path=str(artifacts_dir / 'pause.png'))
        captures.append('pause.png')
        r = hit['rect']
        page.mouse.click(r['x'] + r['width'] / 2, r['y'] + r['height'] / 2)
        focused = page.evaluate('document.activeElement.id')
        closed = not page.locator('#pause').is_visible()
        observations['focus_restored'] = {'actual': closed and focused == 'game', 'expected': True,
                                         'overlayClosed': closed, 'focusedElement': focused}
    return {'observations': observations, 'captures': captures}


class SceneChecks(unittest.TestCase):
    browser = None

    def test_rejects_incomplete_or_ambiguous_selections(self):
        for config, requested in ((GROUPS, ['typo']), ({'ui': []}, ['ui']),
                                  ({'ui': GROUPS['ui'] * 2}, ['ui'])):
            with self.assertRaises(ValueError):
                planned_cases(config, requested)
        self.assertEqual(assertion_gates({'observations': {}}, ['mute'])[0]['status'], 'unverified')

    def test_manual_scene_url_and_normal_entry(self):
        from playwright.sync_api import sync_playwright
        from validate_game import wait_for_observation
        with tempfile.TemporaryDirectory() as temp, sync_playwright() as pw:
            html = Path(temp) / 'game.html'
            html.write_text(PAGE.replace('DIAGNOSTICS', (SKILL / 'templates/diagnostics.js').read_text())
                            .replace('FAULT', 'none'))
            browser = pw.chromium.launch(executable_path=self.browser)
            page = browser.new_page()
            page.goto(html.as_uri() + '?scene=pause-long')
            self.assertIsNone(page.evaluate('window.__GAME_TEST__'))
            self.assertFalse(page.locator('#pause').is_visible())
            page.goto(html.as_uri() + '?test=1&scene=pause-long')
            page.locator('#resume').wait_for()
            self.assertTrue(page.evaluate('window.__GAME_TEST__.ready'))
            self.assertEqual(page.evaluate('window.__GAME_TEST__.metrics().sceneId'), 'pause-long')
            page.goto(html.as_uri() + '?test=1&scene=unknown')
            wait_for_observation(page, 'window.__GAME_TEST__?.fatal', 3)
            self.assertIn('Unknown scene', page.evaluate('window.__GAME_TEST__.fatal'))
            browser.close()

    def test_real_mix_surface_and_covered_control(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            template = (SKILL / 'templates/diagnostics.js').read_text()
            profile = {'focusedChecks': GROUPS, 'seed': 4207, 'quality': 'medium',
                       'viewport': {'width': 390, 'height': 680}}
            (root / 'budget.json').write_text(json.dumps(profile))
            for fault, groups in [('none', list(GROUPS)), ('audio', ['audio']),
                                  ('steps', ['footsteps']), ('ui', ['ui'])]:
                html = root / 'game.html'
                html.write_text(PAGE.replace('DIAGNOSTICS', template).replace('FAULT', fault))
                command = [sys.executable, str(SKILL / 'scripts/validate_game.py'), str(html),
                           '--budget', str(root / 'budget.json'), '--scenario-script', __file__,
                           '--out', str(root / 'artifacts'), '--timeout', '10']
                if self.browser:
                    command.extend(['--browser', self.browser])
                for group in groups:
                    command.extend(['--focus', group])
                process = subprocess.run(command, capture_output=True, text=True, timeout=80)
                report = json.loads((root / 'artifacts/focused/focused-report.json').read_text())
                self.assertEqual(process.returncode, 0 if fault == 'none' else 2, report)
                self.assertEqual(report['releaseStatus'], 'unverified')
                with self.assertRaisesRegex(ValueError, 'focused'):
                    finalize(root / 'artifacts/focused/focused-report.json', root / 'unused.json')
                self.assertFalse((root / 'artifacts/report.json').exists())
                self.assertEqual([c['focus'] for c in report['cases']], groups)
                for case in report['cases']:
                    self.assertEqual(case['observedScene'], case['scene'])
                    self.assertEqual(parse_qs(case['query'])['scene'], [case['scene']])
                    checks = {item['id']: item for item in case['checks']}
                    self.assertEqual(checks['offline_resources']['status'], 'passed', checks)
                    self.assertTrue(all(Path(f['path']).is_file() for f in case['captures']))
                    if fault != 'none':
                        failed = {g['id'] for g in case['checks'] if g['status'] == 'failed'}
                        self.assertEqual(failed, {'audio': {'mute_at_output'}, 'steps': {'surface_change'},
                                                 'ui': {'resume_reachable', 'focus_restored'}}[fault], case)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--browser')
    args, remaining = parser.parse_known_args()
    SceneChecks.browser = args.browser
    unittest.main(argv=[sys.argv[0], *remaining], verbosity=2)
