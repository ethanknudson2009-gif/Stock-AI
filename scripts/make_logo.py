"""Generate the Stock AI logo: a robot-magnifier mark + clean wordmark.

Writes assets/logo_{dark,light}.svg (mark + wordmark) and assets/mark_{dark,light}.svg
(mark only, for compact/mobile spots). Colors come from ui/theme.py tokens.
Run: python scripts/make_logo.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ui.theme import TOKENS  # noqa: E402

FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Helvetica, Arial, sans-serif"


def mark(accent: str, eye: str) -> str:
    """64×64 mark: open ring (gaps top-left and right), antenna, eyes, magnifier handle."""
    return (
        f'<g fill="none" stroke="{accent}" stroke-linecap="round">'
        # ring split in two arcs, centered (30,30) r=17
        '<path d="M31.48 13.06 A17 17 0 0 1 45.97 24.19" stroke-width="5.5"/>'
        '<path d="M46.42 34.40 A17 17 0 1 1 20.25 16.07" stroke-width="5.5"/>'
        # antenna stem
        '<path d="M30 13 V8.5" stroke-width="4.5"/>'
        # magnifier neck + grip
        '<path d="M42 42 L50 50" stroke-width="5.5"/>'
        '<path d="M50.5 50.5 L57 57" stroke-width="9.5"/></g>'
        f'<circle cx="30" cy="5.6" r="4.4" fill="{accent}"/>'
        f'<ellipse cx="24.8" cy="30" rx="3.1" ry="4.4" fill="{eye}"/>'
        f'<ellipse cx="35.2" cy="30" rx="3.1" ry="4.4" fill="{eye}"/>'
    )


def logo(text: str, accent: str, eye: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="224" height="64" viewBox="0 0 224 64">'
        f"{mark(accent, eye)}"
        f'<text x="74" y="43" font-family="{FONT}" font-size="31" font-weight="700" letter-spacing="-0.6">'
        f'<tspan fill="{text}">Stock</tspan><tspan fill="{accent}" dx="7">AI</tspan></text></svg>'
    )


def mark_only(accent: str, eye: str) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">{mark(accent, eye)}</svg>'


if __name__ == "__main__":
    (ROOT / "assets").mkdir(exist_ok=True)
    for name, t in TOKENS.items():
        (ROOT / "assets" / f"logo_{name}.svg").write_text(logo(t["text"], t["accent"], t["text"]))
        (ROOT / "assets" / f"mark_{name}.svg").write_text(mark_only(t["accent"], t["text"]))
        print("wrote", f"assets/logo_{name}.svg", f"assets/mark_{name}.svg")
