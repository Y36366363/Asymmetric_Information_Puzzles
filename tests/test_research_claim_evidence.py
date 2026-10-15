from copy import deepcopy
from hashlib import sha256
import json

import pytest

from scripts.audit_research_claims import DEFAULT_INDEX, audit_claims


def _fixture(tmp_path):
    artifact = tmp_path / 'failed.json'
    artifact.write_text('{"passed": false, "runtime_allowed": false}\n')
    index = {
        'schema_version': 'aip-claim-evidence-v1',
        'claims': [{
            'id': 'retained_failure',
            'status': 'mixed',
            'statement': 'Candidate failed its registered gate.',
            'scope': 'One fixed seed and budget.',
            'limitations': 'No runtime promotion.',
            'next_question': 'Which assumption failed?',
            'evidence': [{
                'path': 'failed.json',
                'sha256': sha256(artifact.read_bytes()).hexdigest(),
                'kind': 'artifact_assertion',
                'assertions': [{'pointer': '/passed', 'equals': False}],
            }],
        }],
    }
    return index, artifact


def test_retained_negative_result_is_valid_evidence(tmp_path):
    index, _ = _fixture(tmp_path)
    report = audit_claims(index, root=tmp_path)
    assert report['integrity_passed'] is True
    assert report['experiments_rerun'] is False
    assert report['semantic_faithfulness_proven'] is False


def test_changed_evidence_is_rejected_before_claims_are_accepted(tmp_path):
    index, artifact = _fixture(tmp_path)
    artifact.write_text('{"passed": true}\n')
    with pytest.raises(ValueError, match='digest changed'):
        audit_claims(index, root=tmp_path)


@pytest.mark.parametrize('assertion', [
    {'pointer': '/passed', 'equals': True},
    {'pointer': '/passed', 'equals': 0},
    {'pointer': '/does_not_exist', 'equals': False},
])
def test_false_or_mistyped_assertions_fail_even_with_correct_digest(tmp_path, assertion):
    index, _ = _fixture(tmp_path)
    index['claims'][0]['evidence'][0]['assertions'] = [assertion]
    with pytest.raises(ValueError, match='assertion failed|invalid artifact pointer'):
        audit_claims(index, root=tmp_path)


def test_missing_files_outside_paths_and_incomplete_claims_fail(tmp_path):
    index, _ = _fixture(tmp_path)
    for path in ('missing.json', '../outside.json', '/etc/passwd'):
        changed = deepcopy(index)
        changed['claims'][0]['evidence'][0]['path'] = path
        with pytest.raises(ValueError, match='path|missing|outside'):
            audit_claims(changed, root=tmp_path)
    del index['claims'][0]['limitations']
    with pytest.raises(ValueError, match='missing limitations'):
        audit_claims(index, root=tmp_path)


def test_repository_claims_are_traceable_including_unestablished_hypotheses():
    report = audit_claims(json.loads(DEFAULT_INDEX.read_text()))
    assert report['claim_count'] >= 6
    assert any(claim['status'] == 'not_established' for claim in report['claims'])
    assert any(claim['status'] == 'mixed' for claim in report['claims'])
