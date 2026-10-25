import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_code_case_diagnosis_does_not_reclassify_primary_failure():
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        spec = importlib.util.spec_from_file_location("scope_component_audit", ROOT / "scripts/audit_gamespec_scope_components.py")
        audit = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(audit)
        _, bundle = audit.package()
        item = bundle["cases"]["slice_42"]
        payload = {"schema_version": "aip-observation-refusal-v1", "game_id": "slice_42",
                   "status": "out_of_schema", "error_code": "out_of_schema_static_visibility",
                   "witness": item["control"]["required_witness"].copy()}
        result = audit.refusal_components(payload, item)
        assert result["only_error_code_case_failure"]
        assert result["registered_visibility_change_exact"]
        from aip.core.game_spec_smoke import validate_scope_refusal
        assert not validate_scope_refusal(payload, item["control"])["passed"]
        payload["witness"]["player"] = "player_1"
        result = audit.refusal_components(payload, item)
        assert not result["only_error_code_case_failure"]
        assert not result["registered_visibility_change_exact"]
    finally:
        sys.path.pop(0)
