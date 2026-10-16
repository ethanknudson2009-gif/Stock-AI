"""Generate the pixel-art STOCK//AI wordmark (assets/logo_{dark,light}.svg).

Letters are drawn as squares from a 5x7 bitmap font, so the logo is crisp at any
size and needs no web font. Colors come from ui/theme.py tokens.
Run: python scripts/make_logo.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ui.theme import TOKENS  # noqa: E402

GLYPHS = {
    "S": [".###.", "#...#", "#....", ".###.", "....#", "#...#", ".###."],
    "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "C": [".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."],
    "K": ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
    "/": ["....#", "...#.", "...#.", "..#..", ".#...", ".#...", "#...."],
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "I": [".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."],
}
PX = 4  # pixel size


def svg(text_color: str, accent: str) -> str:
    word = "STOCK//AI"
    rects, x = [], 0
    for ch in word:
        color = accent if ch == "/" else text_color
        for r, row in enumerate(GLYPHS[ch]):
            for c, cell in enumerate(row):
                if cell == "#":
                    rects.append(f'<rect x="{(x + c) * PX}" y="{r * PX}" width="{PX}" height="{PX}" fill="{color}"/>')
        x += 6
    w, h = (x - 1) * PX, 7 * PX
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" shape-rendering="crispEdges">{"".join(rects)}</svg>'


if __name__ == "__main__":
    (ROOT / "assets").mkdir(exist_ok=True)
    for name, t in TOKENS.items():
        (ROOT / "assets" / f"logo_{name}.svg").write_text(svg(t["text"], t["accent"]))
        print("wrote", f"assets/logo_{name}.svg")
