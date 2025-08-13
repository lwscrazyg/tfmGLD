"""fbref_html_matches.py – adaptor scraping FBref match‑logs

Cambia por completo el anterior enfoque de Football‑Data: ahora extrae los
*n* últimos partidos directamente de **FBref** sin depender de ninguna API.

Pasos:
1. **_search_player**: usa la búsqueda de FBref para obtener `player_id` y slug.
2. **_matchlog_url**: construye la URL del match‑log de la temporada indicada
   (`YYYY` = temporada que termina ese año; 2025 → 2024‑2025).
3. Descarga y cachea el HTML en `data/fb_html_cache` para no golpear el sitio.
4. Lee la tabla con `pandas.read_html`, filtra filas reales y devuelve los
   últimos *n* partidos con columnas traducidas.

Uso:
```python
from adaptors.fbref_html_matches import last_matches

df = last_matches("Erling Haaland", season=2025, n=5)
```
Si `season` es `None`, se usa el año actual.
"""
from __future__ import annotations

import re, unicodedata, time
from datetime import datetime
from pathlib import Path
from typing import Optional, List

import pandas as pd
import requests
from bs4 import BeautifulSoup

CACHE_DIR = Path("data/fb_html_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
HEADERS = {"User-Agent": "Mozilla/5.0 (ScoutingApp)"}
BASE = "https://fbref.com"

# ────────────────────────────────────────────────────────────────────────────────
# Helpers de depuración
# ────────────────────────────────────────────────────────────────────────────────

def _dbg(tag: str, val: object) -> None:
    print(f"[FBREF DEBUG] {tag}: {val}", flush=True)


def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")

# ────────────────────────────────────────────────────────────────────────────────
# Player search
# ────────────────────────────────────────────────────────────────────────────────

def _search_player(name: str) -> Optional[tuple[str, str]]:
    """Devuelve `(player_id, slug)` buscando en la página de resultados.

    • Intenta localizar `div.search-item-url` (nuevo layout FBref).
    • Fallback a la etiqueta `<a>` como antes.
    """
    url = f"{BASE}/en/search/search.fcgi?search={_slugify(name)}"
    _dbg("search", url)
    try:
        html = requests.get(url, headers=HEADERS, timeout=15).text
    except requests.RequestException as exc:
        _dbg("req error", exc)
        return None

    soup = BeautifulSoup(html, "lxml")

    # 1) Nuevo formato – la URL completa está en un div.search-item-url
    url_div = soup.select_one("div.search-item-url")
    if url_div and url_div.text.startswith("/en/players/"):
        href = url_div.text.strip()
    else:
        # 2) Antiguo formato – primer enlace <a href="/en/players/...">
        a = soup.select_one("a[href^='/en/players/']")
        if not a:
            _dbg("no result", name)
            return None
        href = a["href"]

    parts = href.strip("/").split("/")
    if len(parts) < 4:
        _dbg("unexpected href", href)
        return None
    pid, slug = parts[2], parts[3]
    _dbg("pid/slug", (pid, slug))
    return pid, slug

# ────────────────────────────────────────────────────────────────────────────────
# Match‑logs scraping
# ────────────────────────────────────────────────────────────────────────────────

def _matchlog_url(pid: str, slug: str, season: int) -> str:
    return f"{BASE}/en/players/{pid}/matchlogs/{season}/{slug}-Match-Logs"


def _get_html(url: str) -> str:
    fn = CACHE_DIR / (url.split("/")[-2] + "_" + url.split("/")[-1] + ".html")
    if fn.exists() and fn.stat().st_mtime > time.time() - 6 * 60 * 60:
        return fn.read_text("utf-8")
    r = requests.get(url, headers=HEADERS, timeout=15)
    _dbg("log status", r.status_code)
    r.raise_for_status()
    fn.write_text(r.text, "utf-8")
    return r.text

# ────────────────────────────────────────────────────────────────────────────────
# Public function
# ────────────────────────────────────────────────────────────────────────────────

def last_matches(name: str, season: int | None = None, n: int = 5) -> Optional[pd.DataFrame]:
    """Devuelve DataFrame con los *n* últimos partidos de la temporada indicada."""
    pid_slug = _search_player(name)
    if not pid_slug:
        return None
    pid, slug = pid_slug

    season = season or datetime.now().year
    url = _matchlog_url(pid, slug, season)
    _dbg("matchlog", url)

    try:
        html = _get_html(url)
    except Exception as exc:
        _dbg("html error", exc)
        return None

    # FBref a veces esconde la tabla en un "comment"; BeautifulSoup quita los <!-- -->
    tables = pd.read_html(html, match="Match Logs", flavor="bs4")
    if not tables:
        _dbg("no tables", slug)
        return None
    df = tables[0]

    # Líneas de encabezado repetidas → eliminar rows donde 'Rk' == 'Rk'
    df = df[df["Rk"].astype(str) != "Rk"]

    # Toma las últimas n filas reales
    df_last = df.tail(n)

    # Seleccionar columnas clave
    cols_map = {
        "Date": "Fecha",
        "Opponent": "Rival",
        "Result": "Marcador",
        "Venue": "Loc/Vis",
        "Min": "Min",
        "Gls": "Goles",
        "Ast": "Asist",
        "xG": "xG",
        "xA": "xA",
    }
    subset = [c for c in cols_map if c in df_last.columns]
    df_last = df_last[subset].rename(columns=cols_map)
    df_last["Fecha"] = pd.to_datetime(df_last["Fecha"]).dt.strftime("%d-%m-%Y")

    _dbg("rows returned", len(df_last))
    return df_last.reset_index(drop=True) if not df_last.empty else None










