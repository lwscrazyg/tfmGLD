# pages/xi_builder.py — XI Builder (optimization + comparison)
# v3.2 UI polish — Visual changes only (no logic/flow)

from __future__ import annotations

import os
from pathlib import Path
import streamlit as st
from rapidfuzz import process

from services.xi_service import (
    Squad, FORMATIONS, load_player_pool, score_players,
    add_market_values, optimize_xi, compare_squads
)
from services.player_service import fetch_player
from adaptors.soccerdata_fbref import FBrefStats

SQUADS_DIR = Path("data/squads")
SQUADS_DIR.mkdir(parents=True, exist_ok=True)

def _is_valid_squad_file(name: str) -> bool:
    p = SQUADS_DIR / f"{name}.json"
    try:
        import json
        raw = p.read_text(encoding="utf-8")
        if not raw.strip():
            return False
        d = json.loads(raw)
        return isinstance(d, dict) and "formation" in d and "slots" in d
    except Exception:
        return False

def _safe_rerun():
    try:
        st.rerun()
    except Exception:
        st.experimental_rerun()

# ——— Global styles (UI visuals only; respects app tokens) ———
def _inject_css():
    st.markdown("""
    <style>
    :root{
      /* Inherits from app.py if present; safe fallbacks */
      --brand: var(--brand, #0b5f35);
      --brand-2: var(--brand-2, #15a06f);
      --ink: var(--ink, #203028);
      --muted: var(--muted, #6a7a70);
      --card: var(--card, #ffffff);
      --line: var(--line, #e6ece8);
      --shadow: var(--shadow, 0 8px 24px rgba(0,0,0,.08));
      --focus: var(--focus, #15a06f);
    }
    *{ font-family:'Poppins', system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; }
    .block-container{ max-width: 1200px; }

    /* More pronounced and accessible Tabs */
    button[role="tab"]{
      border:1px solid var(--line) !important; border-bottom:none !important;
      border-radius:12px 12px 0 0 !important; margin-right:6px;
      background: color-mix(in srgb, var(--brand) 8%, transparent) !important;
      color: var(--brand) !important; font-weight: 700 !important;
    }
    button[aria-selected="true"][role="tab"]{
      background: var(--card) !important; color: var(--ink) !important;
    }

    /* Visible focus */
    :focus-visible, button:focus-visible, [role="textbox"]:focus-visible {
      outline: 3px solid var(--focus) !important; outline-offset: 2px !important; border-radius: 10px;
    }

    /* Buttons */
    div.stButton > button{
      border-radius:12px; border:1px solid var(--line);
      background: color-mix(in srgb, var(--brand) 12%, transparent);
      color: var(--brand); padding:.6rem .9rem; font-weight:800; box-shadow:var(--shadow);
      transition: transform .05s ease, background .15s ease;
    }
    div.stButton > button:hover{ background: color-mix(in srgb, var(--brand) 18%, transparent); transform: translateY(-1px); }

    /* Labels and controls */
    label[data-testid="stWidgetLabel"]{ font-weight:800; color:var(--ink); }
    .stSelectbox, .stTextInput, .stNumberInput { font-weight: 600; }

    /* DataFrames with soft borders */
    .stDataFrame, .stTable{ border:1px solid var(--line); border-radius:14px; box-shadow:var(--shadow); }

    /* Expanders */
    details[data-testid="stExpander"]{
      border:1px solid var(--line); border-radius:14px; background:var(--card); box-shadow:var(--shadow);
    }
    details[data-testid="stExpander"] summary{ font-weight:800; color:var(--ink); }

    /* Metrics */
    [data-testid="stMetric"]{
      border:1px solid var(--line); border-radius:14px; padding:.6rem; background:var(--card); box-shadow:var(--shadow);
    }

    /* Help/explanation bar */
    .hint{
      background: color-mix(in srgb, var(--brand) 6%, var(--card));
      border:1px solid var(--line); border-radius:12px; padding:.6rem .8rem; color: var(--muted);
    }
    </style>
    """, unsafe_allow_html=True)

# ——— Pitch with improved SVG (visual only) ———
def _draw_pitch(squad: Squad, orientation: str = "vertical"):
    from streamlit.components.v1 import html as st_html

    if orientation not in {"vertical", "horizontal"}:
        orientation = "vertical"

    # Canvases: horizontal (1200x800) or vertical (800x1200)
    if orientation == "horizontal":
        width, height = 1200, 800
        rect_x, rect_y, rect_w, rect_h, r = 20, 20, width-40, height-40, 16
        mid_line = {"x1": width/2, "y1": 20, "x2": width/2, "y2": height-20}
        center = (width/2, height/2)
        COORDS = {
            "4-3-3": {
                "GK":(600,760),
                "LB":(200,620),"LCB":(420,650),"RCB":(780,650),"RB":(1000,620),
                "LCM":(420,480),"CM":(600,450),"RCM":(780,480),
                "LW":(260,260),"ST":(600,200),"RW":(940,260)
            },
            "4-2-3-1": {
                "GK":(600,760),
                "LB":(200,620),"LCB":(420,650),"RCB":(780,650),"RB":(1000,620),
                "LDM":(470,520),"CDM":(600,520),"RDM":(730,520),
                "LAM":(420,360),"CAM":(600,340),"RAM":(780,360),
                "ST":(600,210)
            },
            "4-4-2": {
                "GK":(600,760),
                "LB":(200,620),"LCB":(420,650),"RCB":(780,650),"RB":(1000,620),
                "LM":(320,430),"LCM":(500,430),"RCM":(700,430),"RM":(880,430),
                "LS":(520,250),"RS":(680,250)
            },
        }
        coords = COORDS.get(squad.formation, COORDS["4-3-3"])
        iframe_h = 620

        box_w, box_h = rect_w*0.5, 120
        area_w, area_h = rect_w*0.3, 60
        up_box = (width/2 - box_w/2, rect_y, box_w, box_h)
        up_area = (width/2 - area_w/2, rect_y, area_w, area_h)
        dn_box = (width/2 - box_w/2, rect_y+rect_h-box_h, box_w, box_h)
        dn_area = (width/2 - area_w/2, rect_y+rect_h-area_h, area_w, area_h)

    else:  # VERTICAL (portrait)
        width, height = 800, 1200
        rect_x, rect_y, rect_w, rect_h, r = 20, 20, width-40, height-40, 16
        mid_line = {"x1": rect_x, "y1": height/2, "x2": width-20, "y2": height/2}
        center = (width/2, height/2)
        COORDS_V = {
            "4-3-3": {
                "GK":(400,1120),
                "LB":(150, 930), "LCB":(300, 970), "RCB":(500, 970), "RB":(650, 930),
                "LCM":(300, 720), "CM":(400, 690), "RCM":(500, 720),
                "LW":(190, 440), "ST":(400, 360), "RW":(610, 440),
            },
            "4-2-3-1": {
                "GK":(400,1120),
                "LB":(150, 930), "LCB":(300, 970), "RCB":(500, 970), "RB":(650, 930),
                "LDM":(320, 790), "CDM":(400, 790), "RDM":(480, 790),
                "LAM":(300, 560), "CAM":(400, 540), "RAM":(500, 560),
                "ST":(400, 380),
            },
            "4-4-2": {
                "GK":(400,1120),
                "LB":(150, 930), "LCB":(300, 970), "RCB":(500, 970), "RB":(650, 930),
                "LM":(240, 690), "LCM":(340, 690), "RCM":(460, 690), "RM":(560, 690),
                "LS":(360, 420), "RS":(440, 420),
            },
        }
        coords = COORDS_V.get(squad.formation, COORDS_V["4-3-3"])
        iframe_h = 720

        box_h, box_w = rect_h*0.22, rect_w
        area_h, area_w = rect_h*0.12, rect_w*0.6
        up_box  = (rect_x, rect_y, rect_w, box_h)
        up_area = (rect_x + (rect_w-area_w)/2, rect_y, area_w, area_h)
        dn_box  = (rect_x, rect_y+rect_h-box_h, rect_w, box_h)
        dn_area = (rect_x + (rect_w-area_w)/2, rect_y+rect_h-area_h, area_w, area_h)

    # HTML + SVG (aesthetics only)
    html = f"""
<!doctype html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0">
<svg viewBox="0 0 {width} {height}" width="100%" height="{iframe_h}"
     preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg">

  <defs>
    <linearGradient id="grass" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"  stop-color="#0f6b3f"/>
      <stop offset="100%" stop-color="#0b5f35"/>
    </linearGradient>
    <pattern id="mow" width="40" height="40" patternUnits="userSpaceOnUse">
      <rect width="40" height="20" fill="rgba(255,255,255,.03)"/>
      <rect y="20" width="40" height="20" fill="rgba(0,0,0,.03)"/>
    </pattern>
    <filter id="shadow" x="-50%" y="-50%" width="200%" height="200%">
      <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="rgba(0,0,0,0.25)"/>
    </filter>
  </defs>

  <!-- Pitch -->
  <rect x="{rect_x}" y="{rect_y}" width="{rect_w}" height="{rect_h}" rx="{r}" ry="{r}"
        fill="url(#grass)" stroke="#e8f5ee" stroke-width="4"/>
  <rect x="{rect_x}" y="{rect_y}" width="{rect_w}" height="{rect_h}" rx="{r}" ry="{r}"
        fill="url(#mow)" opacity=".55"/>

  <!-- Main lines -->
  <line x1="{mid_line['x1']}" y1="{mid_line['y1']}" x2="{mid_line['x2']}" y2="{mid_line['y2']}"
        stroke="#e8f5ee" stroke-width="3" opacity="0.85"/>
  <circle cx="{center[0]}" cy="{center[1]}" r="90"
          stroke="#e8f5ee" stroke-width="3" fill="none" opacity="0.85"/>
  <circle cx="{center[0]}" cy="{center[1]}" r="3" fill="#e8f5ee"/>

  <!-- Large and small boxes -->
  <rect x="{up_box[0]}" y="{up_box[1]}" width="{up_box[2]}" height="{up_box[3]}" fill="none" stroke="#e8f5ee" stroke-width="3" opacity=".9"/>
  <rect x="{up_area[0]}" y="{up_area[1]}" width="{up_area[2]}" height="{up_area[3]}" fill="none" stroke="#e8f5ee" stroke-width="3" opacity=".9"/>
  <rect x="{dn_box[0]}" y="{dn_box[1]}" width="{dn_box[2]}" height="{dn_box[3]}" fill="none" stroke="#e8f5ee" stroke-width="3" opacity=".9"/>
  <rect x="{dn_area[0]}" y="{dn_area[1]}" width="{dn_area[2]}" height="{dn_area[3]}" fill="none" stroke="#e8f5ee" stroke-width="3" opacity=".9"/>

  <!-- Penalty spots -->
  <circle cx="{center[0]}" cy="{rect_y + (up_area[3] + 18)}" r="3" fill="#e8f5ee"/>
  <circle cx="{center[0]}" cy="{rect_y + rect_h - (up_area[3] + 18)}" r="3" fill="#e8f5ee"/>

  <!-- Rounded corners -->
  <path d="M {rect_x} {rect_y+20} a20,20 0 0,1 20,-20" stroke="#e8f5ee" stroke-width="3" fill="none" opacity=".9"/>
  <path d="M {rect_x+rect_w-20} {rect_y} a20,20 0 0,1 20,20" stroke="#e8f5ee" stroke-width="3" fill="none" opacity=".9"/>
  <path d="M {rect_x} {rect_y+rect_h-20} a20,20 0 0,0 20,20" stroke="#e8f5ee" stroke-width="3" fill="none" opacity=".9"/>
  <path d="M {rect_x+rect_w-20} {rect_y+rect_h} a20,20 0 0,0 20,-20" stroke="#e8f5ee" stroke-width="3" fill="none" opacity=".9"/>
"""

    # Players (white circle with green border and shadow)
    for pos, (x, y) in coords.items():
        p = squad.slots.get(pos).player if pos in squad.slots else None
        label = (p.get("name","") or pos).split()[0] if p else pos
        html += f'''
  <g filter="url(#shadow)">
    <circle cx="{x}" cy="{y}" r="32" fill="#ffffff" stroke="#0b5f35" stroke-width="4"/>
    <text x="{x}" y="{y+6}" font-size="18" text-anchor="middle" font-weight="700" fill="#0b5f35">{label}</text>
  </g>'''

    html += "\n</svg></body></html>"
    st_html(html, height=iframe_h+20, scrolling=False)

def _list_saved_squads() -> list[str]:
    all_names = [p.stem for p in SQUADS_DIR.glob("*.json")]
    return [n for n in all_names if _is_valid_squad_file(n)]

def _load_squad(name: str) -> Squad:
    return Squad.load(str(SQUADS_DIR / f"{name}.json"))

def _save_squad(name: str, squad: Squad):
    (SQUADS_DIR / f"{name}.json").parent.mkdir(parents=True, exist_ok=True)
    squad.save(str(SQUADS_DIR / f"{name}.json"))

def _search_box() -> str | None:
    fb = FBrefStats()
    df = fb._fb.read_player_season_stats(stat_type="standard").reset_index()
    names = sorted(df["player"].dropna().unique().tolist())
    q = st.text_input("Search player", "")
    if not q:
        return None
    opts = [h for h,sc,_ in process.extract(q, names, limit=5, score_cutoff=70)]
    return st.selectbox("Matches", opts or [q])

def show() -> None:
    _inject_css()
    st.header("📝 XI Builder", divider="grey")
    st.caption("Build your XI manually, optimize it with basic criteria, and compare it with other saved XIs.")

    # Initial state
    if "squad" not in st.session_state:
        st.session_state["squad"] = Squad()
        st.session_state["squad"].set_formation("4-3-3")
    squad: Squad = st.session_state["squad"]

    tab1, tab2, tab3 = st.tabs(["Builder", "Optimization", "Comparison"])

    # ————— Manual builder —————
    with tab1:
        c1,c2 = st.columns([1,1])
        with c1:
            formation = st.selectbox(
                "Formation",
                list(FORMATIONS.keys()),
                index=list(FORMATIONS.keys()).index(squad.formation),
                key="formation_builder",
                help="Select the system and place players by position."
            )
            if formation != squad.formation:
                squad.set_formation(formation)
            _draw_pitch(squad)

        with c2:
            pos = st.selectbox("Position", FORMATIONS[squad.formation], key="pos_builder")
            name = _search_box()
            if name and st.button("Add to XI", use_container_width=True):
                squad.add(pos, name)
                _safe_rerun()

            if st.button("Clear position", use_container_width=True):
                squad.remove(pos)
                _safe_rerun()

            st.divider()
            st.subheader("Current squad")
            st.dataframe(squad.to_dataframe(), use_container_width=True)
            st.metric("Total value", f"{squad.total_value():.1f} M€")

            st.divider()
            save_name = st.text_input("Save as", "", placeholder="e.g., my_favorite_xi")
            if st.button("Save XI"):
                if save_name.strip():
                    _save_squad(save_name.strip(), squad)
                    st.success(f"Saved as {save_name}.json")
                else:
                    st.warning("Provide a name to save your XI.")

    # ————— Automatic optimization —————
    with tab2:
        st.subheader("Simple optimization")
        st.caption("Choose season and formation and click Optimize. Adjust weights and budget in Advanced options.")
        c1,c2,c3 = st.columns(3)
        season = c1.text_input("Season", "2024-2025")
        league = c2.text_input("League (optional)", "")
        form_sel = c3.selectbox(
            "Formation",
            list(FORMATIONS.keys()),
            index=list(FORMATIONS.keys()).index(squad.formation),
            key="formation_opt"
        )

        with st.expander("Advanced options (weights and budget)"):
            w1,w2,w3,w4 = st.columns(4)
            w_goals = w1.slider("Weight Goals", 0.0, 1.0, 0.5, 0.05)
            w_ass   = w2.slider("Weight Assists", 0.0, 1.0, 0.2, 0.05)
            w_xg    = w3.slider("Weight xG", 0.0, 1.0, 0.3, 0.05)
            w_min   = w4.slider("Weight Minutes", 0.0, 1.0, 0.2, 0.05)
            use_budget = st.checkbox("Use budget (requires market values)", value=False)
            budget = st.number_input("Budget (M€)", 0.0, 9999.0, 0.0, 5.0) if use_budget else 0.0
            custom_weights = {"goals":w_goals,"assists":w_ass,"xG":w_xg,"minutes":w_min} if any([w_goals,w_ass,w_xg,w_min]) else None

        st.caption("Top by position are chosen with typical role metrics (forwards: goals/xG; midfielders: assists; defenders/goalkeeper: minutes).")

        if st.button("Optimize XI", use_container_width=True):
            pool = load_player_pool(season=season or None, league=league or None)
            if custom_weights:
                pool = score_players(pool, custom_weights)
            chosen = optimize_xi(
                form_sel, pool,
                budget_mil=(budget if use_budget and budget>0 else None),
                user_weights=(custom_weights if custom_weights else None)
            )
            new_sq = Squad(formation=form_sel)
            for pos, row in chosen:
                new_sq.slots[pos].player = {
                    "name": row.get("name"),
                    "team": row.get("team"),
                    "league": row.get("league"),
                    "season": row.get("season"),
                    "age": row.get("age"),
                    "position": row.get("pos"),
                    "market_value_mil": row.get("market_value_mil"),
                    "goals": row.get("goals"),
                    "assists": row.get("assists"),
                    "xG": row.get("xG"),
                    "minutes": row.get("minutes"),
                }
            st.session_state["squad"] = new_sq
            st.success("Optimized XI generated.")
            _safe_rerun()

        st.subheader("Top-3 suggested per position")
        try:
            from services.xi_service import score_for_slot, ELIGIBLE_MAP
            pool = load_player_pool(season=season or None, league=league or None)
            import pandas as pd
            rows = []
            for slot in FORMATIONS[form_sel]:
                sc = score_for_slot(pool, slot).copy()
                def eligible(row_pos):
                    rp = str(row_pos).upper()
                    return any(p in rp for p in ELIGIBLE_MAP.get(slot, [slot]))
                sc = sc[sc["pos"].apply(eligible)]
                sc = sc.sort_values("score_slot", ascending=False).head(3)
                for _,r in sc.iterrows():
                    rows.append({"Position":slot, "Name":r.get("name"), "Score":round(float(r.get("score_slot",0)),3), "Club":r.get("team")})
            if rows:
                import pandas as pd
                st.dataframe(pd.DataFrame(rows), use_container_width=True)
        except Exception as e:
            st.caption(f"Could not compute suggestions: {e}")

    # ————— Comparison —————
    with tab3:
        st.subheader("Compare two saved XIs")
        all_sq = _list_saved_squads()
        if not all_sq:
            st.info("No saved XIs yet. Save one in the Builder tab.")
        else:
            c1,c2 = st.columns(2)
            with c1:
                a_name = st.selectbox("Squad A", all_sq, key="cmp_a")
                try:
                    A = _load_squad(a_name)
                except Exception as e:
                    st.error(f"Error loading {a_name}.json: {e}")
                    st.stop()
                st.caption(f"{a_name}.json")
                _draw_pitch(A)
                st.dataframe(A.to_dataframe(), use_container_width=True)
            with c2:
                b_name = st.selectbox("Squad B", all_sq, key="cmp_b")
                try:
                    B = _load_squad(b_name)
                except Exception as e:
                    st.error(f"Error loading {b_name}.json: {e}")
                    st.stop()
                st.caption(f"{b_name}.json")
                _draw_pitch(B)
                st.dataframe(B.to_dataframe(), use_container_width=True)
            st.divider()
            st.subheader("Comparative summary")
            st.dataframe(compare_squads(A,B), use_container_width=True)



