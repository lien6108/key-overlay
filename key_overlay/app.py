"""On-screen overlay showing the key combination currently being pressed, plus an optional
virtual keyboard that lights up held keys. Both sit in a screen corner of the user's choice."""

from __future__ import annotations

import argparse
import collections
import ctypes
import queue
import sys
import threading
import time
import tkinter as tk
from ctypes import wintypes
from tkinter import messagebox
from typing import NamedTuple

from . import __version__
from .hook import KeyboardHook, is_key_down
from .keyboard import VirtualKeyboard
from .keys import KeyState
from .launcher import QUIT_HINT, ask_start, load_settings, save_settings
from .layout import DEFAULT_POSITION, POSITIONS, corner_origin
from .render import DEFAULT_THEME, THEMES, draw_combo
from .tray import ICON_PATH, TRAY_STARTUP_TIMEOUT_S, TrayIcon
from .winapi import COLORKEY, place_window, prepare_overlay_window, primary_work_area

QUIT_LABELS = ["Ctrl", "Alt", "Shift", "Q"]
PRUNE_EVERY_MS = 1000
PRUNE_MIN_AGE_S = 1.0
FADE_STEPS = 8
FADE_STEP_MS = 25
STACK_GAP_PX = 8  # space between the virtual keyboard and the combo panel
ERROR_ALREADY_EXISTS = 183

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CreateMutexW.restype = wintypes.HANDLE


class TrayCommand(NamedTuple):
    """Queued by the tray thread alongside the hook's (vk, is_down) tuples."""
    name: str
    value: str | None = None


def enable_dpi_awareness() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def acquire_single_instance():
    handle = kernel32.CreateMutexW(None, False, "Local\\key-overlay-single-instance")
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        return None
    return handle


class EventRelay(threading.Thread):
    """Blocks on the input queue and wakes the Tk thread only when something arrives,
    so the UI thread sleeps while idle instead of polling."""

    def __init__(self, root: tk.Tk, source: queue.SimpleQueue) -> None:
        super().__init__(name="event-relay", daemon=True)
        self.root = root
        self.source = source
        self.pending: collections.deque = collections.deque()

    def run(self) -> None:
        while True:
            self.pending.append(self.source.get())
            try:
                self.root.event_generate("<<Input>>", when="tail")
            except (RuntimeError, tk.TclError):
                return  # UI is gone


class Overlay:
    def __init__(self, root: tk.Tk, hook: KeyboardHook, tray: TrayIcon,
                 args: argparse.Namespace, settings: dict, scale: float) -> None:
        self.root = root
        self.hook = hook
        self.tray = tray
        self.args = args
        self.settings = settings  # persisted view: theme, combos_only, position, keyboard
        self.scale = scale
        self.state = KeyState()
        self.theme = THEMES[args.theme]
        self.hide_job: str | None = None
        self.fade_job: str | None = None
        self.prune_job: str | None = None
        self.combo_size: tuple[int, int] | None = None  # size of the panel currently on screen
        self.relay = EventRelay(root, hook.events)

        self.hwnd = prepare_overlay_window(root)
        self.canvas = tk.Canvas(root, bg=COLORKEY, highlightthickness=0, bd=0)
        self.canvas.pack()
        self.keyboard = VirtualKeyboard(root, self.theme, args.font_size, scale, args.opacity)
        if settings.get("keyboard"):
            self._place_keyboard()

        root.bind("<<Input>>", self._on_input)
        root.after(0, self.relay.start)  # start once mainloop runs, so cross-thread calls are accepted
        if args.preview:
            root.after(100, lambda: self.show([part.strip() for part in args.preview.split("+")]))

    # ----- input -----

    def _on_input(self, _event=None) -> None:
        now = time.monotonic()
        changed = False
        released = False
        while self.relay.pending:
            item = self.relay.pending.popleft()
            if isinstance(item, TrayCommand):
                if not self._run_command(item):
                    return  # quit
                continue
            vk, is_down = item
            if is_down:
                changed |= self.state.press(vk, now)
            else:
                self.state.release(vk)
                released = True

        if changed:
            labels = self.state.labels()
            if labels == QUIT_LABELS:
                self.quit()
                return
            if self.state.should_display(self.args.combos_only):
                self.show(labels)
        if released and self.state.empty():
            self._schedule_hide()
        if not self.state.empty() and self.prune_job is None:
            self.prune_job = self.root.after(PRUNE_EVERY_MS, self._prune_tick)
        self._refresh_keyboard()

    def _prune_tick(self) -> None:
        """Runs only while keys are held, to recover from key-ups Windows never delivered."""
        self.prune_job = None
        if self.state.empty():
            return
        self.state.prune(is_key_down, time.monotonic(), PRUNE_MIN_AGE_S)
        if self.state.empty():
            self._schedule_hide()
        else:
            self.prune_job = self.root.after(PRUNE_EVERY_MS, self._prune_tick)
        self._refresh_keyboard()

    def _run_command(self, cmd: TrayCommand) -> bool:
        """Apply a tray menu pick. Returns False once the app is quitting."""
        if cmd.name == "quit":
            self.quit()
            return False
        if cmd.name == "toggle_keyboard":
            self._remember("keyboard", not self.keyboard.visible)
            if self.keyboard.visible:
                self.keyboard.hide()
            else:
                self._place_keyboard()
            self._replace_combo()
        elif cmd.name == "position" and cmd.value in POSITIONS:
            self._remember("position", cmd.value)
            if self.keyboard.visible:
                self._place_keyboard()
            self._replace_combo()
        return True

    def _remember(self, key: str, value) -> None:
        """Persist one changed setting without turning this run's command-line flags into defaults."""
        self.settings[key] = value
        save_settings({**load_settings(), key: value})

    # ----- placement -----

    @property
    def position(self) -> str:
        return self.settings.get("position", DEFAULT_POSITION)

    def _margin(self) -> int:
        return round(self.args.margin * self.scale)

    def _place_keyboard(self) -> None:
        x, y = corner_origin(self.position, primary_work_area(),
                             (self.keyboard.width, self.keyboard.height), self._margin())
        self.keyboard.show_at(x, y)
        self._refresh_keyboard()

    def _combo_origin(self, size: tuple[int, int]) -> tuple[int, int]:
        offset = self.keyboard.height + round(STACK_GAP_PX * self.scale) if self.keyboard.visible else 0
        return corner_origin(self.position, primary_work_area(), size, self._margin(), offset)

    def _replace_combo(self) -> None:
        """Move the combo panel if one is on screen (position or keyboard visibility changed)."""
        if self.combo_size is None:
            return
        x, y = self._combo_origin(self.combo_size)
        place_window(self.root, self.hwnd, x, y, *self.combo_size)

    def _refresh_keyboard(self) -> None:
        if self.keyboard.visible:
            self.keyboard.light(self.state.visible_vks(self.args.combos_only))

    # ----- combo panel -----

    def show(self, labels: list[str]) -> None:
        self._cancel_jobs()
        size = draw_combo(self.canvas, labels, self.theme, self.args.font_size, self.scale)
        self.combo_size = size
        x, y = self._combo_origin(size)
        self.root.attributes("-alpha", self.args.opacity)
        place_window(self.root, self.hwnd, x, y, *size)

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
            self.combo_size = None

    def _cancel_jobs(self) -> None:
        for job in (self.hide_job, self.fade_job):
            if job:
                self.root.after_cancel(job)
        self.hide_job = self.fade_job = None

    def quit(self) -> None:
        self.hook.stop()
        self.tray.stop()
        self.root.destroy()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="key-overlay", description=__doc__)
    p.add_argument("--font-size", type=int, default=20, help="key label font size in pt (default 20)")
    p.add_argument("--hold", type=float, default=1.5, help="seconds to keep showing after release (default 1.5)")
    p.add_argument("--margin", type=int, default=24, help="distance from screen edge in px (default 24)")
    p.add_argument("--opacity", type=float, default=0.92, help="0.1-1.0 (default 0.92)")
    p.add_argument("--theme", choices=sorted(THEMES),
                   help=f"color theme (default: last choice, else {DEFAULT_THEME})")
    p.add_argument("--position", choices=list(POSITIONS),
                   help=f"screen corner (default: last choice, else {DEFAULT_POSITION})")
    p.add_argument("--keyboard", action="store_true", default=None,
                   help="also show a small virtual keyboard that lights up held keys (default: last choice)")
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


def resolve_settings(args: argparse.Namespace, saved: dict) -> dict:
    """Command-line flags win; otherwise the last saved choice; otherwise the default."""
    theme = args.theme or saved.get("theme")
    position = args.position or saved.get("position")
    return {
        "theme": theme if theme in THEMES else DEFAULT_THEME,
        "position": position if position in POSITIONS else DEFAULT_POSITION,
        "combos_only": bool(saved.get("combos_only", False)) if args.combos_only is None else True,
        "keyboard": bool(saved.get("keyboard", False)) if args.keyboard is None else True,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    enable_dpi_awareness()
    root = tk.Tk()
    root.title("Key Overlay")
    root.withdraw()
    try:
        root.iconbitmap(default=str(ICON_PATH))
    except tk.TclError:
        pass
    scale = root.winfo_fpixels("1i") / 96

    mutex = acquire_single_instance()
    if mutex is None:
        if not args.no_dialog:
            messagebox.showinfo("Key Overlay", f"Key Overlay 已經在執行中。\n\n要關閉請按 {QUIT_HINT}。")
        return 0

    settings = resolve_settings(args, load_settings())
    if not args.no_dialog and not args.preview:
        choice = ask_start(root, settings, scale)
        if choice is None:
            return 0
        settings = choice
        save_settings(settings)
    args.theme, args.combos_only = settings["theme"], settings["combos_only"]

    hook = KeyboardHook()
    if not args.preview:
        hook.start()
        hook.ready.wait(5)
        if hook.error is not None or not hook.ready.is_set():
            messagebox.showerror("Key Overlay", f"無法安裝鍵盤 hook（Win32 error {hook.error}）。")
            return 1

    tray = TrayIcon(f"Key Overlay {__version__}（按右鍵開啟選單）",
                    [f"Key Overlay {__version__} 執行中", f"快捷鍵 {QUIT_HINT} 也可結束"],
                    on_command=lambda name, value: hook.events.put(TrayCommand(name, value)),
                    get_state=lambda: dict(settings))
    tray.start()
    if not tray.ready.wait(TRAY_STARTUP_TIMEOUT_S):
        hook.stop()
        tray.stop()
        messagebox.showerror("Key Overlay", "通知區域圖示啟動逾時，請確認 Windows 檔案總管正在執行。")
        return 1
    if tray.error is not None:
        hook.stop()
        tray.stop()
        messagebox.showerror("Key Overlay", f"無法建立右下角圖示：{tray.error}")
        return 1
    Overlay(root, hook, tray, args, settings, scale)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
