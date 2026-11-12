#!/usr/bin/env python3
"""Bind a manually inspected visual review to exact automated evidence."""
import argparse
import hashlib
import json
from pathlib import Path
from experience_audit import audit_experience


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finalize(report_path, review_path):
    report_path, review_path = Path(report_path).resolve(), Path(review_path).resolve()
    report = json.loads(report_path.read_text())
    review = json.loads(review_path.read_text())
    failures = []
    unverified = []
    if review.get('reportSha256') != digest(report_path):
        failures.append('Review does not match report SHA-256')
    artifact = report.get('artifact', {})
    try:
        if digest(artifact['path']) != artifact['sha256']:
            failures.append('Game artifact changed after validation')
    except (KeyError, OSError):
        failures.append('Game artifact cannot be verified')
    gates = report.get('gates', [])
    if not gates:
        unverified.append('No automated evidence')
    for check in gates:
        if check.get('status') == 'failed':
            failures.append('Automated gate: ' + check['id'])
        elif check.get('status') != 'passed':
            unverified.append('Automated gate: ' + check['id'])
    if report['budget'].get('schemaVersion', 1) >= 2:
        required = {'validation_profile', 'boot', 'offline_resources', 'action_feedback_submission', 'stability_contract',
                    'hardware_boot_budget', 'hardware_frame_budget', 'no_runtime_errors'}
        required.update('gameplay_' + name for name in report['budget']['requiredGameplayChecks'])
        missing = required - {g['id'] for g in gates}
        unverified.extend('Missing required gate: ' + name for name in sorted(missing))
    if not review.get('reviewer') or review['reviewer'].startswith('REPLACE'):
        unverified.append('Missing actual reviewer / image viewing method')
    if review.get('artDirectionMatch') is not True:
        failures.append('Art direction not confirmed')
    if review.get('criticalDefects'):
        failures.append('Critical visual defects remain')
    shots = {s['id']: s for s in report.get('screenshots', [])}
    reviews = {s['id']: s for s in review.get('scenes', [])}
    for scene in report['budget']['requiredScenes']:
        shot, item = shots.get(scene), reviews.get(scene)
        if not shot or not item:
            unverified.append('Missing view or review: ' + scene)
            continue
        try:
            if digest(shot['path']) != shot['sha256'] or item.get('screenshotSha256') != shot['sha256']:
                failures.append('Screenshot hash mismatch: ' + scene)
        except OSError:
            failures.append('Screenshot missing: ' + scene)
        evidence = item.get('evidence', '').strip()
        if len(evidence) < 12 or evidence.startswith(('Describe visible', 'REPLACE')):
            unverified.append('Missing specific visual evidence: ' + scene)
        for dimension in ['composition', 'materials', 'lighting', 'readability', 'artifactFree']:
            score = item.get('scores', {}).get(dimension)
            if type(score) not in [int, float] or not report['budget']['visualScoreMin'] <= score <= 5:
                failures.append(f'Visual score below target: {scene}/{dimension}')
    for scene in report['budget'].get('requiredMotionReviews', []):
        captures = [c for c in report.get('motionEvidence', []) if c.get('id') == scene]
        item = next((s for s in review.get('motionScenes', []) if s.get('id') == scene), {})
        video = any(Path(c['path']).suffix.lower() in ['.webm', '.mp4'] for c in captures)
        distinct_frames = len({c['sha256'] for c in captures})
        if not captures or (not video and distinct_frames < 3):
            unverified.append('Missing video or frame sequence: ' + scene)
            continue
        hashes = item.get('captureSha256', [])
        for capture in captures:
            try:
                if digest(capture['path']) != capture['sha256'] or capture['sha256'] not in hashes:
                    failures.append('Motion evidence hash mismatch: ' + scene)
            except OSError:
                failures.append('Motion evidence missing: ' + scene)
        if len(item.get('evidence', '').strip()) < 12:
            unverified.append('Missing actual motion review: ' + scene)
        for condition in ['visibleFeedback', 'timingAndContinuity', 'noBlockingArtifacts']:
            if item.get(condition) is not True:
                failures.append('Motion review not passed: ' + scene + '/' + condition)
    if report['budget'].get('requiredExperienceGoals'):
        experience = audit_experience(review.get('experience', {}), report['budget']['requiredExperienceGoals'],
                                      artifact.get('sha256'), report_path.parent)
        failures.extend(experience['failures'])
        unverified.extend(experience['unverified'])
    status = 'failed' if failures else 'unverified' if unverified else 'passed'
    result = {'schemaVersion': 1, 'releaseStatus': status, 'reportSha256': digest(report_path),
              'reviewSha256': digest(review_path), 'failures': failures, 'unverified': unverified}
    output = report_path.with_name('final-review.json')
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('review', type=Path)
    args = parser.parse_args()
    try:
        result = finalize(args.report, args.review)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'releaseStatus': 'failed', 'error': str(exc)}))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return {'passed': 0, 'failed': 2, 'unverified': 3}[result['releaseStatus']]


if __name__ == '__main__':
    raise SystemExit(main())
