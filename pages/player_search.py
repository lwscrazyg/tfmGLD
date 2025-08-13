# pages/player_search.py – v9.1 (UI polish, dark-mode friendly)
"""
Visual and UX improvements without changing functionality:
• Token-based CSS (respects app light/dark mode).
• Cleaner header, chips, and KPIs with better contrast.
• Subtle link to profile (if URL is resolved) without affecting the logic.
"""
from __future__ import annotations

import json
from pathlib import Path
from io import BytesIO
from urllib.parse import quote_plus

import requests
import streamlit as st
from bs4 import BeautifulSoup
from rapidfuzz import process
from PIL import Image

from services.player_service import fetch_player
from utils.text import normalize
from adaptors.soccerdata_fbref import FBrefStats

# ───────────────────── Constants ──────────────────────────────
_DOMAINS = [
    "https://www.transfermarkt.com",
    "https://www.transfermarkt.es",
    "https://www.transfermarkt.de",
]
_HEADERS = {"User-Agent": "Mozilla/5.0 (ScoutingApp)"}
FAV_PATH = Path("data/favorites.json")
FAV_PATH.parent.mkdir(exist_ok=True)

# ───────────────────── Rerun helper ───────────────────────────
_rerun = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)

def _safe_rerun():
    if callable(_rerun):
        _rerun()

# ───────────────────── Favorites helpers ──────────────────────
def _load_favs() -> list[str]:
    try:
        return json.loads(FAV_PATH.read_text()) if FAV_PATH.exists() else []
    except json.JSONDecodeError:
        return []

def _save_favs(lst: list[str]):
    FAV_PATH.write_text(json.dumps(sorted(set(lst)), indent=2, ensure_ascii=False))

# ───────────────────── Scraping helpers ───────────────────────
@st.cache_data(ttl=6*60*60)
def _resolve_profile_url(name: str, team: str | None) -> str | None:
    slug = quote_plus(normalize(name))
    team_norm = normalize(team) if team else None
    for base in _DOMAINS:
        try:
            html = requests.get(f"{base}/schnellsuche/ergebnis/schnellsuche?query={slug}", headers=_HEADERS, timeout=15).text
        except requests.RequestException:
            continue
        soup = BeautifulSoup(html, "lxml")
        for a in soup.select("a[href*='/profil/spieler/']"):
            row = a.find_parent("tr")
            if row is None:
                continue
            if team_norm and team_norm not in normalize(row.text):
                continue
            href = a["href"]
            return href if href.startswith("http") else base + href
        first = soup.select_one("a[href*='/profil/spieler/']")
        if first:
            href = first["href"]
            return href if href.startswith("http") else base + href
    return None

@st.cache_data(ttl=6*60*60)
def _get_photo(url: str | None) -> Image.Image | None:
    if not url:
        return None
    try:
        html = requests.get(url, headers=_HEADERS, timeout=15).text
        meta = BeautifulSoup(html, "lxml").find("meta", property="og:image")
        if meta and meta.get("content"):
            resp = requests.get(meta["content"].replace("amp;", ""), headers=_HEADERS, timeout=10)
            resp.raise_for_status()
            return Image.open(BytesIO(resp.content))
    except Exception:
        return None

@st.cache_data(ttl=6*60*60)
def _player_index_cached():
    fb = FBrefStats()
    df = fb._fb.read_player_season_stats(stat_type="standard").reset_index()
    return df["player"].unique().tolist()

@st.cache_data(ttl=86400, show_spinner=False)
def _player_index_df_cached():
    """Returns a player index with metadata (league, position, season, age)."""
    fb = FBrefStats()
    try:
        df = fb._fb.read_player_season_stats(stat_type="standard").reset_index()
    except Exception:
        import pandas as pd
        return pd.DataFrame(columns=["player","pos","team","league","season","age"])

    def pick(df, candidates):
        for c in candidates:
            if c in df.columns:
                return df[c]
        return None

    import pandas as pd
    out = pd.DataFrame({
        "player":  pick(df, ["player","Player","name","Name"]),
        "pos":     pick(df, ["pos","Pos","position","Position"]),
        "team":    pick(df, ["team","Team","squad","Squad"]),
        "league":  pick(df, ["league","League","comp","Comp","competition","Competition"]),
        "season":  pick(df, ["season","Season"]),
        "age":     pick(df, ["age","Age"]),
    })

    out = out.dropna(subset=["player"]).copy()
    out["season"] = out["season"].astype(str).str.strip()
    out["pos"] = out["pos"].astype(str).str.upper().str.strip()
    try:
        out["age"] = out["age"].astype(float)
    except Exception:
        pass
    return out

def _apply_filters(df, leagues=None, positions=None, seasons=None, age_range=None):
    import numpy as np
    if df is None or df.empty:
        return df
    mask = np.ones(len(df), dtype=bool)
    if leagues:
        mask &= df["league"].astype(str).isin(leagues)
    if positions:
        mask &= df["pos"].astype(str).isin(positions)
    if seasons:
        mask &= df["season"].astype(str).isin(seasons)
    if age_range and all(age_range):
        lo, hi = age_range
        try:
            mask &= df["age"].astype(float).between(float(lo), float(hi), inclusive="both")
        except Exception:
            pass
    return df[mask]

# ───────────────────── UI helpers ─────────────────────────────
_ICON = {"g": "⚽", "a": "🎯", "xg": "📈", "min": "⏱️"}

def _inject_css():
    # Use tokens from app.py if present; define safe fallbacks.
    st.markdown("""
    <style>
    :root{
      --brand: var(--brand, #0b5f35);
      --brand2: var(--brand-2, #15a06f);
      --ink: var(--ink, #203028);
      --muted: var(--muted, #6a7a70);
      --card: var(--card, #ffffff);
      --line: var(--line, #e6ece8);
      --shadow: var(--shadow, 0 8px 24px rgba(0,0,0,.06));
      --pill: var(--pill, #e9fbf3);
      --focus: var(--focus, #15a06f);
    }
    *{ font-family: 'Poppins', system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; }
    .block-container{ max-width: 1200px; }

    /* Expander */
    details[data-testid="stExpander"]{
      border:1px solid var(--line); border-radius:14px; background:var(--card); box-shadow:var(--shadow);
    }
    details[data-testid="stExpander"] summary{
      padding:.65rem 0; font-weight:700; color:var(--ink);
    }

    /* Chips (favorites/recent) */
    .chip button, div[data-testid="stMarkdownContainer"] .chip{
      display:inline-block; margin:4px 6px 0 0; padding:.45rem .7rem;
      border:1px solid color-mix(in srgb, var(--brand) 20%, var(--line));
      border-radius:999px; background: color-mix(in srgb, var(--brand) 12%, transparent);
      color: var(--brand); font-weight:700; box-shadow:var(--shadow);
      transition: transform .05s ease, background .15s ease;
    }
    .chip button:hover{ background: color-mix(in srgb, var(--brand) 18%, transparent); transform: translateY(-1px); }

    /* Profile */
    .profile{
      background:
        radial-gradient(900px 400px at 100% -50%, var(--card) 0%, color-mix(in srgb, var(--brand) 10%, transparent) 40%, transparent 70%),
        linear-gradient(180deg, var(--card) 0%, color-mix(in srgb, var(--brand) 8%, transparent) 100%);
      border:1px solid var(--line); border-radius:18px; box-shadow:var(--shadow); padding:18px;
    }
    .profile h2{ margin:0 0 2px 0; color:var(--brand); }
    .meta{ color:var(--muted); }
    .badge{ display:inline-block; background:var(--pill); color:var(--brand);
            border:1px solid color-mix(in srgb, var(--brand) 25%, var(--line));
            padding:6px 10px; border-radius:999px; font-weight:800; }
    .season{ display:inline-block; background: color-mix(in srgb, var(--ink) 6%, var(--card));
             border:1px solid var(--line); color: color-mix(in srgb, var(--ink) 80%, black);
             padding:4px 10px; border-radius:999px; margin-left:8px; font-weight:700; }

    /* Image */
    .avatar{ border-radius:14px; box-shadow:0 12px 28px rgba(0,0,0,.12); }

    /* KPI cards */
    .kpi{
      background: var(--card); border:1px solid var(--line); border-radius:14px; text-align:center;
      padding:14px 10px; box-shadow:var(--shadow);
    }
    .kpi .v{ font-size:1.6rem; font-weight:900; line-height:1; margin-bottom:4px; }
    .kpi small{ color:var(--muted); font-weight:700; letter-spacing:.2px; }

    /* Buttons */
    div.stButton > button{
      border-radius:12px; border:1px solid var(--line);
      background: color-mix(in srgb, var(--brand) 12%, transparent);
      color: var(--brand); padding:.6rem .9rem; font-weight:800; box-shadow:var(--shadow);
      transition: transform .05s ease, background .15s ease;
    }
    div.stButton > button:hover{ background: color-mix(in srgb, var(--brand) 18%, transparent); transform: translateY(-1px); }

    /* Labels and inputs */
    label[data-testid="stWidgetLabel"]{ font-weight:800; color:var(--ink); }
    :focus-visible, button:focus-visible, [role="textbox"]:focus-visible {
      outline: 3px solid var(--focus) !important; outline-offset: 2px !important; border-radius: 10px;
    }

    /* Data sources */
    .sources{ color: var(--muted); }
    .sources a{ color: var(--brand); text-decoration: none; font-weight: 700; }
    .sources a:hover{ text-decoration: underline; }
    </style>
    """, unsafe_allow_html=True)

def _header(photo, p, favs):
    _inject_css()
    st.markdown(f"<div class='profile'>", unsafe_allow_html=True)
    img_col, info_col = st.columns([1, 3])
    with img_col:
        st.image(photo or "https://placehold.co/200x240?text=No+Photo", width=200, output_format="PNG")
    with info_col:
        st.markdown(f"<h2>{p.name}</h2>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='meta'>{(p.position or '')} · {(p.team or '')} {(f'({p.league})' if p.league else '')}</div>",
            unsafe_allow_html=True
        )
        row = st.columns([1,1,2])
        with row[0]:
            if p.market_value_mil is not None:
                st.markdown(f"<span class='badge'>💶 {p.market_value_mil:.1f} M€</span>", unsafe_allow_html=True)
        with row[1]:
            st.markdown(f"<span class='season'>Season {p.season}</span>", unsafe_allow_html=True)

        st.markdown("<div style='height:.35rem'></div>", unsafe_allow_html=True)

        # —— Favorites button ——
        if p.name in favs:
            if st.button("✓ Remove from favorites"):
                favs.remove(p.name)
                _save_favs(favs)
                _safe_rerun()
        else:
            if st.button("⭐ Add to favorites"):
                favs.append(p.name)
                _save_favs(favs)
                _safe_rerun()

    st.markdown("</div>", unsafe_allow_html=True)

def _stat_card(label, value, color):
    st.markdown(
        f"""
        <div class='kpi'>
          <div class='v' style='color:{color}'>{value}</div>
          <small>{label}</small>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ───────────────────── main page ───────────────────────────────
def show():
    _inject_css()
    st.header("🏟️ Player Search", divider="grey")
    st.caption("Search players, review key metrics, and save favorites for quick access.")

    # —— Favorites expander ——
    with st.expander("⭐ Favorites", expanded=False):
        favs = _load_favs()
        if favs:
            cols = st.columns(2)
            for i, name in enumerate(favs):
                with cols[i % 2]:
                    st.markdown("<div class='chip'>", unsafe_allow_html=True)
                    if st.button(name, key=f"fav_{name}"):
                        st.session_state["search_query"] = name
                        _safe_rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("Empty — search players and star them ⭐")

    # —— Recent searches ——
    recs = st.session_state.get("recent_queries", [])
    if recs:
        st.markdown("#### Recent")
        rcols = st.columns(min(4, len(recs)))
        for i, q in enumerate(recs[:8]):
            with rcols[i % len(rcols)]:
                st.markdown("<div class='chip'>", unsafe_allow_html=True)
                if st.button(q, key=f"recent_{i}"):
                    st.session_state["search_query"] = q
                    _safe_rerun()
                st.markdown("</div>", unsafe_allow_html=True)

    # —— Quick filters ——
    idx_df = _player_index_df_cached()
    if idx_df is not None and not idx_df.empty:
        with st.expander("🔎 Quick filters", expanded=False):
            c1, c2, c3, c4 = st.columns(4)
            leagues = sorted([x for x in idx_df["league"].dropna().astype(str).unique().tolist() if x and x != "None"])
            positions = sorted([x for x in idx_df["pos"].dropna().astype(str).unique().tolist() if x and x != "None"])
            seasons = sorted([x for x in idx_df["season"].dropna().astype(str).unique().tolist() if x and x != "None"], reverse=True)

            sel_leagues = c1.multiselect("League", leagues, key="flt_leagues")
            sel_positions = c2.multiselect("Position", positions, key="flt_positions")
            default_season = seasons[0:1] if seasons else []
            sel_seasons = c3.multiselect("Season", seasons, default=default_season, key="flt_seasons")

            # Age range if available
            if "age" in idx_df.columns and idx_df["age"].notna().any():
                try:
                    a_min = int(idx_df["age"].dropna().astype(float).min())
                    a_max = int(idx_df["age"].dropna().astype(float).max())
                    sel_age = c4.slider("Age", min_value=a_min, max_value=a_max, value=(a_min, a_max), key="flt_age")
                except Exception:
                    sel_age = None
            else:
                sel_age = None
    else:
        sel_leagues = sel_positions = sel_seasons = []
        sel_age = None

    # —— Search with suggestions ——
    query = st.text_input(
        "Player name",
        value=st.session_state.get("search_query", ""),
        key="search_input",
        help="Type a name: we suggest up to 5 matches (fuzzy match)."
    )
    if not query:
        st.stop()

    names_df = _apply_filters(idx_df, sel_leagues, sel_positions, sel_seasons, sel_age)
    names = (names_df['player'].dropna().unique().tolist() if names_df is not None and not names_df.empty else [])
    suggestions = [h for h, sc, _ in process.extract(query, names, limit=5, score_cutoff=70)]
    selected = st.selectbox("Matches", suggestions or [query]) if suggestions else query

    with st.spinner("Fetching data…"):
        # Save recent search
        _recs = st.session_state.get("recent_queries", [])
        if selected not in _recs:
            st.session_state["recent_queries"] = [selected] + _recs[:7]

        player = fetch_player(selected)
        if player is None:
            st.error(f"No information found for **{selected}**.")
            st.stop()

        # Photo and header
        tm_url = _resolve_profile_url(player.name, player.team)
        photo = _get_photo(tm_url)
        favs = _load_favs()
        _header(photo, player, favs)

        # KPIs
        st.markdown("<div style='height:.25rem'></div>", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        with c1: _stat_card(f"{_ICON['g']} Goals", player.goals, "var(--brand)")
        with c2: _stat_card(f"{_ICON['a']} Assists", player.assists, "var(--brand2)")
        with c3: _stat_card(f"{_ICON['xg']} xG", player.xG, "color-mix(in srgb, var(--brand) 70%, var(--brand2))")
        with c4: _stat_card(f"{_ICON['min']} Min", player.minutes, "color-mix(in srgb, var(--brand) 55%, var(--brand2))")

        st.divider()

        # Sources (optional link if available)
        if tm_url:
            st.markdown(
                f"<div class='sources'>Sources: FBref · SoccerData · "
                f"<a href='{tm_url}' target='_blank' rel='noopener noreferrer'>Transfermarkt</a></div>",
                unsafe_allow_html=True
            )
        else:
            st.caption("Sources: FBref · Transfermarkt · SoccerData")








