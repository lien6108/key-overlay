"""Bottom-left on-screen overlay showing the key combination currently being pressed."""

from __future__ import annotations

import argparse
import ctypes
import queue
import sys
import time
import tkinter as tk
from ctypes import wintypes
from tkinter import messagebox

from . import __version__
from .hook import KeyboardHook, is_key_down
from .keys import KeyState
from .launcher import QUIT_HINT, ask_start, load_settings, save_settings
from .render import DEFAULT_THEME, THEMES, draw_combo

QUIT_LABELS = ["Ctrl", "Alt", "Shift", "Q"]
POLL_MS = 15
PRUNE_EVERY_S = 1.0
PRUNE_MIN_AGE_S = 1.0
FADE_STEPS = 8
FADE_STEP_MS = 25

COLORKEY = "#010203"  # painted pixels in this color become fully transparent

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


class Overlay:
    def __init__(self, root: tk.Tk, hook: KeyboardHook, args: argparse.Namespace, scale: float) -> None:
        self.root = root
        self.hook = hook
        self.args = args
        self.scale = scale
        self.state = KeyState()
        self.theme = THEMES[args.theme]
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
        root.deiconify()
        root.update_idletasks()
        self.hwnd = user32.GetAncestor(root.winfo_id(), GA_ROOT)
        self._apply_window_styles()
        if args.preview:
            root.after(100, lambda: self.show([part.strip() for part in args.preview.split("+")]))
        else:
            root.after(POLL_MS, self._poll)

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
        width, height = draw_combo(self.canvas, labels, self.theme, self.args.font_size, self.scale)
        left, _, _, bottom = primary_work_area()
        margin = round(self.args.margin * self.scale)
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
    p.add_argument("--theme", choices=sorted(THEMES),
                   help=f"color theme (default: last choice, else {DEFAULT_THEME})")
    p.add_argument("--combos-only", action="store_true", default=None,
                   help="only show when Ctrl/Alt/Win is held, so plain typing (e.g. passwords) is never displayed")
    p.add_argument("--no-dialog", action="store_true",
                   help="skip the start-up dialog (for auto-start); uses the last saved choice")
    p.add_argument("--preview", metavar="COMBO",
                   help='only draw this combo, without hooking the keyboard, e.g. "Ctrl+Shift+Z" (theme preview)')
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = p.parse_args(argv)
    args.opacity = min(1.0, max(0.1, args.opacity))
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    enable_dpi_awareness()
    root = tk.Tk()
    root.title("Key Overlay")
    root.withdraw()
    scale = root.winfo_fpixels("1i") / 96

    mutex = acquire_single_instance()
    if mutex is None:
        if not args.no_dialog:
            messagebox.showinfo("Key Overlay", f"Key Overlay 已經在執行中。\n\n要關閉請按 {QUIT_HINT}。")
        return 0

    saved = load_settings()
    if args.theme is None:
        args.theme = saved.get("theme") if saved.get("theme") in THEMES else DEFAULT_THEME
    if args.combos_only is None:
        args.combos_only = bool(saved.get("combos_only", False))

    if not args.no_dialog and not args.preview:
        choice = ask_start(root, args.theme, args.combos_only, scale)
        if choice is None:
            return 0
        args.theme, args.combos_only = choice["theme"], choice["combos_only"]
        save_settings(choice)

    hook = KeyboardHook()
    if not args.preview:
        hook.start()
        hook.ready.wait(5)
        if hook.error is not None or not hook.ready.is_set():
            messagebox.showerror("Key Overlay", f"無法安裝鍵盤 hook（Win32 error {hook.error}）。")
            return 1

    Overlay(root, hook, args, scale)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
