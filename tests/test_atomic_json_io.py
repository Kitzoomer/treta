import tempfile
import unittest
from pathlib import Path

from core.persistence.json_io import atomic_read_json, atomic_write_json


class AtomicJsonIoTest(unittest.TestCase):
    def test_atomic_write_and_read_json_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "state.json"
            data = {"hola": "mundo", "count": 3}

            atomic_write_json(path, data)

            self.assertEqual(atomic_read_json(path, {}), data)
            self.assertFalse(path.with_suffix(path.suffix + ".tmp").exists())

    def test_atomic_read_json_quarantines_corrupt_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "broken.json"
            path.write_text("{", encoding="utf-8")

            loaded = atomic_read_json(path, {"default": True})

            self.assertEqual(loaded, {"default": True})
            self.assertFalse(path.exists())
            self.assertEqual(len(list(Path(tmp_dir).glob("broken.json*.corrupt"))), 1)


if __name__ == "__main__":
    unittest.main()
