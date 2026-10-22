"""Win32 helpers shared by the overlay windows: click-through topmost styling and the work area."""

from __future__ import annotations

import ctypes
import tkinter as tk
from ctypes import wintypes

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
GA_ROOT = 2
HWND_TOPMOST = -1
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x0001, 0x0002, 0x0010
SPI_GETWORKAREA = 0x0030

COLORKEY = "#010203"  # painted pixels in this color become fully transparent

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT, ctypes.c_void_p, wintypes.UINT]


def primary_work_area() -> tuple[int, int, int, int]:
    """(left, top, right, bottom) of the primary monitor excluding the taskbar."""
    rect = wintypes.RECT()
    user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
    return rect.left, rect.top, rect.right, rect.bottom


def prepare_overlay_window(window: tk.Tk | tk.Toplevel) -> int:
    """Make `window` borderless, color-keyed transparent and topmost; returns its HWND.

    The window is mapped (at 1x1) so the HWND exists; callers set the real geometry later.
    """
    window.overrideredirect(True)
    window.configure(bg=COLORKEY)
    window.attributes("-transparentcolor", COLORKEY)
    window.attributes("-topmost", True)
    window.attributes("-alpha", 0.0)
    window.geometry("1x1+0+0")
    window.deiconify()
    window.update_idletasks()
    hwnd = user32.GetAncestor(window.winfo_id(), GA_ROOT)
    apply_click_through(hwnd)
    return hwnd


def apply_click_through(hwnd: int) -> None:
    """Mouse passes through, never takes focus, hidden from the taskbar and Alt+Tab."""
    style = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    style |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
    user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style)


def place_window(window: tk.Tk | tk.Toplevel, hwnd: int, x: int, y: int, width: int, height: int) -> None:
    """Size, move and pin `window` on top.

    Tk's `wm geometry` ignores a request that only changes the position while the size stays
    the same, so the final position is set through Win32; Tk picks it up from WM_MOVE.
    """
    window.geometry(f"{width}x{height}+{x}+{y}")
    window.update_idletasks()
    apply_click_through(hwnd)  # Tk may reset the ex-style when it reconfigures the window
    user32.SetWindowPos(hwnd, HWND_TOPMOST, x, y, width, height, SWP_NOACTIVATE)
