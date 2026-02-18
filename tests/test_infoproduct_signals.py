import os
import shutil
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from core.control import Control
from core.dispatcher import Dispatcher
from core.events import Event
from core.opportunity_store import OpportunityStore
from core.state_machine import State, StateMachine
from core.bus import event_bus


class InfoproductSignalsTest(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self._data_dir = Path(self._temp_dir.name)

        self._original_data_dir = os.environ.get("TRETA_DATA_DIR")
        os.environ["TRETA_DATA_DIR"] = str(self._data_dir)
        self._clear_data_dir()

    def tearDown(self):
        if self._original_data_dir is None:
            os.environ.pop("TRETA_DATA_DIR", None)
        else:
            os.environ["TRETA_DATA_DIR"] = self._original_data_dir
        self._temp_dir.cleanup()

    def _clear_data_dir(self):
        self._data_dir.mkdir(parents=True, exist_ok=True)
        for child in self._data_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()

    def test_run_infoproduct_scan_populates_opportunity_store(self):
        while event_bus.pop(timeout=0.001) is not None:
            pass

        opportunity_store = OpportunityStore()
        control = Control(opportunity_store=opportunity_store)
        dispatcher = Dispatcher(state_machine=StateMachine(initial_state=State.IDLE), control=control)

        with unittest.mock.patch(
            "core.reddit_public.service.RedditPublicService.scan_subreddits",
            return_value=[
                {
                    "id": "a1",
                    "title": "Need client proposal template",
                    "selftext": "I am struggling with pricing and rate discussion.",
                    "score": 5,
                    "num_comments": 2,
                    "subreddit": "freelance",
                },
                {
                    "id": "a2",
                    "title": "media kit help",
                    "selftext": "how do i create one?",
                    "score": 7,
                    "num_comments": 3,
                    "subreddit": "ugc",
                },
                {
                    "id": "a3",
                    "title": "struggling with client onboarding",
                    "selftext": "",
                    "score": 4,
                    "num_comments": 1,
                    "subreddit": "smallbusiness",
                },
            ],
        ):
            dispatcher.handle(Event(type="RunInfoproductScan", payload={}, source="test"))

        while True:
            queued = event_bus.pop(timeout=0.01)
            if queued is None:
                break
            dispatcher.handle(queued)

        items = opportunity_store.list()
        self.assertEqual(len(items), 3)


if __name__ == "__main__":
    unittest.main()
