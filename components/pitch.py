# components/pitch.py
import streamlit as st
from pathlib import Path

FIELD_IMG = str(Path(__file__).parent / "assets/pitch.png")

CSS = """
<style>
.pitch-container { position: relative; width: 100%; }
.pitch-container img { width: 100%; }
.slot {
  position: absolute; width: 70px; height: 70px; border-radius: 50%;
  background:#0c713d33; backdrop-filter: blur(2px);
  display:flex; align-items:center; justify-content:center;
  font-weight:600; cursor:pointer;
}
</style>
"""

# coordenadas aproximadas (x%, y%) para 4-3-3 sobre un lienzo 100×100
POS_COORDS_433 = {
    "GK":  (50, 92),
    "LB":  (18, 78), "LCB": (38, 70), "RCB": (62, 70), "RB": (82, 78),
    "LCM": (30, 50), "CM":  (50, 46), "RCM":(70, 50),
    "LW":  (15, 25), "ST":  (50, 20), "RW": (85, 25),
}

def draw_pitch(squad):
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown('<div class="pitch-container">', unsafe_allow_html=True)
    st.markdown(f'<img src="{FIELD_IMG}">', unsafe_allow_html=True)

    coords = POS_COORDS_433  # TODO: mapear según formación
    for pos, (x, y) in coords.items():
        label = squad.slots[pos].player["name"].split()[0] if squad.slots[pos].player else pos
        st.markdown(
            f'<div class="slot" style="left:{x}%; top:{y}%" '
            f'onclick="window.parent.postMessage({{slot:\'{pos}\'}}, \'*\')">{label}</div>',
            unsafe_allow_html=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)
