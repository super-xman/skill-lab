"""Check experience-review completeness and the evidence needed to close issues."""
import hashlib
from pathlib import Path


def audit_experience(review, rules, artifact_sha, root):
    failures, gaps = [], []
    if review.get('artifactSha256') != artifact_sha:
        gaps.append('Experience review is not bound to this game artifact')
    if review.get('basis') not in ['agent_playtest', 'user_feedback', 'mixed']:
        gaps.append('Missing experience-review source')
    if review.get('normalEntryPlayed') is not True:
        gaps.append('Normal player entry has not been reviewed')
    def evidence(items, label):
        if not isinstance(items, list) or not items:
            gaps.append('Missing experience evidence: ' + label)
            return
        for item in items:
            try:
                path = Path(root) / item['path']
                if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
                    failures.append('Experience evidence hash mismatch: ' + label)
            except (OSError, KeyError, TypeError):
                failures.append('Experience evidence cannot be verified: ' + label)
    goals = {item.get('id'): item for item in review.get('goals', [])}
    for name in rules:
        item = goals.get(name, {})
        if item.get('status') == 'failed':
            failures.append('Player experience below target: ' + name)
        elif item.get('status') != 'passed':
            gaps.append('Player experience not reviewed: ' + name)
        if len(item.get('observation', '').strip()) < 12:
            gaps.append('Missing concrete player observation: ' + name)
        evidence(item.get('evidence'), name)
    for item in review.get('issues', []):
        name = item.get('id', 'unnamed')
        if item.get('priority') in ['P0', 'P1'] and item.get('status') != 'closed':
            failures.append('Open core-experience issue: ' + name)
        if item.get('status') == 'closed':
            if item.get('verifiedArtifactSha256') != artifact_sha:
                failures.append('Issue closure uses another game build: ' + name)
            if len(item.get('playerOutcome', '').strip()) < 12:
                gaps.append('Missing observed outcome after fix: ' + name)
            for phase in ['beforeEvidence', 'afterEvidence', 'regressionEvidence']:
                evidence(item.get(phase), name + '/' + phase)
    return {'failures': failures, 'unverified': gaps}
