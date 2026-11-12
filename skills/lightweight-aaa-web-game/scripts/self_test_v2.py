"""Synthetic positive/negative regression fixtures for v2 gates, not game QA."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from feedback_audit import audit_feedback
from stability_audit import audit_stability
from experience_audit import audit_experience
from validate_game import SKILL, static_checks, profile_check
from finalize_review import finalize

BUDGET = json.loads((SKILL / 'templates/budgets.json').read_text())


class FeedbackTests(unittest.TestCase):
    def fixture(self):
        shots, renders = [], []
        for i in range(100):
            frame, time = i * 10, i * 160
            shots.append({'id': str(i), 'acceptedAtMs': time, 'acceptedFrame': frame,
                          'expectedFx': ['muzzle', 'tracer']})
            for channel in ['muzzle', 'tracer']:
                for f in [1, 2]:
                    renders.append({'shotId': str(i), 'channel': channel, 'frame': frame + f,
                                    'presentedAtMs': time + f * 16})
        return {'shots': shots, 'renders': renders}

    def status(self, data):
        return audit_feedback(data, BUDGET['feedbackRules'])['status']

    def test_complete_observations(self):
        self.assertEqual(self.status(self.fixture()), 'passed')

    def test_damage_or_ammo_without_render_cannot_pass(self):
        data = self.fixture(); data['renders'] = []
        self.assertEqual(self.status(data), 'failed')

    def test_one_intermittent_missing_tracer_fails(self):
        data = self.fixture(); data['renders'] = [r for r in data['renders'] if not (r['shotId'] == '48' and r['channel'] == 'tracer')]
        result = audit_feedback(data, BUDGET['feedbackRules'])
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['evidence']['missingRate'], 1/200)

    def test_two_passes_same_frame_not_two_visible_frames(self):
        data = self.fixture(); data['renders'][1]['frame'] = data['renders'][0]['frame']
        self.assertEqual(self.status(data), 'failed')

    def test_late_feedback_fails(self):
        data = self.fixture()
        for r in data['renders'][:4]: r['frame'] += 3
        self.assertEqual(self.status(data), 'failed')

    def test_pool_stale_id_fails(self):
        data = self.fixture(); data['renders'][0]['shotId'] = 'previous-session'
        self.assertEqual(self.status(data), 'failed')

    def test_game_cannot_opt_out_of_tracers(self):
        data = self.fixture(); data['shots'][0]['expectedFx'] = ['muzzle']
        self.assertEqual(self.status(data), 'failed')

    def test_absent_observations_unverified(self):
        self.assertEqual(self.status({}), 'unverified')


class StabilityTests(unittest.TestCase):
    def fixture(self):
        resources = dict(geometries=20, textures=8, materials=10, audioNodes=0, listeners=8, activeEffects=0)
        return {'coldStarts': [{'contextId': str(i), 'artifactSha256': 'fixture-sha', 'readyFrame': 3,
                               'runtimeErrors': 0, 'extraNetworkRequests': 0} for i in range(3)],
                'warmedBaseline': resources,
                'restarts': [{'state': 'playing', 'shotsBefore': 0, 'shotsAfter': 1,
                              'settledResources': copy.deepcopy(resources)} for _ in range(5)],
                'soak': {'wallSeconds': 301, 'combatSeconds': 65, 'renderedFrames': 18000,
                         'runtimeErrors': 0, 'extraNetworkRequests': 0},
                'frameCapsTested': [60,30,15], 'effectPoolCapacity': 20, 'poolReuseAcceptedShots': 100}

    def status(self, data):
        return audit_stability(data, BUDGET['stabilityTargets'], 'fixture-sha')['status']

    def test_complete_release_observations(self):
        self.assertEqual(self.status(self.fixture()), 'passed')

    def test_restart_weapon_cooldown_bug_fails(self):
        data = self.fixture(); data['restarts'][2]['shotsAfter'] = 0
        self.assertEqual(self.status(data), 'failed')

    def test_listener_leak_fails(self):
        data = self.fixture(); data['restarts'][4]['settledResources']['listeners'] += 1
        self.assertEqual(self.status(data), 'failed')

    def test_warm_cache_not_independent_cold_start(self):
        data = self.fixture(); data['coldStarts'][1]['contextId'] = '0'
        self.assertEqual(self.status(data), 'failed')

    def test_short_soak_not_promoted(self):
        data = self.fixture(); data['soak']['wallSeconds'] = 10
        self.assertEqual(self.status(data), 'unverified')

    def test_missing_measurements_not_promoted(self):
        self.assertEqual(self.status({}), 'unverified')


class ExperienceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        p = self.root/'observation.txt'; p.write_text('Synthetic unit-test fixture, not a human playtest.')
        self.ref = {'path': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
        self.review = {'artifactSha256': 'test-sha', 'basis': 'agent_playtest', 'normalEntryPlayed': True,
                       'goals': [{'id': 'action_clarity', 'status': 'passed',
                                  'observation': 'Synthetic observation for evidence binding.', 'evidence': [self.ref]}], 'issues': []}

    def tearDown(self): self.tmp.cleanup()

    def result(self):
        return audit_experience(self.review, ['action_clarity'], 'test-sha', self.root)

    def test_valid_review_evidence(self):
        self.assertEqual(self.result(), {'failures': [], 'unverified': []})

    def test_known_open_user_issue_blocks_acceptance(self):
        self.review['issues'] = [{'id': 'shot-disappears', 'priority': 'P1', 'status': 'open'}]
        self.assertTrue(self.result()['failures'])

    def test_code_change_without_before_after_is_not_closed(self):
        self.review['issues'] = [{'id': 'shot-disappears', 'priority': 'P1', 'status': 'closed',
                                 'verifiedArtifactSha256': 'test-sha', 'playerOutcome': 'Claimed fixed without observed evidence.'}]
        self.assertTrue(self.result()['unverified'])

    def test_changed_evidence_rejected(self):
        (self.root/'observation.txt').write_text('Changed after review')
        self.assertTrue(self.result()['failures'])

    def test_old_build_cannot_close_new_build_issue(self):
        self.review['issues'] = [{'id': 'shot', 'priority': 'P1', 'status': 'closed',
                                 'verifiedArtifactSha256': 'old-sha'}]
        self.assertTrue(self.result()['failures'])


class StaticNetworkTests(unittest.TestCase):
    def test_legacy_budget_cannot_silently_claim_v2(self):
        r={'gates':[]}; profile_check({'schemaVersion':1},r)
        self.assertEqual(r['gates'][0]['status'],'unverified')

    def test_complete_v2_budget(self):
        r={'gates':[]}; profile_check(BUDGET,r)
        self.assertEqual(r['gates'][0]['status'],'passed')

    def test_resource_hints_svg_and_source_maps_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)/'game.html'
            p.write_text('<link rel="alternate stylesheet" href="theme.css"><link rel="preconnect" href="https://example.invalid"><svg><image href="x.png"/></svg><script>//# sourceMappingURL=game.js.map\n</script>')
            r = {'gates': []}; static_checks(p, BUDGET, r)
            self.assertEqual(len(r['gates'][-1]['evidence']), 4)
            self.assertEqual(r['gates'][-1]['status'], 'failed')


class FinalReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        artifact = self.root/'game.html'; artifact.write_text('Synthetic acceptance fixture only')
        digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
        self.report = {'artifact': {'path': str(artifact), 'sha256': digest(artifact)},
                       'gates': [{'id': name, 'status': 'passed'} for name in [
                           'validation_profile','boot','offline_resources','action_feedback_submission','stability_contract',
                           'hardware_boot_budget','hardware_frame_budget','no_runtime_errors','gameplay_action']],
                       'budget': {'schemaVersion': 2, 'requiredGameplayChecks': ['action'],
                                  'requiredScenes': [], 'visualScoreMin': 4,
                                  'requiredMotionReviews': ['primary_action']}, 'motionEvidence': []}
        for i in range(3):
            path = self.root/f'frame-{i}.png'; path.write_bytes(f'hash fixture {i}; not a rendered image'.encode())
            self.report['motionEvidence'].append({'id':'primary_action','path':str(path),'sha256':digest(path)})
        self.review = {'reviewer': 'Synthetic unit test only', 'artDirectionMatch': True, 'criticalDefects': [],
                       'motionScenes': [{'id':'primary_action','captureSha256':[x['sha256'] for x in self.report['motionEvidence']],
                                         'visibleFeedback':True,'timingAndContinuity':True,'noBlockingArtifacts':True,
                                         'evidence':'Synthetic fixture tests hash and gate logic, not visual quality.'}]}

    def tearDown(self): self.tmp.cleanup()

    def result(self):
        rp=self.root/'report.json'; rp.write_text(json.dumps(self.report))
        self.review['reportSha256']=hashlib.sha256(rp.read_bytes()).hexdigest()
        vp=self.root/'review.json'; vp.write_text(json.dumps(self.review))
        return finalize(rp,vp)

    def test_complete_binding(self):
        self.assertEqual(self.result()['releaseStatus'],'passed')

    def test_removed_stability_gate_cannot_pass(self):
        self.report['gates']=[g for g in self.report['gates'] if g['id']!='stability_contract']
        self.assertEqual(self.result()['releaseStatus'],'unverified')

    def test_duplicated_static_frame_not_motion_sequence(self):
        self.report['motionEvidence']=[self.report['motionEvidence'][0]]*3
        self.assertEqual(self.result()['releaseStatus'],'unverified')

    def test_changed_motion_file_fails(self):
        Path(self.report['motionEvidence'][0]['path']).write_bytes(b'changed')
        self.assertEqual(self.result()['releaseStatus'],'failed')

    def test_missing_player_experience_cannot_pass(self):
        self.report['budget']['requiredExperienceGoals']=['action_clarity']
        self.assertEqual(self.result()['releaseStatus'],'unverified')


if __name__ == '__main__': unittest.main(verbosity=2)
