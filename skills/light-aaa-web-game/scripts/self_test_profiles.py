#!/usr/bin/env python3
"""Regression tests for project-defined observations and browser profiles."""
import argparse
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from response_audit import audit_response
from validate_game import SKILL, profile_check


def template():
    return json.loads((SKILL / 'templates/budgets.json').read_text())


class ResponseTests(unittest.TestCase):
    def setUp(self):
        self.rules = {'minAcceptedActions': 2, 'channels': {
            'tone': {'source': 'audio', 'expected': {'low': 320, 'high': 640}, 'tolerance': 8, 'maxDelayMs': 80},
            'label': {'source': 'visual', 'expected': {'low': 'A'}, 'maxDelayMs': 80, 'holdMs': 40}}}
        self.trace = {'actions': [{'id': 'a', 'condition': 'low', 'acceptedAtMs': 0},
                                  {'id': 'b', 'condition': 'high', 'acceptedAtMs': 100}],
                      'observations': [
                          {'actionId': 'a', 'channel': 'tone', 'source': 'audio', 'atMs': 10, 'value': 316},
                          {'actionId': 'b', 'channel': 'tone', 'source': 'audio', 'atMs': 115, 'value': 636},
                          {'actionId': 'a', 'channel': 'label', 'source': 'visual', 'atMs': 12, 'value': 'A'},
                          {'actionId': 'a', 'channel': 'label', 'source': 'visual', 'atMs': 60, 'value': 'A'}]}

    def status(self):
        return audit_response(self.trace, self.rules)['status']

    def test_sources_conditions_latency_and_retention(self):
        self.assertEqual(self.status(), 'passed')
        for update in ({'value': 316}, {'source': 'visual'}, {'atMs': 200}, {'atMs': 99}, {'value': True}):
            with self.subTest(update=update):
                trace = copy.deepcopy(self.trace)
                trace['observations'][1].update(update)
                self.assertEqual(audit_response(trace, self.rules)['status'], 'failed')
        self.trace['observations'].pop()
        self.assertEqual(self.status(), 'unverified')
        self.trace['observations'].append({'actionId': 'a', 'channel': 'label', 'source': 'visual',
                                          'atMs': 56, 'value': 'wrong'})
        self.assertEqual(self.status(), 'failed')

    def test_unexercised_condition_and_accepted_but_missing_output(self):
        self.trace['observations'].pop(1)
        self.assertEqual(self.status(), 'failed')
        self.trace['actions'].pop()
        self.assertEqual(self.status(), 'unverified')

    def test_latency_starts_at_input_and_ends_at_first_correct_output(self):
        pending = dict(self.trace['observations'][2], atMs=5, value='pending')
        self.trace['observations'].append(pending)
        self.trace['observations'].append(dict(pending, atMs=95, value='next phase'))
        result = audit_response(self.trace, self.rules)
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['evidence']['maxDelayMs']['label'], 12)

    def test_later_move_cannot_confirm_an_earlier_shared_display(self):
        self.rules['channels']['label']['expected']['high'] = 'B'
        self.trace['observations'][-1]['atMs'] = 210
        self.trace['observations'].extend([{'actionId': 'b', 'channel': 'label', 'source': 'visual',
                                            'atMs': t, 'value': 'B'} for t in (115, 164)])
        self.assertEqual(self.status(), 'unverified')
        self.rules['channels']['label']['scope'] = 'per-action'
        self.assertEqual(self.status(), 'passed')

    def test_profile_rejects_typos_and_unmeasurable_rules(self):
        budget = template()
        def status():
            report = {'gates': []}
            profile_check(budget, report)
            return report['gates'][0]['status']
        self.assertEqual(status(), 'passed')
        budget['renderMode'] = 'unknown'
        self.assertEqual(status(), 'unverified')
        budget['renderMode'] = 'on-demand'
        budget['feedbackRules']['channels']['result']['maxDelayMs'] = -1
        self.assertEqual(status(), 'unverified')


# The project game has no frame loop. Only real button activations change the display and play a tone.
PAGE = """<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" href="data:,"><title>Signal</title>
<main data-game-root>SURFACE <button id="low">A</button> <button id="high">B</button></main>
<script>
const actions = [], buffers = {};
let audio;
const originalContext = HTMLCanvasElement.prototype.getContext;
HTMLCanvasElement.prototype.getContext = function(type, ...args) {
  if (type.startsWith('webgl')) throw new Error('No WebGL adapter on this test device');
  return originalContext.call(this, type, ...args);
};
for (const button of document.querySelectorAll('button')) {
  button.onclick = () => {
    const id = 'action-' + actions.length;
    actions.push({id, condition:button.id, acceptedAtMs:performance.now()});
    document.querySelector('#result').textContent = button.textContent;
    audio ??= new AudioContext();
    const hz = button.id === 'low' ? 320 : SECOND_TONE;
    const buffer = audio.createBuffer(1, 2000, 8000);
    const samples = buffer.getChannelData(0);
    for (let i = 0; i < samples.length; i++) samples[i] = 0.2 * Math.sin(2 * Math.PI * hz * i / 8000);
    const player = audio.createBufferSource();
    player.buffer = buffer;
    player.connect(audio.destination);
    player.start();
    buffers[id] = player.buffer;
  };
}
if (location.search.includes('test=1')) window.__GAME_TEST__ = {
  ready:true, setScene() {}, metrics:() => ({sceneId:'choice', workload:{buttons:document.querySelectorAll('button').length}}),
  audit:() => ({checks:[]}), actions, buffers
};
</script>"""


def run(page, artifacts_dir):
    # Read the rendered label and the PCM actually handed to playback, independently of the expected budget.
    observations = []
    probe = page.locator('main').get_attribute('data-input-probe')
    if probe == 'drift':
        emulation = page.context.new_cdp_session(page)
        screen = {'width': 390, 'height': 844, 'mobile': True}
        emulation.send('Emulation.setDeviceMetricsOverride', dict(screen, deviceScaleFactor=1))
    for name in ('A', 'B'):
        button = page.get_by_role('button', name=name)
        if probe == 'mouse':
            button.click()
        else:
            button.tap()
        observations.extend(page.evaluate("""() => {
          const game = window.__GAME_TEST__, action = game.actions.at(-1);
          const buffer = game.buffers[action.id], pcm = buffer.getChannelData(0);
          let crossings = 0;
          for (let i=1; i<pcm.length; i++) if (pcm[i]>=0 && pcm[i-1]<0) crossings++;
          const atMs = performance.now();
          return [{actionId:action.id, channel:'tone', source:'audio', atMs,
                   value:crossings*buffer.sampleRate/pcm.length},
                  {actionId:action.id, channel:'label', source:'visual', atMs,
                   value:document.querySelector('#result').textContent}];
        }"""))
        page.wait_for_timeout(55)
        observations.append(page.evaluate("""() => ({
          actionId:window.__GAME_TEST__.actions.at(-1).id, channel:'label', source:'visual',
          atMs:performance.now(), value:document.querySelector('#result').textContent})"""))
    actions = page.evaluate('window.__GAME_TEST__.actions')
    actual = page.locator('#result').text_content()
    if probe == 'drift':
        emulation.send('Emulation.setDeviceMetricsOverride', dict(screen, deviceScaleFactor=2))
    return {'checks': [{'id': 'choose', 'status': 'passed' if actual == 'B' else 'failed',
                         'evidence': {'lastLabel': actual}}],
            'feedback': {'actions': actions, 'observations': observations}}


class BrowserProfiles(unittest.TestCase):
    executable = None

    def test_touch_dom_svg_and_audible_difference(self):
        cases = [('dom', 640, 'touch', 'passed', 'passed'), ('svg', 640, 'touch', 'passed', 'passed'),
                 ('dom', 320, 'touch', 'failed', 'passed'), ('dom', 640, 'drift', 'passed', 'failed'),
                 ('dom', 640, 'mouse', 'passed', 'unverified')]
        for backend, pitch, probe, response_status, input_status in cases:
            with self.subTest(backend=backend, pitch=pitch, probe=probe), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                surface = ('<svg data-game-root width="120" height="60"><text x="10" y="40" id="result">–</text></svg>'
                           if backend == 'svg' else '<output id="result">–</output>')
                html = root / 'game.html'
                html.write_text(PAGE.replace('SURFACE', surface).replace('SECOND_TONE', str(pitch))
                                .replace('<main data-game-root>', f'<main data-game-root data-input-probe="{probe}">'))
                budget = template()
                budget.update(renderBackend=backend, renderMode='on-demand', viewport={'width': 390, 'height': 844},
                              device={'inputMethods': ['touch'], 'isMobile': True, 'deviceScaleFactor': 2},
                              requiredScenes=['choice'], benchmarkScene='choice', benchmarkLoad={'buttons': 2},
                              requiredResourceChecks=[], requiredGameplayChecks=['choose'], warmupSeconds=0,
                              requiredMotionReviews=[], visualDimensions=['typography'])
                budget['feedbackRules'] = {'minAcceptedActions': 2, 'channels': {
                    'tone': {'source': 'audio', 'expected': {'low': 320, 'high': 640}, 'tolerance': 8, 'maxDelayMs': 1000},
                    'label': {'source': 'visual', 'expected': {'low': 'A', 'high': 'B'}, 'maxDelayMs': 1000, 'holdMs': 40}}}
                profile = root / 'budget.json'
                profile.write_text(json.dumps(budget))
                command = [sys.executable, '-B', str(SKILL / 'scripts/validate_game.py'), str(html), '--budget',
                           str(profile), '--scenario-script', __file__, '--out', str(root)]
                if self.executable:
                    command += ['--browser', self.executable]
                completed = subprocess.run(command, capture_output=True, text=True, timeout=60)
                report = json.loads((root / 'report.json').read_text())
                gates = {g['id']: g for g in report['gates']}
                for gate in ('validation_profile', 'render_backend', 'gameplay_choose',
                             'representative_load', 'offline_resources', 'no_runtime_errors'):
                    self.assertIn(gate, gates, {key: val['evidence'] for key, val in gates.items()
                                                if val['status'] == 'failed'})
                    self.assertEqual(gates[gate]['status'], 'passed', gates)
                self.assertEqual(gates['action_response']['status'], response_status, gates['action_response'])
                self.assertEqual(gates['player_input']['status'], input_status, gates['player_input'])
                if probe == 'drift':
                    device = gates['player_input']['evidence']
                    self.assertEqual((device['start']['dpr'], device['end']['dpr']), (2, 2))
                    self.assertIn(1, [s['dpr'] for s in device['atInput']])
                self.assertEqual(report['device']['dpr'], 2)
                self.assertGreater(report['device']['touchPoints'], 0)
                self.assertNotIn('render_advances', gates)
                self.assertNotIn('hardware_frame_budget', gates)
                # The short input fixture deliberately submits no endurance evidence.
                self.assertEqual(gates['stability_contract']['status'], 'unverified')
                self.assertEqual(completed.returncode, 2 if 'failed' in (input_status, response_status) else 3)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--browser')
    args, remaining = parser.parse_known_args()
    BrowserProfiles.executable = args.browser
    unittest.main(argv=[sys.argv[0], *remaining], verbosity=2)
