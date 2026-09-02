import unittest

from scripts.audit_mastermind_holdout import build_readiness_report


class MastermindHoldoutAuditTests(unittest.TestCase):
    def test_offline_readiness_report_keeps_claims_and_execution_distinct(self) -> None:
        report = build_readiness_report(("0123",))
        self.assertTrue(report["frozenTransferAudit"]["passed"])
        panel = report["offlineReferencePanel"]
        self.assertEqual(panel["evidenceLevel"], "strong_heuristic")
        self.assertFalse(panel["exactRegretReported"])
        self.assertFalse(panel["exploitabilityReported"])
        gates = report["readinessGates"]
        self.assertTrue(gates["twoModelTwoRepeatSmokeAuthorized"])
        self.assertFalse(gates["twoModelTwoRepeatSmokeExecuted"])


if __name__ == "__main__":
    unittest.main()
