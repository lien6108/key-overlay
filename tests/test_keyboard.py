import unittest

from key_overlay.keyboard import KEY_ROWS, ROW_UNITS, lit_caps
from key_overlay.keys import vk_label


def _caps():
    return [cap for row in KEY_ROWS for cap in row]


class KeyboardLayoutTest(unittest.TestCase):
    def test_every_row_is_the_same_width(self):
        for row in KEY_ROWS:
            self.assertAlmostEqual(sum(units for _, units, _ in row), ROW_UNITS, msg=[label for label, _, _ in row])

    def test_every_cap_maps_to_known_virtual_keys(self):
        for label, _, vks in _caps():
            self.assertTrue(vks, label)
            for vk in vks:
                self.assertFalse(vk_label(vk).startswith("0x"), f"{label} -> {vk:#x} has no name")

    def test_lit_caps_matches_left_and_right_modifiers_separately(self):
        caps = _caps()
        left_shift = next(i for i, (label, _, vks) in enumerate(caps) if label == "Shift" and 0xA0 in vks)
        right_shift = next(i for i, (label, _, vks) in enumerate(caps) if label == "Shift" and 0xA1 in vks)

        self.assertEqual(lit_caps({0xA0}), {left_shift})
        self.assertEqual(lit_caps({0xA1}), {right_shift})
        self.assertEqual(lit_caps({0x10}), {left_shift, right_shift})  # generic VK_SHIFT lights both

    def test_lit_caps_for_a_combo(self):
        caps = _caps()
        ctrl = next(i for i, (_, _, vks) in enumerate(caps) if 0xA2 in vks)
        z = next(i for i, (label, _, _) in enumerate(caps) if label == "Z")

        self.assertEqual(lit_caps(frozenset({0xA2, 0x5A})), {ctrl, z})
        self.assertEqual(lit_caps(frozenset()), set())


if __name__ == "__main__":
    unittest.main()
