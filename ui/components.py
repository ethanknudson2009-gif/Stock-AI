"""Reusable UI building blocks. Styling lives in ui/theme.py (CSS classes + vars)."""

from html import escape

import streamlit as st


def _html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def page_head(title: str, subtitle: str, eyebrow: str = "") -> None:
    """Compact title block for inner pages, with an optional accent eyebrow label."""
    eb = f'<span class="eyebrow">{escape(eyebrow)}</span>' if eyebrow else ""
    _html(f'<div class="page-head">{eb}<h1>{escape(title)}</h1><p>{escape(subtitle)}</p></div>')


def hero(before: str, accent: str, after: str, subtitle: str,
         chips: list[tuple[str, str, str]] | None = None) -> None:
    """Centered home hero; `accent` is set in italic accent color with an underline.

    chips: [(dot_class, label, value)] rendered as a summary strip.
    """
    strip = ""
    if chips:
        strip = '<div class="summary">' + "".join(
            f'<span class="chip"><span class="dot {d}"></span>{escape(label)} <b>{escape(value)}</b></span>'
            for d, label, value in chips
        ) + "</div>"
    title = f"{escape(before)} <em>{escape(accent)}</em>{escape(after)}"
    _html(f'<div class="hero"><h1>{title}</h1><p>{escape(subtitle)}</p>{strip}</div>')


def section(title: str, meta: str = "", eyebrow: str = "", center: bool = False) -> None:
    """Section heading. center=True gives the large centered marketing-style heading."""
    eb = f'<span class="eyebrow">{escape(eyebrow)}</span>' if eyebrow else ""
    cls = "section-title center" if center else "section-title"
    _html(f'<div class="{cls}">{eb}<h2>{escape(title)}</h2><div class="meta">{escape(meta)}</div></div>')


def tone(x: float) -> str:
    return "up" if x > 0 else ("down" if x < 0 else "")


def stat_grid(items: list[tuple[str, str, str]]) -> None:
    """Metric tiles. items: [(label, value, tone)] where tone ∈ {'up','down','accent',''}."""
    cells = "".join(
        f'<div class="stat"><div class="k">{escape(k)}</div><div class="v {t}">{escape(v)}</div></div>'
        for k, v, t in items
    )
    _html(f'<div class="stats">{cells}</div>')


def _sparkline(values: list[float], kind: str, uid: str) -> str:
    if not values or len(values) < 2:
        return ""
    w, h = 200, 40
    lo, hi = min(values), max(values)
    rng = (hi - lo) or 1.0
    n = len(values)
    pts = [(i / (n - 1) * w, h - 2 - (v - lo) / rng * (h - 4)) for i, v in enumerate(values)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    var = f"var(--{kind})"
    return (
        f'<svg class="spark" viewBox="0 0 {w} {h}" preserveAspectRatio="none">'
        f'<defs><linearGradient id="{uid}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" style="stop-color:{var};stop-opacity:0.22"/>'
        f'<stop offset="100%" style="stop-color:{var};stop-opacity:0"/></linearGradient></defs>'
        f'<polygon points="0,{h} {line} {w},{h}" style="fill:url(#{uid})"/>'
        f'<polyline points="{line}" style="fill:none;stroke:{var};stroke-width:1.6;'
        f'vector-effect:non-scaling-stroke;stroke-linejoin:round"/></svg>'
    )


def ticker_grid(quotes: list[dict]) -> None:
    """Responsive grid of ticker cards (symbol, price, % pill, sparkline)."""
    if not quotes:
        st.info("Market data is unavailable right now — try again in a moment.")
        return
    cards = []
    for i, q in enumerate(quotes):
        kind = "up" if q["pct"] >= 0 else "down"
        sign = "+" if q["pct"] >= 0 else "−"
        cards.append(
            f'<div class="tcard"><div class="row"><span class="sym">{escape(q["ticker"])}</span>'
            f'<span class="pill {kind}">{sign}{abs(q["pct"]):.2f}%</span></div>'
            f'<div class="px">${q["last"]:,.2f}</div>{_sparkline(q["spark"], kind, f"sp{i}")}</div>'
        )
    _html(f'<div class="tgrid">{"".join(cards)}</div>')


def nav_card(key: str, page: str, icon: str, title: str, desc: str) -> None:
    """Whole-card-clickable link to another page (page_link stretched over the card)."""
    with st.container(key=f"navcard_{key}"):
        _html(f'<div class="navicon"><span class="ms">{escape(icon)}</span></div>')
        st.page_link(page, label=title)
        _html(f'<p class="navdesc">{escape(desc)}</p><div class="navarrow">→</div>')


def verdict(text: str, positive: bool) -> None:
    _html(f'<div class="verdict {"up" if positive else "down"}">{escape(text)}</div>')


def footer() -> None:
    with st.container(key="app_footer"):
        _html('<div class="footer">Educational tool — not financial advice. '
              'Backtests are hypothetical and survivorship-biased.</div>')
