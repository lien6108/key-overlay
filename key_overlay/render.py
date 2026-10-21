"""Color themes and keycap drawing shared by the overlay and the launcher preview."""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont

THEMES = {
    "yellow": {"name": "亮黃", "panel": "#111111", "keycap": "#FFD60A", "edge": "#FFE866",
               "text": "#111111", "plus": "#FFD60A"},
    "blue": {"name": "亮藍", "panel": "#0B1E3F", "keycap": "#2F80ED", "edge": "#6FA8FF",
             "text": "#FFFFFF", "plus": "#6FA8FF"},
    "white": {"name": "亮白", "panel": "#111111", "keycap": "#FFFFFF", "edge": "#FFFFFF",
              "text": "#111111", "plus": "#FFFFFF"},
}
DEFAULT_THEME = "yellow"

_fonts: dict[int, tuple[tkfont.Font, tkfont.Font]] = {}


def _fonts_for(size: int) -> tuple[tkfont.Font, tkfont.Font]:
    if size not in _fonts:
        _fonts[size] = (tkfont.Font(family="Segoe UI Semibold", size=size),
                        tkfont.Font(family="Segoe UI", size=max(8, size - 4)))
    return _fonts[size]


def round_rect(canvas: tk.Canvas, x1, y1, x2, y2, r, **kw) -> int:
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


def draw_combo(canvas: tk.Canvas, labels: list[str], theme: dict, font_size: int,
               scale: float) -> tuple[int, int]:
    """Clear `canvas`, draw the panel with one keycap per label, resize it and return (width, height)."""

    def px(value: float) -> int:
        return round(value * scale)

    font, plus_font = _fonts_for(font_size)
    canvas.delete("all")
    pad, gap, cap_px, cap_py = px(10), px(8), px(12), px(6)
    cap_h = font.metrics("linespace") + 2 * cap_py
    x = pad
    for i, label in enumerate(labels):
        if i:
            canvas.create_text(x, pad + cap_h / 2, text="+", font=plus_font, fill=theme["plus"], anchor="w")
            x += plus_font.measure("+") + gap
        cap_w = max(cap_h, font.measure(label) + 2 * cap_px)
        round_rect(canvas, x, pad, x + cap_w, pad + cap_h, px(8), fill=theme["keycap"], outline=theme["edge"])
        canvas.create_text(x + cap_w / 2, pad + cap_h / 2, text=label, font=font, fill=theme["text"])
        x += cap_w + gap
    width, height = x - gap + pad, cap_h + 2 * pad
    panel = round_rect(canvas, 0, 0, width, height, px(12), fill=theme["panel"], outline=theme["panel"])
    canvas.tag_lower(panel)
    canvas.configure(width=width, height=height)
    return width, height
