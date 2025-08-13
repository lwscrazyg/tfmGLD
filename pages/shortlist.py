# pages/shortlist.py — Shortlist & Notes (UI) v1.0
from __future__ import annotations
import uuid
from datetime import datetime
from typing import List, Dict

import streamlit as st
import pandas as pd

from services.shortlist_service import (
    SHORTLISTS_DIR, SCHEMA_VERSION,
    list_shortlists, load_shortlist, save_shortlist,
    create_shortlist_if_missing, delete_shortlist,
    add_entry, update_entry, delete_entry,
    export_shortlist_to_csv, import_shortlist_from_csv
)

# ——— UI utilities ———
def _safe_rerun():
    try:
        st.rerun()
    except Exception:
        st.experimental_rerun()

def _inject_css():
    st.markdown("""
    <style>
    :root{
      --brand: var(--brand, #0b5f35);
      --brand-2: var(--brand-2, #15a06f);
      --ink: var(--ink, #203028);
      --muted: var(--muted, #6a7a70);
      --card: var(--card, #ffffff);
      --line: var(--line, #e6ece8);
      --shadow: var(--shadow, 0 8px 24px rgba(0,0,0,.08));
      --focus: var(--focus, #15a06f);
    }
    .panel{ background: var(--card); border:1px solid var(--line); border-radius:14px; padding:14px; box-shadow: var(--shadow);}
    .chip{ display:inline-block; margin:3px 6px 0 0; padding:.35rem .6rem; border:1px solid var(--line);
           border-radius:999px; background: color-mix(in srgb, var(--brand) 10%, transparent); color: var(--brand); font-weight:700;}
    </style>
    """, unsafe_allow_html=True)

# ——— Page ———
def show():
    _inject_css()
    st.header("📓 Shortlist & Notes", divider="grey")
    st.caption("Create shortlists, add players with notes and tags, filter, and export to CSV. Independent of the search and the XI.")

    # State
    if "sl_name" not in st.session_state:
        st.session_state.sl_name = "default"

    # Top bar: pick shortlist + create/delete + import/export
    c_top1, c_top2, c_top3, c_top4 = st.columns([2, 1, 1, 1])
    with c_top1:
        all_sls = list_shortlists()
        if st.session_state.sl_name not in all_sls and all_sls:
            st.session_state.sl_name = all_sls[0]
        st.selectbox("Shortlist", options=all_sls or ["default"], key="sl_name")
    with c_top2:
        with st.popover("➕ New shortlist"):
            new_name = st.text_input("Name", "")
            if st.button("Create"):
                create_shortlist_if_missing(new_name.strip() or "default")
                st.success("Shortlist created.")
                st.session_state.sl_name = new_name.strip() or "default"
                _safe_rerun()
    with c_top3:
        with st.popover("⬆️ Import CSV"):
            up = st.file_uploader("CSV", type=["csv"])
            if up and st.button("Import"):
                import_shortlist_from_csv(st.session_state.sl_name, up)
                st.success("Imported.")
                _safe_rerun()
    with c_top4:
        if st.button("⬇️ Export CSV", use_container_width=True):
            fp = export_shortlist_to_csv(st.session_state.sl_name)
            st.success(f"Exported to {fp}")

    # Delete shortlist button
    with st.expander("⚠️ Delete shortlist (irreversible)"):
        if st.button("Delete current shortlist"):
            delete_shortlist(st.session_state.sl_name)
            st.session_state.sl_name = (list_shortlists()[0] if list_shortlists() else "default")
            _safe_rerun()

    # Load data
    data = load_shortlist(st.session_state.sl_name)
    entries: List[Dict] = data.get("entries", [])

    # Filters
    with st.expander("🔎 Filters", expanded=False):
        c1,c2,c3,c4,c5 = st.columns(5)
        pos = c1.multiselect("Position", sorted({e.get("position","") for e in entries if e.get("position")}), [])
        status = c2.multiselect("Status", ["Scouting","Follow","Target","Rejected","Signed"], [])
        tags_all = sorted({t.strip() for e in entries for t in (e.get("tags","") or "").split(",") if t.strip()})
        tags = c3.multiselect("Tags", tags_all, [])
        min_rating = c4.slider("Minimum rating", 1, 5, 1)
        max_age = c5.number_input("Max age", min_value=0, max_value=60, value=60, step=1)

    # Main table
    def _match_filters(e: Dict) -> bool:
        if pos and (e.get("position") or "") not in pos: return False
        if status and (e.get("status") or "") not in status: return False
        if tags:
            e_tags = {t.strip() for t in (e.get("tags","") or "").split(",") if t.strip()}
            if not set(tags).issubset(e_tags): return False
        if int(e.get("rating", 0) or 0) < min_rating: return False
        try:
            if max_age and e.get("age") and float(e["age"]) > float(max_age): return False
        except Exception:
            pass
        return True

    filtered = [e for e in entries if _match_filters(e)]
    df = pd.DataFrame(filtered) if filtered else pd.DataFrame(columns=[
        "id","name","position","team","league","age","value_mil","rating","status","tags","notes","updated_at"
    ])
    st.dataframe(df.drop(columns=["id"], errors="ignore"), use_container_width=True)

    st.divider()
    st.subheader("Add / Edit entry")

    # Form
    with st.form("entry_form", clear_on_submit=False):
        c1,c2,c3 = st.columns(3)
        with c1:
            name = st.text_input("Name*")
            position = st.text_input("Position", placeholder="ST / LW / CB …")
            team = st.text_input("Team")
        with c2:
            league = st.text_input("League")
            age = st.number_input("Age", min_value=0, max_value=60, value=0, step=1)
            value_mil = st.number_input("Market value (M€)", min_value=0.0, max_value=1000.0, value=0.0, step=0.5)
        with c3:
            rating = st.slider("Rating", 1, 5, 3)
            status_sel = st.selectbox("Status", ["Scouting","Follow","Target","Rejected","Signed"])
            tags_in = st.text_input("Tags (comma-separated)", placeholder="left-footed, high intensity")
        notes = st.text_area("Notes", placeholder="Tactical observations, strength, weakness, context…")

        c_actions = st.columns([1,1,1,4])
        with c_actions[0]:
            submit = st.form_submit_button("Save/Update")
        with c_actions[1]:
            clear = st.form_submit_button("Clear fields")
        with c_actions[2]:
            del_id = st.text_input("ID to delete", placeholder="row uuid")

    if submit:
        if not name.strip():
            st.warning("Name is required.")
        else:
            payload = {
                "name": name.strip(),
                "position": position.strip(),
                "team": team.strip(),
                "league": league.strip(),
                "age": int(age) if age else None,
                "value_mil": float(value_mil) if value_mil else None,
                "rating": int(rating),
                "status": status_sel,
                "tags": tags_in.strip(),
                "notes": notes.strip(),
                "updated_at": datetime.utcnow().isoformat(timespec="seconds"),
            }
            # If it exists by name+team+position, update; otherwise create
            existing = next((e for e in entries if e.get("name","").lower()==payload["name"].lower()
                             and e.get("team","").lower()==payload["team"].lower()
                             and e.get("position","").lower()==payload["position"].lower()), None)
            if existing:
                update_entry(st.session_state.sl_name, existing["id"], payload)
                st.success("Entry updated.")
            else:
                add_entry(st.session_state.sl_name, payload)
                st.success("Entry added.")
            _safe_rerun()

    if clear:
        for k in ("Name*","Position","Team","League","Notes","Tags (comma-separated)"): pass  # UI does not keep keys here

    if del_id and st.button("Delete by ID"):
        ok = delete_entry(st.session_state.sl_name, del_id.strip())
        if ok:
            st.success("Deleted.")
            _safe_rerun()
        else:
            st.warning("ID not found.")

# Compatibility with app.py (module.show())
def run():
    show()

