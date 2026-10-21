"""Start-up dialog: confirm running, pick a theme, explain how to quit. Also persists the choice."""

from __future__ import annotations

import json
import os
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from .render import DEFAULT_THEME, THEMES, draw_combo

QUIT_HINT = "Ctrl + Alt + Shift + Q"
SETTINGS_PATH = Path(os.environ.get("APPDATA", Path.home())) / "KeyOverlay" / "settings.json"


def load_settings() -> dict:
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_settings(settings: dict) -> None:
    try:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def ask_start(root: tk.Tk, theme: str, combos_only: bool, scale: float) -> dict | None:
    """Show the modal launcher. Returns {"theme", "combos_only"} or None when cancelled."""
    win = tk.Toplevel(root)
    win.title("Key Overlay")
    win.resizable(False, False)
    win.attributes("-topmost", True)
    result: dict | None = None

    theme_var = tk.StringVar(value=theme if theme in THEMES else DEFAULT_THEME)
    combos_var = tk.BooleanVar(value=combos_only)

    body = ttk.Frame(win, padding=round(20 * scale))
    body.pack(fill="both", expand=True)
    ttk.Label(body, text="Key Overlay", font=("Segoe UI Semibold", 16)).pack(anchor="w")
    ttk.Label(body, text="在螢幕左下角即時顯示你按下的按鍵，同時按的鍵會用 + 相連。",
              font=("Microsoft JhengHei UI", 10)).pack(anchor="w", pady=(2, 14))

    ttk.Label(body, text="顯示顏色", font=("Microsoft JhengHei UI", 10, "bold")).pack(anchor="w")
    themes_frame = ttk.Frame(body)
    themes_frame.pack(anchor="w", pady=(4, 12))
    for row, (key, spec) in enumerate(THEMES.items()):
        ttk.Radiobutton(themes_frame, text=spec["name"], value=key, variable=theme_var).grid(
            row=row, column=0, sticky="w", padx=(0, 12), pady=3)
        sample = tk.Canvas(themes_frame, highlightthickness=0, bd=0, cursor="hand2")
        draw_combo(sample, ["Ctrl", "Shift", "Z"], spec, 11, scale)
        sample.grid(row=row, column=1, sticky="w", pady=3)
        sample.bind("<Button-1>", lambda _e, k=key: theme_var.set(k))

    ttk.Checkbutton(body, text="只顯示快捷鍵（按住 Ctrl / Alt / Win 時才顯示，一般打字與密碼不會出現）",
                    variable=combos_var).pack(anchor="w", pady=(0, 12))

    quit_box = ttk.LabelFrame(body, text=" 如何關閉 ", padding=round(10 * scale))
    quit_box.pack(fill="x", pady=(0, 16))
    ttk.Label(quit_box, text=f"任何時候按下  {QUIT_HINT}  即可結束程式。",
              font=("Microsoft JhengHei UI", 10, "bold")).pack(anchor="w")
    ttk.Label(quit_box, text="也可以在工作管理員中結束 KeyOverlay.exe。",
              font=("Microsoft JhengHei UI", 9)).pack(anchor="w", pady=(2, 0))

    def start(_event=None) -> None:
        nonlocal result
        result = {"theme": theme_var.get(), "combos_only": combos_var.get()}
        win.destroy()

    buttons = ttk.Frame(body)
    buttons.pack(anchor="e")
    ttk.Button(buttons, text="取消", command=win.destroy).pack(side="left", padx=(0, 8))
    start_btn = ttk.Button(buttons, text="開始執行", command=start, default="active")
    start_btn.pack(side="left")
    win.bind("<Return>", start)
    win.bind("<Escape>", lambda _e: win.destroy())

    win.update_idletasks()
    x = (win.winfo_screenwidth() - win.winfo_reqwidth()) // 2
    y = (win.winfo_screenheight() - win.winfo_reqheight()) // 2
    win.geometry(f"+{x}+{y}")
    win.focus_force()
    start_btn.focus_set()
    win.wait_window()
    return result
