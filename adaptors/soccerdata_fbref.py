# adaptors/soccerdata_fbref.py  (versión corregida)
from __future__ import annotations
import pathlib
import pandas as pd
import soccerdata as sd
from rapidfuzz import process
from utils.text import normalize

DATA_DIR = pathlib.Path("data/fb_cache")

class FBrefStats:
    def __init__(self, seasons="2024-2025",
                 leagues="Big 5 European Leagues Combined"):
        self._fb = sd.FBref(seasons=seasons,
                            leagues=leagues,
                            data_dir=DATA_DIR)

    def _player_row(self, name: str) -> pd.Series | None:
        df = (
            self._fb.read_player_season_stats(stat_type="standard")
            .reset_index()
        )
        # Aplana MultiIndex en columnas
        df.columns = [
            "_".join([c for c in col if c]) if isinstance(col, tuple) else col
            for col in df.columns
        ]

        # ▸ Normaliza toda la columna UNA sola vez (columna auxiliar)
        df["name_norm"] = df["player"].apply(normalize)
        target = normalize(name)

        # 1) Coincidencia exacta normalizada
        exact = df[df["name_norm"] == target]
        if not exact.empty:
            return exact.sort_values("season").iloc[-1]

        # 2) Fuzzy-match sobre la columna normalizada
        choice, score, idx = process.extractOne(
            target, df["name_norm"], score_cutoff=80
        ) or (None, None, None)
        return None if choice is None else df.iloc[idx]

    def get_player_stats(self, name: str) -> dict | None:
        row = self._player_row(name)
        if row is None:
            return None

        return {
            "season":   row["season"],
            "team":     row.get("team"),
            "league":   row.get("league"),
            "age":      row.get("age"),
            "position": row.get("pos"),
            "matches":  int(row.get("Playing Time_MP", 0)),
            "minutes":  int(row.get("Playing Time_Min", 0)),
            "goals":    int(row.get("Performance_Gls", 0)),
            "assists":  int(row.get("Performance_Ast", 0)),
            "xG":       float(row.get("Expected_xG", 0))
        }



