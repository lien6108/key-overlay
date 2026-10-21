import tempfile
import unittest
from pathlib import Path
from unittest import mock

from key_overlay import launcher


class SettingsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "KeyOverlay" / "settings.json"
        patcher = mock.patch.object(launcher, "SETTINGS_PATH", self.path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_missing_file_gives_empty(self):
        self.assertEqual(launcher.load_settings(), {})

    def test_round_trip_creates_folder(self):
        launcher.save_settings({"theme": "blue", "combos_only": True})
        self.assertEqual(launcher.load_settings(), {"theme": "blue", "combos_only": True})

    def test_corrupt_or_non_dict_json_is_ignored(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{not json", encoding="utf-8")
        self.assertEqual(launcher.load_settings(), {})
        self.path.write_text("[1, 2]", encoding="utf-8")
        self.assertEqual(launcher.load_settings(), {})


if __name__ == "__main__":
    unittest.main()
