"""Check claim-to-evidence consistency; this does not rerun experiments."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INDEX = ROOT / 'research/claim_evidence_index.json'


def _file(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError('evidence path must be repository-relative')
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
        raise ValueError(f'evidence file missing or outside repository: {relative}')
    return resolved


def _pointer(document, pointer: str):
    """Resolve RFC 6901 JSON pointers for explicit artifact assertions."""
    if pointer == '':
        return document
    if not isinstance(pointer, str) or not pointer.startswith('/'):
        raise ValueError('artifact pointer must begin with /')
    for part in pointer[1:].split('/'):
        part = part.replace('~1', '/').replace('~0', '~')
        document = document[int(part)] if isinstance(document, list) else document[part]
    return document


def audit_claims(index: dict, *, root: Path = ROOT) -> dict:
    if index.get('schema_version') != 'aip-claim-evidence-v1':
        raise ValueError('unsupported claim index schema')
    claims = index.get('claims')
    if not isinstance(claims, list) or not claims:
        raise ValueError('claim index must contain claims')
    seen = set()
    records = []
    for claim in claims:
        identifier = claim.get('id')
        if not isinstance(identifier, str) or not identifier or identifier in seen:
            raise ValueError('claim IDs must be nonempty and unique')
        seen.add(identifier)
        for field in ('statement', 'scope', 'limitations', 'next_question'):
            if not isinstance(claim.get(field), str) or not claim[field].strip():
                raise ValueError(f'{identifier}: missing {field}')
        if claim.get('status') not in {'supported_in_scope', 'mixed', 'not_established'}:
            raise ValueError(f'{identifier}: unknown evidence status')
        evidence = claim.get('evidence')
        if not isinstance(evidence, list) or not evidence:
            raise ValueError(f'{identifier}: evidence is required')
        checked = []
        for item in evidence:
            path = _file(root, item['path'])
            payload = path.read_bytes()
            if sha256(payload).hexdigest() != item.get('sha256'):
                raise ValueError(f'{identifier}: evidence digest changed: {item["path"]}')
            if item.get('kind') not in {'artifact_assertion', 'source_reference'}:
                raise ValueError(f'{identifier}: unknown evidence kind')
            if item['kind'] == 'artifact_assertion':
                assertions = item.get('assertions')
                if not isinstance(assertions, list) or not assertions:
                    raise ValueError(f'{identifier}: artifact assertions required')
                document = json.loads(payload)
                for assertion in assertions:
                    try:
                        actual = _pointer(document, assertion['pointer'])
                    except (KeyError, IndexError, TypeError, ValueError) as error:
                        raise ValueError(f'{identifier}: invalid artifact pointer') from error
                    expected = assertion['equals']
                    if type(actual) is not type(expected) or actual != expected:
                        raise ValueError(
                            f'{identifier}: assertion failed at {assertion["pointer"]}'
                        )
            checked.append(item['path'])
        records.append({'id': identifier, 'status': claim['status'], 'evidence': checked})
    return {
        'schema_version': 'aip-claim-integrity-report-v1',
        'claim_count': len(records),
        'claims': records,
        'integrity_passed': True,
        'experiments_rerun': False,
        'semantic_faithfulness_proven': False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', type=Path, default=DEFAULT_INDEX)
    args = parser.parse_args()
    try:
        report = audit_claims(json.loads(args.index.read_text(encoding='utf-8')))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f'Claim evidence integrity failed: {error}\n')
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
