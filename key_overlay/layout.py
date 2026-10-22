"""Screen-corner placement for the overlay windows. Pure arithmetic, unit tested."""

from __future__ import annotations

POSITIONS = {
    "bottom-left": "左下",
    "bottom-right": "右下",
    "top-left": "左上",
    "top-right": "右上",
}
DEFAULT_POSITION = "bottom-left"


def is_bottom(position: str) -> bool:
    return position.startswith("bottom")


def is_left(position: str) -> bool:
    return position.endswith("left")


def corner_origin(position: str, work_area: tuple[int, int, int, int], size: tuple[int, int],
                  margin: int, stack_offset: int = 0) -> tuple[int, int]:
    """Top-left point for a window of `size` sitting in `position` of `work_area`.

    `stack_offset` pushes the window away from the top/bottom edge, so a second window
    can sit above (bottom corners) or below (top corners) another one at the same corner.
    """
    left, top, right, bottom = work_area
    width, height = size
    x = left + margin if is_left(position) else right - margin - width
    if is_bottom(position):
        y = bottom - margin - height - stack_offset
    else:
        y = top + margin + stack_offset
    return x, y
