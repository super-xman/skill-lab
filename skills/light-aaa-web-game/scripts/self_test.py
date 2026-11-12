#!/usr/bin/env python3
"""Regression tests for acceptance logic, not game quality."""
import json
import tempfile
import unittest
from pathlib import Path
from validate_game import aggregate, measured_checks, static_checks, sha, SKILL
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


if __name__ == '__main__':
    unittest.main(verbosity=2)
