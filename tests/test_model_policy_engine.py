import os
import unittest

from core.model_policy_engine import ModelPolicyEngine


class ModelPolicyEngineTest(unittest.TestCase):
    def test_defaults_are_safe(self):
        engine = ModelPolicyEngine()
        self.assertEqual(engine.get_model("chat"), "gpt-4o-mini")
        self.assertEqual(engine.get_model("planning"), "gpt-4o-mini")
        self.assertEqual(engine.get_model("summarize"), "gpt-4o-mini")
        self.assertEqual(engine.get_model("tts"), "gpt-4o-mini-tts")

    def test_env_override_for_chat(self):
        previous = os.environ.get("TRETA_MODEL_CHAT")
        os.environ["TRETA_MODEL_CHAT"] = "gpt-4.1-mini"
        try:
            engine = ModelPolicyEngine()
            self.assertEqual(engine.get_model("chat"), "gpt-4.1-mini")
        finally:
            if previous is None:
                os.environ.pop("TRETA_MODEL_CHAT", None)
            else:
                os.environ["TRETA_MODEL_CHAT"] = previous


if __name__ == "__main__":
    unittest.main()
