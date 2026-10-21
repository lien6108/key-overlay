"""Virtual-key naming and pressed-key state.

Kept free of Win32 calls so it can be unit tested on any platform.
"""

from __future__ import annotations

import itertools
from typing import Callable

# Display order for modifiers: Win, Ctrl, Alt, Shift (matches Windows docs, e.g. "Win + Shift + S").
MODIFIER_ORDER = ("Win", "Ctrl", "Alt", "Shift")

MODIFIER_VKS = {
    0x10: "Shift", 0xA0: "Shift", 0xA1: "Shift",
    0x11: "Ctrl", 0xA2: "Ctrl", 0xA3: "Ctrl",
    0x12: "Alt", 0xA4: "Alt", 0xA5: "Alt",
    0x5B: "Win", 0x5C: "Win",
}

NAMED_VKS = {
    0x08: "Backspace", 0x09: "Tab", 0x0D: "Enter", 0x13: "Pause", 0x14: "CapsLock",
    0x1B: "Esc", 0x20: "Space", 0x21: "PgUp", 0x22: "PgDn", 0x23: "End", 0x24: "Home",
    0x25: "←", 0x26: "↑", 0x27: "→", 0x28: "↓", 0x2C: "PrtSc", 0x2D: "Insert", 0x2E: "Del",
    0x5D: "Menu",
    0x6A: "Num*", 0x6B: "Num+", 0x6D: "Num-", 0x6E: "Num.", 0x6F: "Num/",
    0x90: "NumLock", 0x91: "ScrollLock",
    0xAD: "Mute", 0xAE: "Vol-", 0xAF: "Vol+", 0xB0: "Next", 0xB1: "Prev", 0xB3: "Play/Pause",
    # OEM keys, US layout labels.
    0xBA: ";", 0xBB: "=", 0xBC: ",", 0xBD: "-", 0xBE: ".", 0xBF: "/", 0xC0: "`",
    0xDB: "[", 0xDC: "\\", 0xDD: "]", 0xDE: "'",
}

# IME processing / reserved codes that carry no useful label.
IGNORED_VKS = {0xE5, 0xFF}


def vk_label(vk: int) -> str:
    if vk in MODIFIER_VKS:
        return MODIFIER_VKS[vk]
    if vk in NAMED_VKS:
        return NAMED_VKS[vk]
    if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:
        return chr(vk)
    if 0x60 <= vk <= 0x69:
        return f"Num{vk - 0x60}"
    if 0x70 <= vk <= 0x87:
        return f"F{vk - 0x6F}"
    return f"0x{vk:02X}"


def is_modifier(vk: int) -> bool:
    return vk in MODIFIER_VKS


class KeyState:
    """Tracks which keys are physically held, in press order."""

    def __init__(self) -> None:
        self._held: dict[int, tuple[int, float]] = {}  # vk -> (press sequence, press time)
        self._seq = itertools.count()

    def press(self, vk: int, now: float = 0.0) -> bool:
        """Record a key-down. Returns False for auto-repeat and ignored keys."""
        if vk in IGNORED_VKS or vk in self._held:
            return False
        self._held[vk] = (next(self._seq), now)
        return True

    def release(self, vk: int) -> None:
        self._held.pop(vk, None)

    def prune(self, is_down: Callable[[int], bool], now: float, min_age: float) -> None:
        """Drop keys whose key-up was missed (e.g. lock screen, UAC prompt)."""
        for vk, (_, pressed_at) in list(self._held.items()):
            if now - pressed_at >= min_age and not is_down(vk):
                del self._held[vk]

    def empty(self) -> bool:
        return not self._held

    def labels(self) -> list[str]:
        held = sorted(self._held, key=lambda vk: self._held[vk][0])
        mods = {MODIFIER_VKS[vk] for vk in held if is_modifier(vk)}
        result = [m for m in MODIFIER_ORDER if m in mods]
        for vk in held:
            if not is_modifier(vk):
                label = vk_label(vk)
                if label not in result:
                    result.append(label)
        return result

    def has_command_modifier(self) -> bool:
        """True when Ctrl/Alt/Win is held, i.e. the keys form a shortcut rather than typing."""
        return any(MODIFIER_VKS.get(vk) in ("Ctrl", "Alt", "Win") for vk in self._held)


def format_combo(labels: list[str]) -> str:
    return " + ".join(labels)
