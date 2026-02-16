import unittest

from core.system_integrity import compute_system_integrity


class SystemIntegrityTest(unittest.TestCase):
    def test_healthy_empty_state(self):
        report = compute_system_integrity([], [], [])

        self.assertEqual(report["status"], "healthy")
        self.assertEqual(report["issues"], [])
        self.assertEqual(
            report["counts"],
            {"proposals": 0, "plans": 0, "launches": 0, "issues": 0},
        )

    def test_orphan_plan(self):
        plans = [{"plan_id": "plan-1", "proposal_id": "proposal-missing"}]

        report = compute_system_integrity([], plans, [])

        self.assertEqual(report["status"], "warning")
        self.assertEqual(report["counts"]["issues"], 1)
        self.assertEqual(report["issues"][0]["type"], "orphan_plan")
        self.assertEqual(report["issues"][0]["severity"], "warning")

    def test_missing_plan_for_approved_proposal(self):
        proposals = [{"id": "proposal-1", "status": "approved"}]

        report = compute_system_integrity(proposals, [], [])

        self.assertEqual(report["status"], "critical")
        self.assertEqual(report["issues"][0]["type"], "missing_plan")
        self.assertEqual(report["issues"][0]["severity"], "critical")

    def test_launch_without_proposal(self):
        launches = [{"id": "launch-1", "proposal_id": "proposal-missing"}]

        report = compute_system_integrity([], [], launches)

        self.assertEqual(report["status"], "critical")
        issue_types = {issue["type"] for issue in report["issues"]}
        self.assertIn("launch_without_proposal", issue_types)
        self.assertIn("launch_without_plan", issue_types)

    def test_archived_with_active_artifacts(self):
        proposals = [{"id": "proposal-1", "status": "archived"}]
        plans = [{"plan_id": "plan-1", "proposal_id": "proposal-1"}]

        report = compute_system_integrity(proposals, plans, [])

        self.assertEqual(report["status"], "warning")
        self.assertEqual(report["issues"][0]["type"], "archived_with_active_artifacts")
        self.assertEqual(report["issues"][0]["severity"], "warning")


if __name__ == "__main__":
    unittest.main()
