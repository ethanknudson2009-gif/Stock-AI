"""Single source of truth for the UI theme.

Every color lives here as a design token. `apply()` injects the active theme's
tokens as CSS variables on :root plus all component styles; everything else in
the UI references `var(--token)` in CSS or `colors()` for Plotly. No other module
hardcodes a color.
"""

import streamlit as st

TOKENS = {
    "dark": {
        "bg": "#050505",
        "surface": "#0e0e0f",
        "surface-2": "#161618",
        "border": "rgba(255,255,255,0.08)",
        "border-strong": "rgba(255,255,255,0.14)",
        "text": "#f5f5f4",
        "text-muted": "#a3a3a3",
        "text-faint": "#6f6f6f",
        "accent": "#f26b3a",
        "accent-text": "#f58250",
        "accent-soft": "rgba(242,107,58,0.10)",
        "accent-border": "rgba(242,107,58,0.38)",
        "glow": "rgba(242,107,58,0.20)",
        "btn-bg": "#ffffff",
        "btn-text": "#0a0a0a",
        "up": "#22c55e",
        "up-soft": "rgba(34,197,94,0.12)",
        "down": "#ef4444",
        "down-soft": "rgba(239,68,68,0.12)",
        "warn": "#f59e0b",
        "header-bg": "rgba(14,14,15,0.72)",
        "grid": "rgba(255,255,255,0.06)",
        "shadow": "0 1px 2px rgba(0,0,0,0.6)",
        "shadow-hover": "0 18px 50px -18px rgba(242,107,58,0.35)",
    },
    "light": {
        "bg": "#faf8f6",
        "surface": "#ffffff",
        "surface-2": "#f4f1ee",
        "border": "#ebe6e1",
        "border-strong": "#dcd5ce",
        "text": "#141210",
        "text-muted": "#5f5852",
        "text-faint": "#948b83",
        "accent": "#f26b3a",
        "accent-text": "#c2410c",
        "accent-soft": "rgba(242,107,58,0.09)",
        "accent-border": "rgba(242,107,58,0.35)",
        "glow": "rgba(242,107,58,0.12)",
        "btn-bg": "#141210",
        "btn-text": "#ffffff",
        "up": "#16a34a",
        "up-soft": "rgba(22,163,74,0.10)",
        "down": "#dc2626",
        "down-soft": "rgba(220,38,38,0.09)",
        "warn": "#d97706",
        "header-bg": "rgba(255,255,255,0.78)",
        "grid": "rgba(20,18,16,0.07)",
        "shadow": "0 1px 2px rgba(20,18,16,0.05)",
        "shadow-hover": "0 18px 50px -20px rgba(242,107,58,0.30)",
    },
}

UI_FONT = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
MONO_FONT = "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"


def init() -> None:
    """Seed the theme choice once per session (honors ?theme=light|dark)."""
    if "light_mode" not in st.session_state:
        st.session_state["light_mode"] = st.query_params.get("theme") == "light"


def current() -> str:
    """Active theme name: 'dark' (default) or 'light'."""
    return "light" if st.session_state.get("light_mode") else "dark"


def colors() -> dict:
    """Concrete values of the active theme (for Plotly, which can't read CSS vars)."""
    return TOKENS[current()]


def logo_path() -> str:
    return f"assets/logo_{current()}.svg"


def style_fig(fig, yaxis_title: str | None = None, height: int = 380):
    """Make a Plotly figure follow the active theme."""
    c = colors()
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=56, t=24, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=UI_FONT, color=c["text-muted"], size=12),
        legend=dict(orientation="h", y=1.04, yanchor="bottom", x=0, bgcolor="rgba(0,0,0,0)"),
        xaxis_title=None,
        yaxis_title=None,
        hoverlabel=dict(bgcolor=c["surface"], bordercolor=c["border"],
                        font=dict(family=MONO_FONT, color=c["text"])),
    )
    fig.update_xaxes(gridcolor=c["grid"], zeroline=False, linecolor=c["border"], automargin=True)
    fig.update_yaxes(gridcolor=c["grid"], zeroline=False, linecolor=c["border"], automargin=True,
                     tickfont=dict(family=MONO_FONT), side="right")
    return fig


def _root_vars(name: str) -> str:
    return "\n".join(f"  --{k}: {v};" for k, v in TOKENS[name].items())


def apply() -> None:
    """Inject the active theme's CSS variables and all component styles."""
    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
:root {{
{_root_vars(current())}
  --s1: 8px; --s2: 16px; --s3: 24px; --s4: 32px; --s5: 40px; --s6: 48px;
  --radius: 16px; --radius-sm: 10px;
  --font-ui: {UI_FONT};
  --font-mono: {MONO_FONT};
}}

/* ---------- Base ---------- */
html, body {{ background: var(--bg) !important; }}
.stApp, [data-testid="stAppViewContainer"] {{
  background:
    radial-gradient(1100px 620px at 15% 105%, var(--glow), transparent 60%),
    radial-gradient(900px 500px at 85% 110%, var(--accent-soft), transparent 60%),
    var(--bg) !important;
  background-attachment: fixed !important; color: var(--text); font-family: var(--font-ui);
}}
.stApp p, .stApp li, .stApp label, .stMarkdown {{ font-family: var(--font-ui); }}
.stApp p, .stApp li {{ color: var(--text); }}
h1, h2, h3, h4 {{ font-family: var(--font-ui) !important; color: var(--text) !important;
  letter-spacing: -0.02em; font-weight: 600 !important; }}
h2 {{ font-size: 1.25rem !important; }} h3 {{ font-size: 1.05rem !important; }}
[data-testid="stCaptionContainer"], .stCaption, small {{ color: var(--text-muted) !important; }}
a {{ color: var(--accent-text); }}
hr {{ border-color: var(--border) !important; }}
.block-container {{ max-width: 1200px; padding: 120px var(--s3) var(--s6) !important; margin: 0 auto; }}
@media (max-width: 640px) {{ .block-container {{ padding: 96px var(--s2) var(--s5) !important; }} }}

/* ---------- Top bar ---------- */
[data-testid="stHeader"] {{ top: 14px !important; left: 50% !important; right: auto !important;
  transform: translateX(-50%); width: min(1120px, calc(100% - 24px)) !important; height: 60px;
  background: var(--header-bg) !important; backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
  border: 1px solid var(--border-strong); border-radius: 18px; box-shadow: 0 10px 30px -12px rgba(0,0,0,0.45); }}
[data-testid="stHeader"] a {{ border-radius: 10px !important; }}
[data-testid="stHeader"] a[aria-current="page"] {{ background: var(--accent-soft) !important; }}
[data-testid="stHeader"] a {{ color: var(--text-muted) !important; }}
[data-testid="stHeader"] a p {{ color: var(--text-muted) !important; font-family: var(--font-ui) !important;
  font-weight: 500; font-size: 0.88rem; }}
[data-testid="stHeader"] a [data-testid="stIconMaterial"] {{ color: var(--text-faint) !important; }}
[data-testid="stHeader"] a[aria-current="page"] p, [data-testid="stHeader"] a:hover p,
[data-testid="stHeader"] a[aria-current="page"] [data-testid="stIconMaterial"] {{ color: var(--text) !important; }}
[data-testid="stMainMenu"], [data-testid="stAppDeployButton"], .stAppDeployButton {{ display: none !important; }}
@media (min-width: 768px) {{ [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {{ display: none !important; }} }}
[data-testid="stSidebar"] {{ background: var(--surface) !important; border-right: 1px solid var(--border); }}
[data-testid="stSidebar"] a p {{ color: var(--text) !important; }}
@media (max-width: 767px) {{
  .st-key-theme_toggle {{ right: 28px !important; top: 30px !important; }}
  [data-testid="stLogo"] {{ max-height: 22px !important; }}
  .tgrid {{ grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)) !important; gap: var(--s1) !important; }}
  .tcard {{ padding: 12px !important; }}
  .tcard .px {{ font-size: 1.05rem !important; }}
}}
.st-key-theme_toggle {{ position: fixed; top: 32px; right: max(32px, calc((100vw - 1120px) / 2 + 20px));
  z-index: 1000002; width: auto !important; }}
.st-key-theme_toggle label p {{ color: var(--text-muted) !important; }}
[data-testid="stStatusWidget"] {{ margin-right: 96px; }}

/* ---------- Inputs ---------- */
[data-testid="stWidgetLabel"] p {{ color: var(--text-muted) !important; font-size: 0.8rem !important; font-weight: 500; }}
[data-testid="stTextInputRootElement"], [data-testid="stTextAreaRootElement"],
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"],
[data-baseweb="select"] > div {{ background: var(--surface-2) !important; border-color: var(--border) !important;
  border-radius: 10px !important; }}
input, textarea {{ color: var(--text) !important; -webkit-text-fill-color: var(--text) !important;
  font-family: var(--font-mono) !important; }}
[data-baseweb="select"] div {{ color: var(--text) !important; }}
[data-baseweb="popover"] ul, [data-baseweb="menu"] {{ background: var(--surface) !important; }}
[data-baseweb="popover"] li {{ color: var(--text) !important; }}
[data-testid="stSliderThumbValue"], [data-testid="stSliderTickBarMin"],
[data-testid="stSliderTickBarMax"] {{ color: var(--text-muted) !important; font-family: var(--font-mono) !important; }}
[data-testid="stForm"] {{ background: var(--surface); border: 1px solid var(--border) !important;
  border-radius: 16px; padding: var(--s3) !important; box-shadow: var(--shadow); }}

/* ---------- Buttons ---------- */
.stButton > button, .stFormSubmitButton > button {{ background: var(--btn-bg) !important;
  color: var(--btn-text) !important; border: none !important; border-radius: 999px !important;
  font-weight: 600; font-family: var(--font-ui); padding: 10px 22px;
  transition: transform .12s ease, filter .15s ease, box-shadow .2s ease; }}
.stButton > button p, .stFormSubmitButton > button p, .stButton > button span,
.stFormSubmitButton > button span {{ color: var(--btn-text) !important; }}
.stButton > button:hover, .stFormSubmitButton > button:hover {{ box-shadow: 0 8px 24px -8px var(--glow); }}
.stButton > button:hover, .stFormSubmitButton > button:hover {{ filter: brightness(1.08); transform: translateY(-1px); }}

/* ---------- Feedback ---------- */
[data-testid="stAlert"] > div {{ background: var(--surface) !important; border: 1px solid var(--border) !important;
  border-radius: var(--radius-sm) !important; color: var(--text) !important; }}
[data-testid="stAlert"] p {{ color: var(--text) !important; }}
[data-testid="stAlert"]:has([data-testid="stAlertContentInfo"]) > div {{ border-left: 3px solid var(--accent) !important; }}
[data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]) > div {{ border-left: 3px solid var(--up) !important; }}
[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) > div {{ border-left: 3px solid var(--warn) !important; }}
[data-testid="stAlert"]:has([data-testid="stAlertContentError"]) > div {{ border-left: 3px solid var(--down) !important; }}
[data-testid="stExpander"] details {{ background: var(--surface); border: 1px solid var(--border) !important;
  border-radius: var(--radius) !important; }}
[data-testid="stExpander"] summary p {{ color: var(--text) !important; }}
[data-testid="stTable"] table {{ border: 1px solid var(--border); border-radius: var(--radius-sm); overflow: hidden;
  font-family: var(--font-mono); font-size: 0.85rem; }}
[data-testid="stTable"] th {{ background: var(--surface-2) !important; color: var(--text-muted) !important; font-weight: 500; }}
[data-testid="stTable"] td {{ color: var(--text) !important; border-color: var(--border) !important; }}
[data-testid="stSpinner"] p {{ color: var(--text-muted) !important; }}

/* ---------- Components ---------- */
.hero {{ padding: var(--s3) 0 var(--s2); text-align: center; }}
.hero h1 {{ font-size: clamp(2.4rem, 5.6vw, 4rem) !important; line-height: 1.05; margin: 0 auto var(--s2) !important;
  letter-spacing: -0.04em; font-weight: 500 !important; max-width: 820px; }}
.hero h1 em {{ font-style: italic; color: var(--accent-text); font-weight: 500;
  background: linear-gradient(var(--accent), var(--accent)) left 100% / 100% 2px no-repeat; padding-bottom: 2px; }}
.hero p {{ color: var(--text-muted) !important; font-size: 1.1rem; margin: 0 auto var(--s3); max-width: 620px; }}
.summary {{ display: flex; flex-wrap: wrap; gap: var(--s1); justify-content: center; }}
.chip {{ display: inline-flex; align-items: center; gap: 6px; padding: 7px 14px; border-radius: 999px;
  background: var(--surface); border: 1px solid var(--border-strong); color: var(--text-muted); font-size: 0.82rem; }}
.chip b {{ font-family: var(--font-mono); font-weight: 600; color: var(--text); }}
.chip .dot {{ width: 7px; height: 7px; border-radius: 50%; display: inline-block; }}
.dot.up {{ background: var(--up); }} .dot.down {{ background: var(--down); }} .dot.accent {{ background: var(--accent); }}

.page-head {{ padding: var(--s1) 0 var(--s3); }}
.eyebrow {{ display: block; color: var(--accent-text); font-size: 0.72rem; font-weight: 600;
  letter-spacing: 0.18em; text-transform: uppercase; margin-bottom: var(--s1); }}
.page-head h1 {{ font-size: clamp(1.6rem, 3vw, 2rem) !important; margin: 0 0 4px !important; letter-spacing: -0.03em; }}
.page-head p {{ color: var(--text-muted) !important; margin: 0; }}
.section-title {{ display: flex; align-items: baseline; justify-content: space-between; gap: var(--s2);
  flex-wrap: wrap; margin: var(--s5) 0 var(--s2); }}
.section-title.center {{ flex-direction: column; align-items: center; text-align: center; gap: 4px;
  margin: var(--s6) 0 var(--s3); }}
.section-title.center h2 {{ font-size: clamp(1.6rem, 3vw, 2.1rem) !important; font-weight: 500 !important; letter-spacing: -0.03em; }}
.section-title h2 {{ margin: 0 !important; }}
.section-title .meta {{ color: var(--text-faint); font-size: 0.85rem; }}
.section-title h2 [data-testid="stHeaderActionElements"] {{ display: none; }}

.tgrid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: var(--s2); }}
.tcard {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
  padding: var(--s2); box-shadow: var(--shadow); transition: transform .15s ease, box-shadow .2s ease, border-color .2s ease; }}
.tcard:hover {{ transform: translateY(-2px); box-shadow: var(--shadow-hover); border-color: var(--border-strong); }}
.tcard .row {{ display: flex; align-items: center; justify-content: space-between; gap: var(--s1); }}
.tcard .sym {{ font-weight: 600; color: var(--text); font-size: 0.95rem; }}
.tcard .px {{ font-family: var(--font-mono); font-size: 1.3rem; font-weight: 500; color: var(--text);
  margin: var(--s1) 0 var(--s1); }}
.pill {{ font-family: var(--font-mono); font-size: 0.75rem; font-weight: 600; padding: 3px 8px; border-radius: 999px; }}
.pill.up {{ background: var(--up-soft); color: var(--up); }}
.pill.down {{ background: var(--down-soft); color: var(--down); }}
.spark {{ display: block; width: 100%; height: 40px; }}

.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: var(--s2); margin: var(--s1) 0 var(--s1); }}
.stat {{ background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
  padding: var(--s2); box-shadow: var(--shadow); }}
.stat .k {{ color: var(--text-muted); font-size: 0.78rem; font-weight: 500; }}
.stat .v {{ font-family: var(--font-mono); font-size: 1.45rem; font-weight: 500; color: var(--text); margin-top: 4px; }}
.stat .v.up {{ color: var(--up); }} .stat .v.down {{ color: var(--down); }} .stat .v.accent {{ color: var(--accent-text); }}

/* Clickable nav cards (stretched page_link) */
[class*="st-key-navcard_"] {{ position: relative; border: 1px solid var(--accent-border);
  background: linear-gradient(180deg, var(--accent-soft), transparent 70%), var(--surface);
  border-radius: 18px; padding: var(--s3); box-shadow: var(--shadow); gap: 6px !important;
  transition: transform .15s ease, box-shadow .2s ease, border-color .2s ease; height: 100%; }}
[data-testid="stColumn"]:has([class*="st-key-navcard_"]) > div {{ height: 100%; }}
[class*="st-key-navcard_"]:hover {{ transform: translateY(-2px); box-shadow: var(--shadow-hover); border-color: var(--accent); }}
[class*="st-key-navcard_"] div {{ position: static !important; }}
[class*="st-key-navcard_"] [data-testid="stPageLink"] a {{ padding: 0 !important; background: none !important; }}
[class*="st-key-navcard_"] [data-testid="stPageLink"] a::after {{ content: ""; position: absolute; inset: 0; border-radius: var(--radius); }}
[class*="st-key-navcard_"] [data-testid="stPageLink"] p {{ font-size: 1.05rem !important; font-weight: 600 !important; color: var(--text) !important; }}
.navicon {{ width: 40px; height: 40px; border-radius: 10px; display: grid; place-items: center;
  background: var(--accent-soft); border: 1px solid var(--border); margin-bottom: var(--s1); }}
.navicon .ms {{ font-family: 'Material Symbols Rounded'; font-size: 22px; line-height: 1; color: var(--accent-text);
  font-variation-settings: 'FILL' 0, 'wght' 400; -webkit-font-smoothing: antialiased; }}
.navdesc {{ color: var(--text-muted) !important; font-size: 0.9rem; margin: 0 !important; }}
.navarrow {{ color: var(--text-faint); font-size: 1.1rem; margin-top: 6px; transition: transform .15s ease, color .15s ease; }}
[class*="st-key-navcard_"]:hover .navarrow {{ transform: translateX(4px); color: var(--accent-text); }}

.verdict {{ display: flex; align-items: center; gap: var(--s1); padding: 12px var(--s2); border-radius: var(--radius-sm);
  border: 1px solid var(--border); background: var(--surface); color: var(--text); font-size: 0.92rem; margin: var(--s2) 0; }}
.verdict.up {{ border-left: 3px solid var(--up); }} .verdict.down {{ border-left: 3px solid var(--down); }}
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 6px; font-size: 0.75rem; font-weight: 600;
  background: var(--accent-soft); color: var(--accent-text); }}

/* Footer pinned to the bottom of the content column */
.st-key-app_footer {{ order: 9999; margin-top: var(--s6); }}
[data-testid="stVerticalBlock"] > div:has(> .st-key-app_footer) {{ order: 9999; }}
.footer {{ border-top: 1px solid var(--border); padding-top: var(--s2); color: var(--text-faint) !important;
  font-size: 0.78rem; text-align: center; }}

[data-testid="stPlotlyChart"] {{ background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: var(--s1); box-shadow: var(--shadow); }}
</style>
""",
        unsafe_allow_html=True,
    )
