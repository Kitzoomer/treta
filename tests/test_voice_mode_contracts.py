import unittest
from pathlib import Path


class VoiceModeContractsTest(unittest.TestCase):
    def test_ui_has_voice_and_speak_toggles(self):
        app_js = Path("ui/app.js").read_text(encoding="utf-8")
        self.assertIn("Voice Mode:", app_js)
        self.assertIn("Speak:", app_js)
        self.assertIn("Voice not supported in this browser", app_js)

    def test_http_has_conversation_message_endpoint(self):
        ipc_http = Path("core/ipc_http.py").read_text(encoding="utf-8")
        self.assertIn('"/conversation/message"', ipc_http)
        self.assertIn('reply_text', ipc_http)


if __name__ == "__main__":
    unittest.main()
