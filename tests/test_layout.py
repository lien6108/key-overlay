import unittest

from key_overlay.layout import DEFAULT_POSITION, POSITIONS, corner_origin

WORK_AREA = (0, 0, 1920, 1040)  # 1080p with a 40px taskbar
SIZE = (300, 100)


class CornerOriginTest(unittest.TestCase):
    def test_every_position_has_a_display_name_and_default_is_valid(self):
        self.assertEqual(set(POSITIONS), {"bottom-left", "bottom-right", "top-left", "top-right"})
        self.assertIn(DEFAULT_POSITION, POSITIONS)

    def test_four_corners(self):
        self.assertEqual(corner_origin("bottom-left", WORK_AREA, SIZE, 24), (24, 1040 - 24 - 100))
        self.assertEqual(corner_origin("bottom-right", WORK_AREA, SIZE, 24), (1920 - 24 - 300, 1040 - 24 - 100))
        self.assertEqual(corner_origin("top-left", WORK_AREA, SIZE, 24), (24, 24))
        self.assertEqual(corner_origin("top-right", WORK_AREA, SIZE, 24), (1920 - 24 - 300, 24))

    def test_stack_offset_moves_away_from_the_vertical_edge(self):
        self.assertEqual(corner_origin("bottom-left", WORK_AREA, SIZE, 24, stack_offset=200), (24, 1040 - 24 - 100 - 200))
        self.assertEqual(corner_origin("top-right", WORK_AREA, SIZE, 24, stack_offset=200), (1920 - 24 - 300, 24 + 200))

    def test_work_area_origin_is_respected(self):
        self.assertEqual(corner_origin("top-left", (100, 50, 900, 650), SIZE, 10), (110, 60))


if __name__ == "__main__":
    unittest.main()
