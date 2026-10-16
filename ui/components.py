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


def ticker_grid(quotes: list[dict], theme_name: str = "dark") -> None:
    """Responsive grid of ticker cards; each card opens Single Ticker with it preloaded."""
    if not quotes:
        st.info("Market data is unavailable right now — try Refresh in a moment.")
        return
    cards = []
    for i, q in enumerate(quotes):
        kind = "up" if q["pct"] >= 0 else "down"
        sign = "+" if q["pct"] >= 0 else "−"
        sym = escape(q["ticker"])
        cards.append(
            f'<a class="tcard" href="/single_ticker?ticker={sym}&theme={theme_name}" target="_self" '
            f'title="Analyze {sym}"><div class="row"><span class="sym">{sym}</span>'
            f'<span class="pill {kind}">{sign}{abs(q["pct"]):.2f}%</span></div>'
            f'<div class="px">${q["last"]:,.2f}</div>{_sparkline(q["spark"], kind, f"sp{i}")}</a>'
        )
    _html(f'<div class="tgrid">{"".join(cards)}</div>')


def skeleton_grid(n: int = 8) -> str:
    """Shimmering placeholder cards shown while market data loads (returns markup)."""
    cell = ('<div class="tcard sk"><div class="row"><span class="sk-bar w40"></span>'
            '<span class="sk-bar w25"></span></div><div class="sk-bar w60 tall"></div>'
            '<div class="sk-bar w100 spark-h"></div></div>')
    return f'<div class="tgrid">{cell * n}</div>'


def signal_card(state: str, prob: float, adjusted: float, threshold: float, applies_to: str,
                explanation: str) -> None:
    """Today's model call. state ∈ {'buy','sell','none'}; 'none' = the model has no proven edge here.

    `prob` is the raw P(up); `adjusted` is P(up) minus the historical up-frequency — the part
    of the confidence that is information rather than the stock's usual drift.
    """
    label = {"buy": "Buy", "sell": "Sell", "none": "No edge"}[state]
    sub = ('<div class="sig-sub">The model has not beaten the base rate here, so it issues no call.</div>'
           if state == "none" else "")
    _html(
        f'<div class="signal {state}"><div class="sig-main"><span class="eyebrow">Today\'s signal</span>'
        f'<div class="sig-action">{label}</div>{sub}'
        f'<p class="sig-expl">{escape(explanation)}</p></div>'
        f'<div class="sig-side"><div class="sig-k">Raw P(up)</div>'
        f'<div class="sig-v">{prob:.0%}</div>'
        f'<div class="meter"><span style="width:{prob * 100:.0f}%"></span>'
        f'<i style="left:{threshold * 100:.0f}%"></i></div>'
        f'<div class="sig-k">Base-rate-adjusted: <b class="{"up" if adjusted > 0 else "down"}">{adjusted:+.1%}</b> '
        f'vs the stock\'s usual up-frequency</div>'
        f'<div class="sig-k">threshold {threshold:.0%} · applies to {escape(applies_to)}</div></div></div>'
    )


def verdict_banner(items: list[tuple[str, bool, str]]) -> None:
    """Plain-language yes/no checks above the stats. items: [(question, answer, detail)]."""
    cells = "".join(
        f'<div class="vq {"yes" if ok else "no"}"><span class="q">{escape(q)}</span>'
        f'<span class="a">{"Yes" if ok else "No"}</span><span class="d">{escape(d)}</span></div>'
        for q, ok, d in items)
    _html(f'<div class="vbanner">{cells}</div>')


def skeleton_results() -> str:
    """Placeholder for a results page while models train (returns markup)."""
    return ('<div class="sk-page"><div class="sk-bar w60 tall"></div><div class="sk-bar w100 spark-h"></div>'
            '<div class="stats">' + '<div class="stat"><div class="sk-bar w40"></div>'
            '<div class="sk-bar w60 tall"></div></div>' * 4 + '</div><div class="sk-bar w100 chart-h"></div></div>')


def banner(kind: str, title: str, body: str, icon: str = "") -> None:
    """Prominent status banner. kind ∈ {'warn','danger','info'}."""
    ic = f'<span class="ms">{escape(icon)}</span>' if icon else ""
    _html(f'<div class="banner {kind}">{ic}<div><b>{escape(title)}</b><span>{escape(body)}</span></div></div>')


def note(text: str) -> None:
    """Small always-visible caveat line (e.g. survivorship bias)."""
    _html(f'<div class="note"><span class="ms">info</span>{escape(text)}</div>')


def data_table(headers: list[str], rows: list[list[str]], highlight: int | None = 0,
               tones: list[list[str]] | None = None) -> None:
    """Clean HTML table; `highlight` row index gets the accent treatment."""
    head = "".join(f"<th>{escape(h)}</th>" for h in headers)
    body = []
    for r, row in enumerate(rows):
        cls = ' class="hl"' if r == highlight else ""
        cells = "".join(
            f'<td class="{(tones[r][c] if tones else "")}">{escape(v)}</td>' for c, v in enumerate(row))
        body.append(f"<tr{cls}>{cells}</tr>")
    _html(f'<div class="dtable-wrap"><table class="dtable"><thead><tr>{head}</tr></thead>'
          f'<tbody>{"".join(body)}</tbody></table></div>')


def confusion_matrix(conf: dict) -> None:
    """2×2 confusion matrix of predicted vs actual direction."""
    tp, fp, fn, tn = conf["tp"], conf["fp"], conf["fn"], conf["tn"]
    _html(
        '<table class="cm"><tr><th></th><th>Actually up</th><th>Actually down</th></tr>'
        f'<tr><th>Predicted up</th><td class="good">{tp}<small>correct</small></td>'
        f'<td class="bad">{fp}<small>false alarm</small></td></tr>'
        f'<tr><th>Predicted down</th><td class="bad">{fn}<small>missed</small></td>'
        f'<td class="good">{tn}<small>correct</small></td></tr></table>'
    )


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
