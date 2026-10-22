"""Compact on-screen keyboard (65% layout) whose keys light up while physically held."""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import font as tkfont

from .render import round_rect
from .winapi import COLORKEY, place_window, prepare_overlay_window

ROW_UNITS = 15.0  # every row adds up to this many key widths

# (label, width in key units, virtual-key codes that light this cap)
KEY_ROWS: list[list[tuple[str, float, tuple[int, ...]]]] = [
    [("Esc", 1, (0x1B,))] + [(f"F{n}", 1, (0x6F + n,)) for n in range(1, 13)] + [("Del", 2, (0x2E,))],
    [("`", 1, (0xC0,))] + [(c, 1, (ord(c),)) for c in "1234567890"]
    + [("-", 1, (0xBD,)), ("=", 1, (0xBB,)), ("Bksp", 2, (0x08,))],
    [("Tab", 1.5, (0x09,))] + [(c, 1, (ord(c),)) for c in "QWERTYUIOP"]
    + [("[", 1, (0xDB,)), ("]", 1, (0xDD,)), ("\\", 1.5, (0xDC,))],
    [("Caps", 1.75, (0x14,))] + [(c, 1, (ord(c),)) for c in "ASDFGHJKL"]
    + [(";", 1, (0xBA,)), ("'", 1, (0xDE,)), ("Enter", 2.25, (0x0D,))],
    [("Shift", 2.25, (0xA0, 0x10))] + [(c, 1, (ord(c),)) for c in "ZXCVBNM"]
    + [(",", 1, (0xBC,)), (".", 1, (0xBE,)), ("/", 1, (0xBF,)), ("Shift", 1.75, (0xA1, 0x10)),
       ("↑", 1, (0x26,))],
    [("Ctrl", 1, (0xA2, 0x11)), ("Win", 1, (0x5B, 0x5C)), ("Alt", 1, (0xA4, 0x12)), ("Space", 6, (0x20,)),
     ("Alt", 1, (0xA5, 0x12)), ("Menu", 1, (0x5D,)), ("Ctrl", 1, (0xA3, 0x11)),
     ("←", 1, (0x25,)), ("↓", 1, (0x28,)), ("→", 1, (0x27,))],
]


def lit_caps(held: frozenset[int] | set[int]) -> set[int]:
    """Indexes (row-major, matching draw order) of the caps that `held` should light."""
    lit = set()
    index = 0
    for row in KEY_ROWS:
        for _label, _units, vks in row:
            if any(vk in held for vk in vks):
                lit.add(index)
            index += 1
    return lit


@dataclass
class Cap:
    rect: int
    text: int


def draw_keyboard(canvas: tk.Canvas, theme: dict, font_size: int, scale: float) -> tuple[int, int, list[Cap]]:
    """Draw every key in its idle color. Returns (width, height, caps in row-major order)."""

    def px(value: float) -> int:
        return round(value * scale)

    unit, gap, pad = px(font_size * 1.5), px(4), px(8)
    font = tkfont.Font(family="Segoe UI", size=max(7, font_size // 2))
    canvas.delete("all")
    caps: list[Cap] = []
    y = pad
    for row in KEY_ROWS:
        x = pad
        for label, units, _vks in row:
            w = round(unit * units + gap * (units - 1))
            rect = round_rect(canvas, x, y, x + w, y + unit, px(5),
                              fill=theme["idle"], outline=theme["idle_edge"])
            text = canvas.create_text(x + w / 2, y + unit / 2, text=label, font=font, fill=theme["idle_text"])
            caps.append(Cap(rect, text))
            x += w + gap
        y += unit + gap
    width = round(pad * 2 + unit * ROW_UNITS + gap * (ROW_UNITS - 1))
    height = y - gap + pad
    panel = round_rect(canvas, 0, 0, width, height, px(10), fill=theme["panel"], outline=theme["panel"])
    canvas.tag_lower(panel)
    canvas.configure(width=width, height=height)
    return width, height, caps


class VirtualKeyboard:
    """A second click-through overlay window. Hidden until `show_at` is called."""

    def __init__(self, root: tk.Tk, theme: dict, font_size: int, scale: float, opacity: float) -> None:
        self.theme = theme
        self.opacity = opacity
        self.visible = False
        self._lit: set[int] = set()
        self.win = tk.Toplevel(root)
        self.hwnd = prepare_overlay_window(self.win)
        self.canvas = tk.Canvas(self.win, bg=COLORKEY, highlightthickness=0, bd=0)
        self.canvas.pack()
        self.width, self.height, self.caps = draw_keyboard(self.canvas, theme, font_size, scale)
        self.win.withdraw()

    def show_at(self, x: int, y: int) -> None:
        self.win.deiconify()
        self.win.attributes("-alpha", self.opacity)
        place_window(self.win, self.hwnd, x, y, self.width, self.height)
        self.visible = True

    def hide(self) -> None:
        self.win.withdraw()
        self.visible = False
        self.light(frozenset())

    def light(self, held: frozenset[int]) -> None:
        """Recolor only the caps whose state changed since the last call."""
        wanted = lit_caps(held)
        for index in self._lit - wanted:
            self._paint(index, pressed=False)
        for index in wanted - self._lit:
            self._paint(index, pressed=True)
        self._lit = wanted

    def _paint(self, index: int, pressed: bool) -> None:
        cap, t = self.caps[index], self.theme
        if pressed:
            self.canvas.itemconfigure(cap.rect, fill=t["keycap"], outline=t["edge"])
            self.canvas.itemconfigure(cap.text, fill=t["text"])
        else:
            self.canvas.itemconfigure(cap.rect, fill=t["idle"], outline=t["idle_edge"])
            self.canvas.itemconfigure(cap.text, fill=t["idle_text"])
