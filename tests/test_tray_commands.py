import unittest

from key_overlay import tray
from key_overlay.layout import POSITIONS


class TrayCommandMappingTest(unittest.TestCase):
    def test_position_commands_round_trip_and_do_not_collide(self):
        ids = [tray.command_for_position(key) for key in POSITIONS]
        self.assertEqual(len(set(ids)), len(POSITIONS))
        self.assertNotIn(tray.CMD_QUIT, ids)
        self.assertNotIn(tray.CMD_TOGGLE_KEYBOARD, ids)
        for key in POSITIONS:
            self.assertEqual(tray.position_for_command(tray.command_for_position(key)), key)

    def test_unknown_command_is_not_a_position(self):
        self.assertIsNone(tray.position_for_command(tray.CMD_QUIT))
        self.assertIsNone(tray.position_for_command(tray.CMD_POSITION_BASE + len(POSITIONS)))
        self.assertIsNone(tray.position_for_command(0))


if __name__ == "__main__":
    unittest.main()
