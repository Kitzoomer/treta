import json
import os
import unittest
from unittest.mock import Mock, patch
from urllib.request import Request, urlopen

from core.ipc_http import start_http_server


class VoiceTTSEndpointTest(unittest.TestCase):
    @patch("core.ipc_http.OpenAI")
    def test_voice_tts_returns_mpeg_audio(self, mock_openai):
        server = start_http_server(host="127.0.0.1", port=0)
        previous_api_key = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = "test-key"

        try:
            mock_response = Mock()
            mock_response.read.return_value = b"fake-mp3"
            mock_client = Mock()
            mock_client.audio.speech.create.return_value = mock_response
            mock_openai.return_value = mock_client

            request = Request(
                f"http://127.0.0.1:{server.server_port}/voice/tts",
                data=json.dumps({"text": "Hola"}).encode("utf-8"),
                method="POST",
                headers={"Content-Type": "application/json"},
            )

            with urlopen(request, timeout=2) as response:
                body = response.read()

            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers.get("Content-Type"), "audio/mpeg")
            self.assertEqual(body, b"fake-mp3")
            mock_client.audio.speech.create.assert_called_once_with(
                model="gpt-4o-mini-tts",
                voice="sol",
                input="Hola",
            )
        finally:
            if previous_api_key is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = previous_api_key
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
