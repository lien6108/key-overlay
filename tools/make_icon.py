"""Generate key_overlay/assets/icon.ico (a yellow keycap with a "K") without third-party libraries.

Run: python tools/make_icon.py
"""

from __future__ import annotations

import struct
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "key_overlay" / "assets" / "icon.ico"
SIZES = (16, 24, 32, 48, 64)

KEYCAP = (0xFF, 0xD6, 0x0A, 0xFF)
EDGE = (0x11, 0x11, 0x11, 0xFF)
CLEAR = (0, 0, 0, 0)
GLYPH_K = (
    "X...X",
    "X..X.",
    "X.X..",
    "XX...",
    "X.X..",
    "X..X.",
    "X...X",
)


def render(n: int) -> list[list[tuple[int, int, int, int]]]:
    px = [[CLEAR] * n for _ in range(n)]
    radius = max(2, n // 6)
    border = max(1, n // 16)

    def inside(x: int, y: int, inset: int) -> bool:
        lo, hi = inset, n - 1 - inset
        r = max(0, radius - inset)
        if not (lo <= x <= hi and lo <= y <= hi):
            return False
        cx = min(max(x, lo + r), hi - r)
        cy = min(max(y, lo + r), hi - r)
        return (x - cx) ** 2 + (y - cy) ** 2 <= r * r

    for y in range(n):
        for x in range(n):
            if inside(x, y, border):
                px[y][x] = KEYCAP
            elif inside(x, y, 0):
                px[y][x] = EDGE

    scale = max(1, (n * 9 // 16) // 7)
    gw, gh = 5 * scale, 7 * scale
    ox, oy = (n - gw) // 2, (n - gh) // 2
    for gy, row in enumerate(GLYPH_K):
        for gx, cell in enumerate(row):
            if cell == "X":
                for dy in range(scale):
                    for dx in range(scale):
                        px[oy + gy * scale + dy][ox + gx * scale + dx] = EDGE
    return px


def bmp_entry(n: int) -> bytes:
    px = render(n)
    header = struct.pack("<IiiHHIIiiII", 40, n, n * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    xor = b"".join(bytes((b, g, r, a)) for row in reversed(px) for (r, g, b, a) in row)
    and_row = ((n + 31) // 32) * 4
    return header + xor + b"\x00" * and_row * n


def main() -> None:
    images = [bmp_entry(n) for n in SIZES]
    out = struct.pack("<HHH", 0, 1, len(SIZES))
    offset = 6 + 16 * len(SIZES)
    for n, data in zip(SIZES, images):
        out += struct.pack("<BBBBHHII", n % 256, n % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(out + b"".join(images))
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
