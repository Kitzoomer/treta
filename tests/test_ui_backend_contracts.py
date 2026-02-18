import unittest
from pathlib import Path


class UiBackendContractsTest(unittest.TestCase):
    def test_launch_status_payload_uses_active_not_launched(self):
        app_js = Path("ui/app.js").read_text(encoding="utf-8")
        self.assertIn('status: "active"', app_js)
        self.assertNotIn('status: "launched" } } };', app_js)

    def test_launch_action_is_gated_by_ready_for_review(self):
        app_js = Path("ui/app.js").read_text(encoding="utf-8")
        self.assertIn('const isReadyForLaunch = proposalStatus === "ready_for_review";', app_js)
        self.assertIn('} else if (proposalId && isReadyForLaunch && !launch) {', app_js)


if __name__ == "__main__":
    unittest.main()
