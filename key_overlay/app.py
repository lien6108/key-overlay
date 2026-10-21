"""Bottom-left on-screen overlay showing the key combination currently being pressed."""

from __future__ import annotations

import argparse
import ctypes
import queue
import sys
import time
import tkinter as tk
from ctypes import wintypes
from tkinter import font as tkfont

from . import __version__
from .hook import KeyboardHook, is_key_down
from .keys import KeyState

QUIT_LABELS = ["Ctrl", "Alt", "Shift", "Q"]
POLL_MS = 15
PRUNE_EVERY_S = 1.0
PRUNE_MIN_AGE_S = 1.0
FADE_STEPS = 8
FADE_STEP_MS = 25

COLORKEY = "#010203"  # painted pixels in this color become fully transparent
PANEL_BG = "#1E1E1E"
KEYCAP_BG = "#3A3A3A"
KEYCAP_EDGE = "#5A5A5A"
TEXT_FG = "#FFFFFF"
PLUS_FG = "#A0A0A0"

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
GA_ROOT = 2
HWND_TOPMOST = -1
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x0001, 0x0002, 0x0010
SPI_GETWORKAREA = 0x0030
ERROR_ALREADY_EXISTS = 183

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT, ctypes.c_void_p, wintypes.UINT]
kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CreateMutexW.restype = wintypes.HANDLE


def enable_dpi_awareness() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor
    except (AttributeError, OSError):
        try:
            user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def acquire_single_instance():
    handle = kernel32.CreateMutexW(None, False, "Local\\key-overlay-single-instance")
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        return None
    return handle


def primary_work_area() -> tuple[int, int, int, int]:
    rect = wintypes.RECT()
    user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
    return rect.left, rect.top, rect.right, rect.bottom


def round_rect(canvas: tk.Canvas, x1, y1, x2, y2, r, **kw) -> int:
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


class Overlay:
    def __init__(self, root: tk.Tk, hook: KeyboardHook, args: argparse.Namespace) -> None:
        self.root = root
        self.hook = hook
        self.args = args
        self.state = KeyState()
        self.scale = root.winfo_fpixels("1i") / 96
        self.font = tkfont.Font(family="Segoe UI Semibold", size=args.font_size)
        self.plus_font = tkfont.Font(family="Segoe UI", size=max(8, args.font_size - 4))
        self.hide_job: str | None = None
        self.fade_job: str | None = None
        self.last_prune = time.monotonic()

        root.overrideredirect(True)
        root.configure(bg=COLORKEY)
        root.attributes("-transparentcolor", COLORKEY)
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.0)
        self.canvas = tk.Canvas(root, bg=COLORKEY, highlightthickness=0, bd=0)
        self.canvas.pack()
        root.geometry("1x1+0+0")
        root.update_idletasks()
        self.hwnd = user32.GetAncestor(root.winfo_id(), GA_ROOT)
        self._apply_window_styles()
        root.after(POLL_MS, self._poll)

    def px(self, value: float) -> int:
        return round(value * self.scale)

    def _apply_window_styles(self) -> None:
        style = user32.GetWindowLongPtrW(self.hwnd, GWL_EXSTYLE)
        style |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        user32.SetWindowLongPtrW(self.hwnd, GWL_EXSTYLE, style)

    def _poll(self) -> None:
        now = time.monotonic()
        changed = False
        released = False
        try:
            while True:
                vk, is_down = self.hook.events.get_nowait()
                if is_down:
                    changed |= self.state.press(vk, now)
                else:
                    self.state.release(vk)
                    released = True
        except queue.Empty:
            pass

        if now - self.last_prune >= PRUNE_EVERY_S:
            self.last_prune = now
            had_keys = not self.state.empty()
            self.state.prune(is_key_down, now, PRUNE_MIN_AGE_S)
            released |= had_keys and self.state.empty()

        if changed:
            labels = self.state.labels()
            if labels == QUIT_LABELS:
                self.quit()
                return
            if not self.args.combos_only or self.state.has_command_modifier():
                self.show(labels)
        if released and self.state.empty():
            self._schedule_hide()

        self.root.after(POLL_MS, self._poll)

    def show(self, labels: list[str]) -> None:
        self._cancel_jobs()
        c = self.canvas
        c.delete("all")
        pad, gap, cap_px, cap_py = self.px(10), self.px(8), self.px(12), self.px(6)
        text_h = self.font.metrics("linespace")
        cap_h = text_h + 2 * cap_py
        x = pad
        for i, label in enumerate(labels):
            if i:
                c.create_text(x, pad + cap_h / 2, text="+", font=self.plus_font, fill=PLUS_FG, anchor="w")
                x += self.plus_font.measure("+") + gap
            cap_w = max(cap_h, self.font.measure(label) + 2 * cap_px)
            round_rect(c, x, pad, x + cap_w, pad + cap_h, self.px(8), fill=KEYCAP_BG, outline=KEYCAP_EDGE)
            c.create_text(x + cap_w / 2, pad + cap_h / 2, text=label, font=self.font, fill=TEXT_FG)
            x += cap_w + gap
        width, height = x - gap + pad, cap_h + 2 * pad
        panel = round_rect(c, 0, 0, width, height, self.px(12), fill=PANEL_BG, outline=PANEL_BG)
        c.tag_lower(panel)
        c.configure(width=width, height=height)

        left, _, _, bottom = primary_work_area()
        margin = self.px(self.args.margin)
        self.root.geometry(f"{width}x{height}+{left + margin}+{bottom - margin - height}")
        self.root.attributes("-alpha", self.args.opacity)
        self._apply_window_styles()
        user32.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)

    def _schedule_hide(self) -> None:
        self._cancel_jobs()
        self.hide_job = self.root.after(int(self.args.hold * 1000), lambda: self._fade(FADE_STEPS))

    def _fade(self, steps_left: int) -> None:
        self.hide_job = None
        self.root.attributes("-alpha", self.args.opacity * steps_left / FADE_STEPS)
        if steps_left > 0:
            self.fade_job = self.root.after(FADE_STEP_MS, lambda: self._fade(steps_left - 1))
        else:
            self.fade_job = None

    def _cancel_jobs(self) -> None:
        for job in (self.hide_job, self.fade_job):
            if job:
                self.root.after_cancel(job)
        self.hide_job = self.fade_job = None

    def quit(self) -> None:
        self.hook.stop()
        self.root.destroy()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="key-overlay", description=__doc__)
    p.add_argument("--font-size", type=int, default=20, help="key label font size in pt (default 20)")
    p.add_argument("--hold", type=float, default=1.5, help="seconds to keep showing after release (default 1.5)")
    p.add_argument("--margin", type=int, default=24, help="distance from screen edge in px (default 24)")
    p.add_argument("--opacity", type=float, default=0.92, help="0.1-1.0 (default 0.92)")
    p.add_argument("--combos-only", action="store_true",
                   help="only show when Ctrl/Alt/Win is held, so plain typing (e.g. passwords) is never displayed")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = p.parse_args(argv)
    args.opacity = min(1.0, max(0.1, args.opacity))
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    mutex = acquire_single_instance()
    if mutex is None:
        return 0  # already running

    enable_dpi_awareness()
    hook = KeyboardHook()
    hook.start()
    hook.ready.wait(5)
    root = tk.Tk()
    root.title("Key Overlay")
    if hook.error is not None or not hook.ready.is_set():
        from tkinter import messagebox
        root.withdraw()
        messagebox.showerror("Key Overlay", f"無法安裝鍵盤 hook（Win32 error {hook.error}）。")
        return 1

    Overlay(root, hook, args)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
