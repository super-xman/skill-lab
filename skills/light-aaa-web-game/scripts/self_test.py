#!/usr/bin/env python3
"""Regression tests for acceptance logic, not game quality."""
import json
import tempfile
import unittest
from pathlib import Path
from validate_game import aggregate, benchmark_load, measured_checks, profile_check, static_checks, sha, SKILL
from feedback_audit import audit_feedback
from stability_audit import audit_stability
from finalize_review import finalize


class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.budget = json.loads((SKILL / 'templates/budgets.json').read_text())

    def tearDown(self):
        self.temp.cleanup()

    def inspect(self, html, **limits):
        path = self.root / 'game.html'
        path.write_text(html)
        report = {'gates': []}
        static_checks(path, self.budget | limits, report)
        return report

    def test_single_file_size_measured(self):
        report = self.inspect('<html><script>const x=1;</script></html>')
        self.assertEqual(aggregate(report['gates']), 'passed')
        self.assertEqual(report['artifact']['rawBytes'], (self.root/'game.html').stat().st_size)

    def test_external_script_and_css_rejected(self):
        report = self.inspect('<script src="https://example.invalid/x.js"></script><style>@import "x.css";</style>')
        self.assertEqual(report['gates'][-1]['status'], 'failed')
        self.assertEqual(len(report['gates'][-1]['evidence']), 2)

    def test_budget_rejects_real_bytes(self):
        report = self.inspect('<html>你好</html>', rawBytesMax=1)
        self.assertEqual(report['gates'][0]['status'], 'failed')

    def test_missing_evidence_is_unverified(self):
        report = {'gates': []}
        measured_checks(report, '', {'checks':[{'id':'geometry','status':'passed'}]}, ['geometry','audio'])
        self.assertTrue(all(g['status']=='unverified' for g in report['gates']))

    def fixture_review(self, status='passed'):
        html = self.root/'game.html'; html.write_text('<html>fixture</html>')
        shot = self.root/'shot.png'; shot.write_bytes(b'test-only-hash-fixture')
        report = {'artifact':{'path':str(html),'sha256':sha(html)},
          'gates':[{'id':'hardware_frame_budget','status':status}],
          'budget':{'requiredScenes':['overview'],'visualScoreMin':4},
          'screenshots':[{'id':'overview','path':str(shot),'sha256':sha(shot)}]}
        rp = self.root/'report.json'; rp.write_text(json.dumps(report))
        review = {'reportSha256':sha(rp),'reviewer':'Unit test only; not a real visual review',
          'artDirectionMatch':True,'criticalDefects':[], 'scenes':[{'id':'overview',
          'screenshotSha256':sha(shot),'evidence':'Unit-test fixture verifies hash binding only.',
          'scores':dict.fromkeys(['composition','materials','lighting','readability','artifactFree'],4)}]}
        vp = self.root/'review.json'; vp.write_text(json.dumps(review))
        return rp, vp, html, shot

    def test_matching_review_passes_and_changed_game_fails(self):
        rp,vp,html,_ = self.fixture_review()
        self.assertEqual(finalize(rp,vp)['releaseStatus'],'passed')
        html.write_text('changed')
        self.assertEqual(finalize(rp,vp)['releaseStatus'],'failed')

    def test_changed_screenshot_fails(self):
        rp,vp,_,shot = self.fixture_review()
        shot.write_bytes(b'changed')
        self.assertEqual(finalize(rp,vp)['releaseStatus'],'failed')

    def test_unverified_performance_cannot_be_promoted(self):
        rp,vp,_,_ = self.fixture_review('unverified')
        self.assertEqual(finalize(rp,vp)['releaseStatus'],'unverified')


class GameplayContractTests(unittest.TestCase):
    def setUp(self):
        self.budget = json.loads((SKILL / 'templates/budgets.json').read_text())

    def test_puzzle_action_needs_actual_rendered_orientation(self):
        rules = self.budget['feedbackRules'] | {'requiredChannels': ['orientation']}
        actions, renders = [], []
        for turn in range(rules['minAcceptedActions']):
            action_id = f'rotate-{turn}'
            frame = turn * 5
            actions.append({'id': action_id, 'acceptedAtMs': frame * 16, 'acceptedFrame': frame,
                            'expectedChannels': ['orientation']})
            for displayed in [frame + 1, frame + 2]:
                renders.append({'actionId': action_id, 'channel': 'orientation', 'frame': displayed,
                                'presentedAtMs': displayed * 16})
        evidence = {'actions': actions, 'renders': renders}
        self.assertEqual(audit_feedback(evidence, rules)['status'], 'passed')
        renders.pop()
        result = audit_feedback(evidence, rules)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['evidence']['missingPairs'][0]['actionId'], actions[-1]['id'])

    def test_racing_load_uses_track_counters(self):
        self.budget['benchmarkLoad'] = {'visibleTrackSections': 8, 'activeKarts': 4}
        load = {'visibleTrackSections': 8, 'activeKarts': 4}
        self.assertTrue(benchmark_load(self.budget, {'workload': load})[0])
        self.assertFalse(benchmark_load(self.budget, {'workload': load | {'activeKarts': 2}})[0])
        self.assertFalse(benchmark_load(self.budget, {'enemiesAlive': 8, 'effectsActive': 5})[0])

    def test_legacy_shooter_load_still_uses_its_own_thresholds(self):
        legacy = {'schemaVersion': 2, 'benchmarkMinEnemies': 3, 'benchmarkMinEffects': 1}
        self.assertTrue(benchmark_load(legacy, {'enemiesAlive': 3, 'effectsActive': 1})[0])
        self.assertFalse(benchmark_load(legacy, {'enemiesAlive': 1, 'effectsActive': 1})[0])

    def test_empty_load_or_feedback_never_certifies_a_game(self):
        report = {'gates': []}
        profile_check(self.budget, report)
        self.assertEqual(report['gates'][0]['status'], 'passed')
        self.budget['feedbackRules']['requiredChannels'] = []
        self.budget['benchmarkLoad'] = {}
        profile_check(self.budget, report)
        self.assertEqual(report['gates'][1]['status'], 'unverified')
        self.assertEqual(audit_feedback({}, self.budget['feedbackRules'])['status'], 'unverified')

    def test_recovery_and_active_play_without_an_effect_pool(self):
        targets = self.budget['stabilityTargets']
        counts = dict(geometries=8, textures=0, materials=1, audioNodes=0, listeners=2, activeEffects=0)
        observations = {
            'coldStarts': [{'contextId': str(i), 'artifactSha256': 'fixture', 'readyFrame': 1,
                            'runtimeErrors': 0, 'extraNetworkRequests': 0}
                           for i in range(targets['independentColdStarts'])],
            'warmedBaseline': counts,
            'restarts': [{'state': 'playing', 'actionsBefore': 2, 'actionsAfter': 3,
                          'settledResources': counts} for _ in range(targets['restartCycles'])],
            'soak': {'wallSeconds': 300, 'activePlaySeconds': 60, 'renderedFrames': 12000,
                     'runtimeErrors': 0, 'extraNetworkRequests': 0},
            'frameCapsTested': [60, 30, 15]}
        def status():
            return audit_stability(observations, targets, 'fixture')['status']
        self.assertEqual(status(), 'passed')
        observations['restarts'][0]['actionsAfter'] = 2
        self.assertEqual(status(), 'failed')
        observations['restarts'][0]['actionsAfter'] = 3
        targets['effectPoolReuseFactor'] = 3
        self.assertEqual(status(), 'unverified')
        observations.update(effectPoolCapacity=4, poolReuseActions=12)
        self.assertEqual(status(), 'passed')


if __name__ == '__main__':
    unittest.main(verbosity=2)
