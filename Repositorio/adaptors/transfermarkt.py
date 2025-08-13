"""transfermarkt.py – adaptor con DEBUG prints
Versión robusta y formateada correctamente. Obtiene el valor de mercado en **M€**
para un nombre de jugador o una URL directa de Transfermarkt.

Estrategia resumida:
1. Si el argumento es una URL (`http`), se scrapea esa página directamente.
2. Si es un nombre, se normaliza y se busca en los dominios .com / .es / .de.
3. De la lista de resultados se extraen TODAS las URLs de perfil y se prueban
   hasta encontrar una con valor ≠ None.
4. El valor se obtiene primero de un bloque JSON (`TM.initData`) y, si no
   existe o vale 0, de un texto visible «€ 25.00 m / k».
5. Incluye `print()` de depuración con prefijo `[TM DEBUG]`.
"""
from __future__ import annotations

import json
import re
import time
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

import bs4
import requests

from utils.text import normalize

# ────────────────────────────────────────────────────────────────────────────────
# Constantes
# ────────────────────────────────────────────────────────────────────────────────
_BASE_DOMAINS = [
    "https://www.transfermarkt.com",
    "https://www.transfermarkt.es",
    "https://www.transfermarkt.de",
]

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ScoutingApp/0.1; +https://example.com)",
    "Accept-Language": "en-US,en;q=0.8",  # evita redirecciones al .de/.es
}

_JSON_RX = re.compile(r"TM\.initData\s*=\s*(\{.*?\});", re.S)
_VAL_RX = re.compile(r"€\s?([\d.,]+)\s?([mk])", re.I)

# Carpeta donde se guarda HTML de depuración si algo falla
_CACHE_DIR = Path("data/_debug_tm")
_CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ────────────────────────────────────────────────────────────────────────────────
# Utilidades internas
# ────────────────────────────────────────────────────────────────────────────────

def _dbg(label: str, value: object) -> None:
    """Imprime logs de depuración siempre con flush=True."""
    print(f"[TM DEBUG] {label}: {value}", flush=True)


def _candidate_player_links(html: str, base: str) -> list[str]:
    """Extrae todas las URLs de perfil de jugador de la página de resultados."""
    soup = bs4.BeautifulSoup(html, "lxml")
    links: list[str] = []
    for a in soup.select("a[href*='/profil/spieler/']"):
        href = a.get("href", "")
        if not href:
            continue
        full = href if href.startswith("http") else base + href
        if full not in links:
            links.append(full)
    if not links:
        (_CACHE_DIR / "last_search.html").write_text(html[:20_000], "utf-8")
        _dbg("candidate links", "0 — guardado last_search.html para inspección")
    else:
        _dbg("candidate links", links[:5])
    return links


def _value_from_json(html: str) -> float | None:
    """Intenta sacar el valor de mercado del bloque JSON interno."""
    m = _JSON_RX.search(html)
    if not m:
        return None
    try:
        raw_val = int(json.loads(m.group(1)).get("marketValue", 0))
    except (json.JSONDecodeError, ValueError):
        return None

    if raw_val == 0:
        return None

    # Algunos dominios (p. ej. .es) devuelven céntimos; otros, euros.
    euros = raw_val / 100 if raw_val >= 1_000_000_000 else raw_val
    return round(euros / 1_000_000, 3)


def _value_from_html(html: str) -> float | None:
    """Fallback: expresión regular sobre el texto visible «€ 25.00 m» o «k»."""
    m = _VAL_RX.search(html)
    if not m:
        return None

    raw_num, unit = m.groups()
    raw_num = raw_num.replace(" ", "")  # narrow no‑break space

    # Normaliza separadores decimales
    if "," in raw_num and "." in raw_num:
        # «1.234,56» → punto miles, coma decimal
        if raw_num.find(".") < raw_num.find(","):
            raw_num = raw_num.replace(".", "").replace(",", ".")
        else:  # «1,234.56» poco común
            raw_num = raw_num.replace(",", "")
    elif "," in raw_num:
        raw_num = raw_num.replace(",", ".")
    # solo punto: ya está ok

    try:
        value = float(raw_num)
    except ValueError:
        _dbg("parse float err", raw_num)
        return None

    if unit.lower() == "k":
        value *= 0.001  # miles → millones
    return round(value, 3)


def _scrape_profile(url: str) -> float | None:
    """Scrapea un perfil concreto y devuelve el valor en millones o None."""
    _dbg("profile", url)
    try:
        r = requests.get(url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        html = r.text
    except requests.RequestException as exc:
        _dbg("profile req err", exc)
        return None

    mv = _value_from_json(html) or _value_from_html(html)
    _dbg("scraped value", mv)
    return mv


# ────────────────────────────────────────────────────────────────────────────────
# API pública
# ────────────────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=512)
def get_market_value(query: str) -> float | None:
    """Devuelve el valor de mercado (M€) o `None`.

    * Si `query` comienza por «http», se trata como URL directa.
    * Si es un nombre, se normaliza y se busca en varios dominios.
    * El primer perfil que arroje un valor ≠ None se devuelve.
    """
    _dbg("query", query)

    # Caso URL directa
    if query.startswith("http"):
        return _scrape_profile(query)

    # Caso nombre
    slug = quote_plus(normalize(query))
    _dbg("slug", slug)

    for base in _BASE_DOMAINS:
        search_url = f"{base}/schnellsuche/ergebnis/schnellsuche?query={slug}"
        _dbg("search", search_url)
        try:
            r = requests.get(search_url, headers=_HEADERS, timeout=12)
            _dbg("search status", r.status_code)
            r.raise_for_status()
            for player_url in _candidate_player_links(r.text, base):
                time.sleep(0.5)  # pequeño delay para no abusar
                mv = _scrape_profile(player_url)
                if mv is not None:
                    _dbg("return", mv)
                    return mv
        except requests.RequestException as exc:
            _dbg("search err", exc)
            continue

    _dbg("result", None)
    return None









