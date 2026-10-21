import unittest

from key_overlay.keys import KeyState, format_combo, vk_label

VK_LCTRL, VK_RCTRL, VK_LSHIFT, VK_LALT, VK_LWIN = 0xA2, 0xA3, 0xA0, 0xA4, 0x5B
VK_Z, VK_X, VK_C = 0x5A, 0x58, 0x43


class VkLabelTest(unittest.TestCase):
    def test_letters_digits_function_keys(self):
        self.assertEqual(vk_label(VK_Z), "Z")
        self.assertEqual(vk_label(0x31), "1")
        self.assertEqual(vk_label(0x70), "F1")
        self.assertEqual(vk_label(0x87), "F24")
        self.assertEqual(vk_label(0x63), "Num3")

    def test_left_right_modifiers_collapse(self):
        self.assertEqual(vk_label(VK_LCTRL), "Ctrl")
        self.assertEqual(vk_label(VK_RCTRL), "Ctrl")
        self.assertEqual(vk_label(0xA5), "Alt")

    def test_unknown_falls_back_to_hex(self):
        self.assertEqual(vk_label(0xE9), "0xE9")


class KeyStateTest(unittest.TestCase):
    def test_modifiers_sorted_before_keys(self):
        s = KeyState()
        s.press(VK_Z)
        s.press(VK_LSHIFT)
        s.press(VK_LCTRL)
        self.assertEqual(format_combo(s.labels()), "Ctrl + Shift + Z")

    def test_win_comes_first(self):
        s = KeyState()
        s.press(VK_LSHIFT)
        s.press(VK_LWIN)
        s.press(0x53)
        self.assertEqual(s.labels(), ["Win", "Shift", "S"])

    def test_non_modifiers_keep_press_order(self):
        s = KeyState()
        for vk in (VK_C, VK_Z, VK_X):
            s.press(vk)
        self.assertEqual(s.labels(), ["C", "Z", "X"])

    def test_auto_repeat_is_not_a_change(self):
        s = KeyState()
        self.assertTrue(s.press(VK_Z))
        self.assertFalse(s.press(VK_Z))

    def test_both_ctrl_keys_show_once(self):
        s = KeyState()
        s.press(VK_LCTRL)
        s.press(VK_RCTRL)
        self.assertEqual(s.labels(), ["Ctrl"])
        s.release(VK_LCTRL)
        self.assertEqual(s.labels(), ["Ctrl"])

    def test_release_and_empty(self):
        s = KeyState()
        s.press(VK_LCTRL)
        s.release(VK_LCTRL)
        s.release(VK_Z)  # unknown release is harmless
        self.assertTrue(s.empty())

    def test_ignored_vk(self):
        s = KeyState()
        self.assertFalse(s.press(0xE5))
        self.assertTrue(s.empty())

    def test_prune_only_old_keys_that_are_up(self):
        s = KeyState()
        s.press(VK_LCTRL, now=0.0)
        s.press(VK_Z, now=0.9)
        s.prune(lambda vk: False, now=1.0, min_age=1.0)
        self.assertEqual(s.labels(), ["Z"])

    def test_command_modifier(self):
        s = KeyState()
        s.press(VK_LSHIFT)
        s.press(VK_Z)
        self.assertFalse(s.has_command_modifier())
        s.press(VK_LALT)
        self.assertTrue(s.has_command_modifier())


if __name__ == "__main__":
    unittest.main()
