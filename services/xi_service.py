
# services/xi_service.py — XI logic (optimizer + persistence + comparer)
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Tuple
import json
import math
import pandas as pd

from adaptors.soccerdata_fbref import FBrefStats
from adaptors.transfermarkt import get_market_value
from services.player_service import fetch_player

FORMATIONS: Dict[str, List[str]] = {
    "4-3-3": ["GK","LB","LCB","RCB","RB","LCM","CM","RCM","LW","ST","RW"],
    "4-2-3-1": ["GK","LB","LCB","RCB","RB","LDM","CDM","RDM","LAM","CAM","RAM","ST"],
    "4-4-2": ["GK","LB","LCB","RCB","RB","LM","LCM","RCM","RM","LS","RS"],
}

# Elegibilidad de posiciones (simple). Se puede afinar por usuario.
ELIGIBLE_MAP: Dict[str, List[str]] = {
    "GK": ["GK"],
    "LB": ["LB","LWB","FB","WB","LB/LWB"],
    "RB": ["RB","RWB","FB","WB","RB/RWB"],
    "LCB": ["CB","LCB","DEF"],
    "RCB": ["CB","RCB","DEF"],
    "CM": ["CM","DM","AM","LCM","RCM","MID"],
    "LCM": ["CM","LCM","DM","MID","AM"],
    "RCM": ["CM","RCM","DM","MID","AM"],
    "LDM": ["DM","CM","MID"],
    "CDM": ["DM","CM","MID"],
    "RDM": ["DM","CM","MID"],
    "LM": ["LM","LW","MID"],
    "RM": ["RM","RW","MID"],
    "CAM": ["AM","CM"],
    "LAM": ["AM","LW","LM"],
    "RAM": ["AM","RW","RM"],
    "LW": ["LW","LM","AM"],
    "RW": ["RW","RM","AM"],
    "ST": ["ST","CF","FW"],
    "LS": ["ST","CF","FW"],
    "RS": ["ST","CF","FW"],
}

@dataclass
class Slot:
    pos: str
    player: Optional[dict] = None  # dict con campos de Player

@dataclass
class Squad:
    formation: str = "4-3-3"
    slots: Dict[str, Slot] = field(default_factory=dict)

    def __post_init__(self):
        if not self.slots:
            for p in FORMATIONS[self.formation]:
                self.slots[p] = Slot(pos=p)

    def set_formation(self, formation: str) -> None:
        self.formation = formation
        self.slots = {p: Slot(pos=p) for p in FORMATIONS[formation]}

    def add(self, pos: str, player_name: str) -> None:
        p = fetch_player(player_name)
        if p is None:
            return
        self.slots[pos].player = {
            "name": p.name,
            "team": p.team, "league": p.league, "season": p.season,
            "age": p.age, "position": p.position,
            "market_value_mil": p.market_value_mil,
            "goals": p.goals, "assists": p.assists, "xG": p.xG, "minutes": p.minutes,
        }

    def remove(self, pos: str) -> None:
        if pos in self.slots:
            self.slots[pos].player = None

    def to_dataframe(self) -> pd.DataFrame:
        rows = []
        for pos, s in self.slots.items():
            p = s.player or {}
            rows.append({
                "Pos": pos,
                "Nombre": p.get("name"),
                "Club": p.get("team"),
                "Edad": p.get("age"),
                "Liga": p.get("league"),
                "Temporada": p.get("season"),
                "Valor M€": p.get("market_value_mil"),
                "Min": p.get("minutes"),
                "Goles": p.get("goals"),
                "Asist": p.get("assists"),
                "xG": p.get("xG"),
            })
        return pd.DataFrame(rows)

    def total_value(self) -> float:
        df = self.to_dataframe()
        if "Valor M€" not in df.columns or df.empty:
            return 0.0
        return float(pd.to_numeric(df["Valor M€"], errors="coerce").fillna(0).sum())

    # ——— Persistencia ———
    def to_dict(self) -> dict:
        return {
            "formation": self.formation,
            "slots": {k: v.player for k, v in self.slots.items()},
        }

    @staticmethod
    def from_dict(d: dict) -> "Squad":
        sq = Squad(formation=d.get("formation", "4-3-3"))
        for pos in FORMATIONS[sq.formation]:
            sq.slots[pos] = Slot(pos=pos, player=d.get("slots", {}).get(pos))
        return sq

    def save(self, path: str) -> None:
        import os, tempfile
        d = os.path.dirname(path) or "."
        os.makedirs(d, exist_ok=True)
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)

    @staticmethod
    def load(path: str) -> "Squad":
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read()
            if not raw.strip():
                # Archivo vacío: devolver Squad nuevo
                return Squad()
            data = json.loads(raw)
            return Squad.from_dict(data)
        except json.JSONDecodeError as e:
            # Marcar archivo corrupto y devolver Squad nuevo
            bad = path + ".corrupt"
            try:
                import shutil; shutil.copy(path, bad)
            except Exception:
                pass
            raise ValueError(f"Archivo de plantilla corrupto: {path}") from e

# ——— Utilidades de datos ———


def load_player_pool(season: Optional[str]=None, league: Optional[str]=None) -> pd.DataFrame:
    """Carga pool de jugadores desde FBref (standard stats). Robusto a columnas y MultiIndex."""
    fb = FBrefStats(seasons=season or "2024-2025")
    df = fb._fb.read_player_season_stats(stat_type="standard").reset_index()

    # Aplanar MultiIndex si existe
    if hasattr(df.columns, "levels") and len(getattr(df.columns, "levels", [])) > 1:
        df.columns = ["_".join([str(x) for x in tup if x not in (None, "", "Unnamed: 0_level_0")]).strip("_")
                      for tup in df.columns]

    # Helper para elegir la primera columna disponible
    def pick(colnames):
        for c in colnames:
            if c in df.columns:
                return c
        return None

    # Mapeo flexible
    name_col = pick(["player","Player","name","Name","player_player"])
    pos_col  = pick(["pos","Pos","position","Position","Player positions","player_pos"])
    team_col = pick(["team","Team","squad","Squad","player_team"])
    lg_col   = pick(["league","League","comp","Comp","competition","Competition"])
    season_col = pick(["season","Season"])
    age_col  = pick(["age","Age"])
    min_col  = pick(["Playing Time_Min","min","minutes","Playing_Time_Min"])
    gls_col  = pick(["Performance_Gls","goals","Gls"])
    ast_col  = pick(["Performance_Ast","assists","Ast"])
    xg_col   = pick(["Expected_xG","xG","Exp_xG"])

    # Asegurar columnas destino
    out = pd.DataFrame({
        "name":    df[name_col] if name_col else None,
        "pos":     df[pos_col] if pos_col else None,
        "team":    df[team_col] if team_col else None,
        "league":  df[lg_col] if lg_col else None,
        "season":  df[season_col] if season_col else None,
        "age":     df[age_col] if age_col else None,
        "minutes": df[min_col] if min_col else None,
        "goals":   df[gls_col] if gls_col else None,
        "assists": df[ast_col] if ast_col else None,
        "xG":      df[xg_col] if xg_col else None,
    })

    # Normalizaciones básicas
    out["pos"] = out["pos"].astype(str).str.upper().str.strip()
    out["season"] = out["season"].astype(str).str.strip()

    if league:
        out = out[out["league"].astype(str) == str(league)]

    # Evitar KeyError garantizando existencia de columnas
    for c in ["name","pos"]:
        if c not in out.columns:
            out[c] = None

    return out.dropna(subset=["name"]).copy()
def add_market_values(df: pd.DataFrame, max_lookup:int=60) -> pd.DataFrame:
    """Añade valor de mercado (M€) a un subconjunto de jugadores para no quemar el scraping."""
    df = df.copy()
    df["market_value_mil"] = None
    names = df["name"].dropna().unique().tolist()[:max_lookup]
    for n in names:
        try:
            mv = get_market_value(n)
        except Exception:
            mv = None
        df.loc[df["name"]==n, "market_value_mil"] = mv
    return df

def zscore(s: pd.Series) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce")
    mu = s.mean(skipna=True)
    sd = s.std(skipna=True)
    if sd is None or sd == 0 or math.isnan(sd):
        return s*0
    return (s - mu) / sd

def score_players(df: pd.DataFrame, weights: Dict[str,float]) -> pd.DataFrame:
    out = df.copy()
    for m in ["minutes","goals","assists","xG"]:
        out[f"z_{m}"] = zscore(out[m])
    out["score"] = (
        weights.get("minutes",0.2)*out["z_minutes"].fillna(0) +
        weights.get("goals",0.4)*out["z_goals"].fillna(0) +
        weights.get("assists",0.2)*out["z_assists"].fillna(0) +
        weights.get("xG",0.2)*out["z_xG"].fillna(0)
    )
    return out

def slot_weights(slot: str) -> Dict[str,float]:
    slot = str(slot).upper()
    # Presets simples por línea. Ajustables.
    if slot in ("ST","LS","RS","CF","LW","RW","LAM","RAM"):
        return {"goals":0.5,"xG":0.3,"assists":0.2,"minutes":0.0}
    if slot in ("CAM","CM","LCM","RCM","CDM","LDM","RDM","LM","RM"):
        return {"assists":0.4,"minutes":0.3,"xG":0.2,"goals":0.1}
    if slot in ("LB","RB","LCB","RCB"):
        return {"minutes":0.6,"assists":0.2,"xG":0.1,"goals":0.1}
    if slot == "GK":
        return {"minutes":1.0,"goals":0.0,"assists":0.0,"xG":0.0}
    return {"minutes":0.4,"goals":0.2,"assists":0.2,"xG":0.2}

def score_for_slot(pool: pd.DataFrame, slot: str) -> pd.DataFrame:
    w = slot_weights(slot)
    out = score_players(pool, w)
    out = out.copy()
    out["score_slot"] = out["score"]
    return out

# ——— Optimización ———
def optimize_xi(formation: str, pool: pd.DataFrame, budget_mil: Optional[float]=None) -> List[Tuple[str, dict]]:
    """
    Devuelve lista [(slot_pos, player_dict), ...] de 11 jugadores.
    Usa ILP con PuLP si hay presupuesto; si no, usa Hungarian máximo por score.
    """
    slots = FORMATIONS[formation]
    pool = pool.copy().reset_index(drop=True)

    # Elegibilidad booleana
    def eligible(slot: str, row_pos: str) -> bool:
        poss = ELIGIBLE_MAP.get(slot, [slot])
        rp = str(row_pos).upper()
        return any(p in rp for p in poss)

    # Si hay presupuesto, intentamos PuLP
    if budget_mil is not None:
        try:
            import pulp
            prob = pulp.LpProblem("xi_opt", pulp.LpMaximize)
            # variables
            x = {}
            for i, row in pool.iterrows():
                for j, slot in enumerate(slots):
                    if eligible(slot, row["pos"]):
                        x[(i,j)] = pulp.LpVariable(f"x_{i}_{j}", lowBound=0, upBound=1, cat="Binary")
            # objetivo
            prob += pulp.lpSum(pool.loc[i,"score"] * x[(i,j)] for (i,j) in x)
            # cada slot exactamente 1
            for j, slot in enumerate(slots):
                prob += pulp.lpSum(x[(i,jj)] for (i,jj) in x if jj==j) == 1
            # cada jugador a lo sumo 1 slot
            for i in pool.index:
                prob += pulp.lpSum(x[(ii,j)] for (ii,j) in x if ii==i) <= 1
            # presupuesto si hay valores
            if "market_value_mil" in pool.columns and pool["market_value_mil"].notna().any():
                prob += pulp.lpSum(pool.loc[i,"market_value_mil"] * pulp.lpSum(x[(i,j)] for (i,j) in x if i==i) 
                                   for i in pool.index) <= float(budget_mil)
            prob.solve(pulp.PULP_CBC_CMD(msg=False))
            sel = []
            for (i,j), var in x.items():
                if var.value() == 1:
                    r = pool.iloc[i].to_dict()
                    sel.append((slots[j], r))
            return sel
        except Exception:
            pass  # caemos a hungarian

    # Hungarian sin presupuesto: asignamos -score como coste y bloqueamos no elegibles con gran coste
    import numpy as np
    from scipy.optimize import linear_sum_assignment

    n = len(pool)
    m = len(slots)
    cost = np.full((n, m), 1e6, dtype=float)
    for j, slot in enumerate(slots):
        slot_scored = score_for_slot(pool, slot)
        for i, row in slot_scored.iterrows():
            if eligible(slot, row["pos"]):
                cost[i, j] = -float(row.get("score_slot", row.get("score", 0.0)))
    row_ind, col_ind = linear_sum_assignment(cost)
    chosen = []
    used_slots = set()
    for i, j in zip(row_ind, col_ind):
        if cost[i,j] < 1e6 and slots[j] not in used_slots:
            chosen.append((slots[j], pool.iloc[i].to_dict()))
            used_slots.add(slots[j])
        if len(used_slots) == len(slots):
            break
    return chosen

# ——— Comparador ———
def compare_squads(a: Squad, b: Squad) -> pd.DataFrame:
    da = a.to_dataframe()
    db = b.to_dataframe()
    # agregados
    def agg(df):
        return pd.Series({
            "Valor total (M€)": pd.to_numeric(df["Valor M€"], errors="coerce").fillna(0).sum(),
            "Edad media": pd.to_numeric(df["Edad"], errors="coerce").mean(),
            "Min totales": pd.to_numeric(df["Min"], errors="coerce").fillna(0).sum(),
            "Goles totales": pd.to_numeric(df["Goles"], errors="coerce").fillna(0).sum(),
            "Asist totales": pd.to_numeric(df["Asist"], errors="coerce").fillna(0).sum(),
            "xG total": pd.to_numeric(df["xG"], errors="coerce").fillna(0).sum(),
        })
    A = agg(da); B = agg(db)
    out = pd.DataFrame({"Squad A": A, "Squad B": B})
    out["Δ (B - A)"] = out["Squad B"] - out["Squad A"]
    return out
