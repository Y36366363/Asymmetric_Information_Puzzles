"""Reference-free local diagnostics. Local consistency is never semantic truth."""
from aip.benchmark.gamespec_attribution import normalize_table
from aip.benchmark.gamespec_interface import serialize_proposal


MISSING = object()


def check_local(fields, *, table=MISSING, proposal=MISSING, require_observer=True):
    """No rules, reference or case-kind argument: only inspect declared data.

    require_observer is a restriction of the CURRENT three-owner language.
    Legitimate games with nature-only fields must disable it/use another contract.
    """
    fields = tuple(fields)
    if not fields or any(not isinstance(f,str) for f in fields) or len(fields)!=len(set(fields)):
        raise ValueError("unique nonempty field vocabulary required")
    violations = []
    normalized = None
    inspected_table = table is not MISSING
    inspected_proposal = proposal is not MISSING
    if inspected_table:
        try:
            normalized = normalize_table(table,fields)
        except ValueError:
            violations.append({"code":"table_contract_error"})
        if normalized is not None and require_observer:
            for phase,views in enumerate(normalized):
                absent = sorted(set(fields)-(set(views[0])|set(views[1])))
                if absent:
                    violations.append({"code":"outside_three_owner_language","phase":phase,"fields":absent})
    proposal_valid = False
    if inspected_proposal:
        try:
            serialize_proposal(proposal,{"case_id":"local_check","fields":dict.fromkeys(fields,"")})
            proposal_valid = True
        except (ValueError,TypeError,KeyError):
            violations.append({"code":"proposal_contract_error"})
    if proposal_valid:
        if proposal["decision"]=="refusal":
            w = proposal["witness"]
            if w["before_visible"]==w["after_visible"]:
                violations.append({"code":"non_change_witness"})
            if normalized is not None:
                actual = tuple(w["field"] in phase[w["player"]] for phase in normalized)
                if actual!=(w["before_visible"],w["after_visible"]):
                    violations.append({"code":"witness_disagrees_with_declared_table"})
        elif normalized is not None:
            consistent = any(all(
                set(candidate["public_fields"])|set(candidate["private_fields_by_player"][f"player_{player}"])
                ==set(phase[player]) for phase in normalized for player in range(2))
                for candidate in proposal["candidates"])
            if not consistent:
                violations.append({"code":"candidate_disagrees_with_declared_table"})
    if not inspected_table and not inspected_proposal:
        violations.append({"code":"no_declared_data"})
    return {"status":"reject_local" if violations else "locally_consistent_unverified",
        "violations":violations,"inspected_table":inspected_table,"inspected_proposal":inspected_proposal,
        "require_observer_in_each_phase":require_observer,
        "semantic_verdict":"not_assessed","semantic_certification_allowed":False,
        "diagnostic_only_no_runtime_promotion":True}
