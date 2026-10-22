import unittest

from key_overlay.app import parse_args, resolve_settings


class ResolveSettingsTest(unittest.TestCase):
    def test_defaults_when_nothing_saved(self):
        self.assertEqual(resolve_settings(parse_args([]), {}), {
            "theme": "yellow", "position": "bottom-left", "combos_only": False, "keyboard": False})

    def test_saved_choice_is_used(self):
        saved = {"theme": "blue", "position": "top-right", "combos_only": True, "keyboard": True}
        self.assertEqual(resolve_settings(parse_args([]), saved), saved)

    def test_flags_override_saved(self):
        saved = {"theme": "blue", "position": "top-right", "combos_only": False, "keyboard": False}
        args = parse_args(["--theme", "white", "--position", "bottom-right", "--keyboard", "--combos-only"])
        self.assertEqual(resolve_settings(args, saved), {
            "theme": "white", "position": "bottom-right", "combos_only": True, "keyboard": True})

    def test_invalid_saved_values_fall_back_to_defaults(self):
        saved = {"theme": "neon", "position": "middle", "combos_only": "yes", "keyboard": 1}
        self.assertEqual(resolve_settings(parse_args([]), saved), {
            "theme": "yellow", "position": "bottom-left", "combos_only": True, "keyboard": True})


if __name__ == "__main__":
    unittest.main()
