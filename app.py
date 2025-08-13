# app.py – Scouting App launcher (v3.4, UI refresh + dark mode + shortlist CTA)
from importlib import import_module
from typing import Dict

import streamlit as st
from streamlit_option_menu import option_menu

# ——— Global config ————————————————————————————————————
APP_VERSION = "v3.4"
st.set_page_config(page_title="⚽ Scouting App", page_icon="⚽", layout="wide")

def safe_rerun():
    """Call st.rerun() or st.experimental_rerun() depending on the installed version."""
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()

# ——— Pages ———————————————————————————————————————
PAGES: Dict[str, str | None] = {
    "Home": None,
    "Player Search": "pages.player_search",
    "XI Builder": "pages.xi_builder",
    "Shortlist & Notes": "pages.shortlist",
}
ICONS = {
    "Home": "house",
    "Player Search": "search",
    "XI Builder": "clipboard-data",
    "Shortlist & Notes": "bookmark-star",
}

# ——— Persist nav state ———————————————————————————
if "nav_page" not in st.session_state:
    st.session_state.nav_page = "Home"
if "theme" not in st.session_state:
    st.session_state.theme = "light"  # 'light' | 'dark'

# ——— Global styles (Google Fonts + Bootstrap Icons + CSS) ———————————
# Tokens for both themes; we alternate values based on st.session_state.theme
is_dark = st.session_state.theme == "dark"
css_tokens = f"""
:root {{
  --brand: {'#11a56f' if is_dark else '#0b5f35'};
  --brand-2: {'#35d09d' if is_dark else '#15a06f'};
  --ink: {'#e9f1ed' if is_dark else '#203028'};
  --muted: {'#9bb3a7' if is_dark else '#6a7a70'};
  --bg-1: {'#0e1512' if is_dark else '#f5faf7'};
  --bg-2: {'#0b110f' if is_dark else '#eef6f1'};
  --card: {'#0f1714' if is_dark else '#ffffff'};
  --line: {'#1d2a25' if is_dark else '#e6ece8'};
  --shadow: 0 8px 24px rgba(0,0,0,.20);
  --focus: {'#35d09d' if is_dark else '#15a06f'};
}}
"""

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap');
@import url('https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css');

{css_tokens}

/* Background and typography */
html, body, [data-testid="stAppViewContainer"]{{
  background: linear-gradient(180deg, var(--bg-1) 0%, var(--bg-2) 100%);
  color: var(--ink);
}}
*{{
  font-family:
    'Poppins',
    system-ui, -apple-system, Segoe UI, Roboto, 'Helvetica Neue', Arial, 'Noto Sans', 'Liberation Sans', sans-serif,
    'Apple Color Emoji','Segoe UI Emoji','Segoe UI Symbol','Noto Color Emoji';
}}

/* Hide Streamlit's native multipage navigator in the sidebar */
div[data-testid="stSidebarNav"] {{ display: none !important; }}

/* Comfortable wide layout */
.block-container{{
  padding-top: 1rem !important;
  padding-bottom: 2.5rem !important;
  max-width: 1200px;
}}

/* Polished sidebar */
section[data-testid="stSidebar"]{{
  background: var(--card) !important;
  border-right: 1px solid var(--line);
  box-shadow: 0 0 24px rgba(0,0,0,.08);
}}
section[data-testid="stSidebar"] > div:first-child{{ padding-top: .75rem; }}
section[data-testid="stSidebar"] .bi{{ font-size: 1.05rem; }}

/* Option menu (streamlit-option-menu) */
.nav-link{{
  border-radius: 12px !important;
  margin: 4px 8px !important;
  padding: 10px 12px !important;
  transition: all .15s ease;
  border: 1px solid transparent !important;
  color: var(--ink) !important;
}}
.nav-link:hover{{ background: rgba(53,208,157,.10) !important; border-color: var(--line) !important; }}
.nav-link i{{ margin-right: .5rem; }}
.nav-link-selected{{
  background-color: rgba(53,208,157,.18) !important;
  color: var(--brand) !important;
  font-weight: 600 !important;
  border-color: var(--line) !important;
}}

/* Visible focus for accessibility */
:focus-visible, .nav-link:focus-visible, button:focus-visible {{
  outline: 3px solid var(--focus) !important;
  outline-offset: 2px !important;
  border-radius: 12px;
}}

/* Hero */
.hero{{
  position: relative;
  overflow: hidden;
  background:
    radial-gradient(1000px 500px at 100% -50%, var(--card) 0%, rgba(53,208,157,.08) 40%, transparent 70%),
    linear-gradient(180deg, var(--card) 0%, rgba(53,208,157,.06) 100%);
  border: 1px solid var(--line);
  border-radius: 20px;
  box-shadow: var(--shadow);
  padding: 36px 28px;
}}
.hero .badge{{
  display:inline-block; background: rgba(53,208,157,.12); color: var(--brand); font-weight: 600;
  border:1px solid var(--line); padding:6px 10px; border-radius: 999px; font-size:.9rem;
}}
.hero h1{{
  margin: 10px 0 6px 0; color: var(--brand);
  font-size: clamp(2.2rem, 3.5vw, 3rem); line-height: 1.1;
}}
.hero p{{ color: var(--muted); max-width: 760px; font-size: 1.05rem; }}

/* CTA buttons */
.cta{{ display:flex; gap:12px; flex-wrap: wrap; margin-top: 14px; }}
.cta .btn{{
  appearance:none; border:none; cursor:pointer;
  padding:12px 16px; border-radius: 12px; font-weight: 600;
  box-shadow: var(--shadow); transition: transform .05s ease, box-shadow .15s ease, background .15s ease;
}}
.cta .btn-primary{{ background: var(--brand); color: #fff; }}
.cta .btn-primary:hover{{ transform: translateY(-1px); box-shadow: 0 10px 30px rgba(11,95,53,.25); }}
.cta .btn-ghost{{ background: rgba(53,208,157,.10); color: var(--brand); border:1px solid var(--line); }}
.cta .btn-ghost:hover{{ transform: translateY(-1px); }}

/* Feature cards */
.grid{{ display:grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap:16px; margin-top: 20px; }}
@media (max-width: 1000px){{ .grid{{ grid-template-columns: repeat(2, minmax(0,1fr)); }} }}
@media (max-width: 640px){{ .grid{{ grid-template-columns: 1fr; }} }}
.card{{
  background: var(--card); border:1px solid var(--line); border-radius: 16px; padding:16px 16px 18px 16px;
  box-shadow: var(--shadow); transition: transform .08s ease, box-shadow .15s ease, border-color .15s ease, background .15s ease;
}}
.card:hover{{ transform: translateY(-2px); box-shadow: 0 10px 26px rgba(0,0,0,.12); border-color: var(--line); }}
.card .icon{{
  width:42px; height:42px; border-radius: 12px; display:grid; place-items:center;
  background: rgba(53,208,157,.12); color:var(--brand);
  margin-bottom:10px; font-size:1.2rem;
}}
.card h3{{ margin: 0 0 6px 0; color:var(--ink); font-size:1.15rem; }}
.card p{{ color: var(--muted); font-size:.98rem; }}

/* Native Streamlit buttons (Home) */
div.stButton > button{{
  width:100%; border-radius:12px; border:1px solid var(--line); background: rgba(53,208,157,.10); color:var(--brand);
  padding:.7rem 1rem; font-weight:600; transition: all .15s ease; box-shadow: var(--shadow);
}}
div.stButton > button:hover{{ background: rgba(53,208,157,.18); transform: translateY(-1px); }}

/* Footer */
.footer{{ color: var(--muted); font-size:.92rem; text-align:center; margin-top: 28px; }}
</style>
""", unsafe_allow_html=True)

# ——— Sidebar ————————————————————————————
with st.sidebar:
    st.markdown(
        f"<h2 style='color:var(--brand);text-align:center;margin:.25rem 0 0 0;'>⚽ Scouting App</h2>",
        unsafe_allow_html=True,
    )
    # Theme toggle
    theme_label = "🌙 Dark mode" if st.session_state.theme == "light" else "🌞 Light mode"
    if st.toggle(theme_label, value=is_dark, key="toggle_theme"):
        st.session_state.theme = "dark"
    else:
        st.session_state.theme = "light"

    # Menu
    sel = option_menu(
        menu_title=None,
        options=list(PAGES.keys()),
        icons=[ICONS[p] for p in PAGES],
        default_index=list(PAGES.keys()).index(st.session_state.nav_page),
        styles={
            "container": {"padding": "0"},
            "nav-link": {"font-size": "16px"},
            "nav-link-selected": {"background-color": "#d4edda"},
        },
    )

# Update state if selection changed
if sel != st.session_state.nav_page:
    st.session_state.nav_page = sel

page = st.session_state.nav_page

# ——— Routing —————————————————————————————————————————
if page == "Home":

    # HERO with CTA
    st.markdown(
        f"""
        <div class="hero">
          <span class="badge">{APP_VERSION}</span>
          <h1>Welcome to the Scouting App</h1>
          <p>
            Explore profiles, design lineups, and speed up your scouting workflow
            with a fast, clean interface. Use the <b>sidebar menu</b> or the shortcuts below.
          </p>
          <div class="cta">
            <span class="btn btn-primary">🔍 Player Search</span>
            <span class="btn btn-ghost">📝 XI Builder</span>
            <span class="btn btn-ghost">📓 Shortlist & Notes</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Real CTAs aligned with the hero
    cta1, cta2, cta3 = st.columns([1,1,1])
    with cta1:
        if st.button("🔍  Player Search", use_container_width=True):
            st.session_state.nav_page = "Player Search"
            safe_rerun()
    with cta2:
        if st.button("📝  XI Builder", use_container_width=True):
            st.session_state.nav_page = "XI Builder"
            safe_rerun()
    with cta3:
        if st.button("📓  Shortlist & Notes", use_container_width=True):
            st.session_state.nav_page = "Shortlist & Notes"
            safe_rerun()

    # Feature cards (descriptive text)
    st.markdown("""
    <div class="grid">
      <div class="card">
        <div class="icon"><i class="bi bi-search"></i></div>
        <h3>Player Search</h3>
        <p>Search footballers by name/position and explore key metrics with precise filters.</p>
      </div>
      <div class="card">
        <div class="icon"><i class="bi bi-clipboard-data"></i></div>
        <h3>XI Builder</h3>
        <p>Design your ideal XI, save lineups, and export your proposal for reports.</p>
      </div>
      <div class="card">
        <div class="icon"><i class="bi bi-bookmark-star"></i></div>
        <h3>Shortlist & Notes</h3>
        <p>Create shortlists, add notes, tags, and ratings. Import/export CSV for your Master's thesis or club.</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(
        f'<div class="footer">Made with 💚 for analysts — {APP_VERSION} — Keep your data and workflow in one place.</div>',
        unsafe_allow_html=True,
    )

else:
    module_path = PAGES[page]
    if module_path:
        try:
            with st.spinner("Loading…"):
                module = import_module(module_path)
                # Expect a show() function in the page module
                if hasattr(module, "show"):
                    module.show()
                else:
                    st.error(f"The page '{page}' does not expose a show() function.")
        except Exception as e:
            st.error(f"Error loading page '{page}': {e}")
    else:
        st.error("Invalid route.")














