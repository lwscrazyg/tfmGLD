# services/shortlist_service.py — Shortlist & Notes (service) v1.0
from __future__ import annotations
import json
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

SHORTLISTS_DIR = Path("data/shortlists")
SHORTLISTS_DIR.mkdir(parents=True, exist_ok=True)

SCHEMA_VERSION = 1

def _file(name: str) -> Path:
    safe = "".join(c for c in name if c.isalnum() or c in ("_","-")).strip() or "default"
    return SHORTLISTS_DIR / f"{safe}.json"

def list_shortlists() -> List[str]:
    return sorted([p.stem for p in SHORTLISTS_DIR.glob("*.json")]) or ["default"]

def create_shortlist_if_missing(name: str) -> None:
    p = _file(name)
    if not p.exists():
        payload = {
            "name": name,
            "schema_version": SCHEMA_VERSION,
            "created_at": datetime.utcnow().isoformat(timespec="seconds"),
            "updated_at": None,
            "entries": []
        }
        p.write_text(json.dumps(payload, indent=2, ensure_ascii=False))

def load_shortlist(name: str) -> Dict[str, Any]:
    p = _file(name)
    if not p.exists():
        create_shortlist_if_missing(name)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        # fallback vacío
        return {"name": name, "schema_version": SCHEMA_VERSION, "entries": []}

def save_shortlist(name: str, data: Dict[str, Any]) -> None:
    data["updated_at"] = datetime.utcnow().isoformat(timespec="seconds")
    _file(name).write_text(json.dumps(data, indent=2, ensure_ascii=False))

def delete_shortlist(name: str) -> None:
    p = _file(name)
    if p.exists():
        p.unlink(missing_ok=True)

# ——— Entradas ———
BASE_FIELDS = ["id","name","position","team","league","age","value_mil","rating","status","tags","notes","updated_at"]

def _sanitize_entry(e: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: e.get(k) for k in BASE_FIELDS if k in e}
    out.setdefault("id", str(uuid.uuid4()))
    out.setdefault("rating", 3)
    out.setdefault("status", "Scouting")
    out.setdefault("tags", "")
    out.setdefault("updated_at", datetime.utcnow().isoformat(timespec="seconds"))
    return out

def add_entry(shortlist: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = load_shortlist(shortlist)
    entry = _sanitize_entry(payload)
    # Evitar duplicados exactos por (name, team, position)
    if any(e.get("name","").lower()==entry["name"].lower() and
           (e.get("team","") or "").lower()==(entry.get("team","") or "").lower() and
           (e.get("position","") or "").lower()==(entry.get("position","") or "").lower()
           for e in data.get("entries", [])):
        # si existe, actualiza notas/estado/rating/etc. sin duplicar
        for e in data["entries"]:
            if (e.get("name","").lower()==entry["name"].lower() and
                (e.get("team","") or "").lower()==(entry.get("team","") or "").lower() and
                (e.get("position","") or "").lower()==(entry.get("position","") or "").lower()):
                e.update({k:v for k,v in entry.items() if k!="id"})
                e["updated_at"] = datetime.utcnow().isoformat(timespec="seconds")
        save_shortlist(shortlist, data)
        return entry
    data.setdefault("entries", []).append(entry)
    save_shortlist(shortlist, data)
    return entry

def update_entry(shortlist: str, entry_id: str, payload: Dict[str, Any]) -> bool:
    data = load_shortlist(shortlist)
    found = False
    for e in data.get("entries", []):
        if e.get("id") == entry_id:
            e.update({k:v for k,v in payload.items() if k in BASE_FIELDS and k!="id"})
            e["updated_at"] = datetime.utcnow().isoformat(timespec="seconds")
            found = True
            break
    if found:
        save_shortlist(shortlist, data)
    return found

def delete_entry(shortlist: str, entry_id: str) -> bool:
    data = load_shortlist(shortlist)
    before = len(data.get("entries", []))
    data["entries"] = [e for e in data.get("entries", []) if e.get("id") != entry_id]
    after = len(data["entries"])
    if after < before:
        save_shortlist(shortlist, data)
        return True
    return False

# ——— CSV ———
def export_shortlist_to_csv(shortlist: str) -> str:
    import pandas as pd
    data = load_shortlist(shortlist)
    df = pd.DataFrame(data.get("entries", []), columns=BASE_FIELDS)
    fp = str(_file(shortlist).with_suffix(".csv"))
    df.to_csv(fp, index=False)
    return fp

def import_shortlist_from_csv(shortlist: str, file_like) -> None:
    import pandas as pd
    create_shortlist_if_missing(shortlist)
    df = pd.read_csv(file_like)
    # normalizar columnas
    cols_map = {c.lower(): c for c in df.columns}
    def pick(row, *names):
        for n in names:
            if n in cols_map:
                return row[cols_map[n]]
        return None
    data = load_shortlist(shortlist)
    for _, row in df.iterrows():
        payload = {
            "id": str(pick(row, "id")) if pick(row, "id") else str(uuid.uuid4()),
            "name": pick(row, "name","nombre"),
            "position": pick(row, "position","pos"),
            "team": pick(row, "team","equipo","club"),
            "league": pick(row, "league","liga","comp"),
            "age": pick(row, "age","edad"),
            "value_mil": pick(row, "value_mil","market_value_mil","valor"),
            "rating": pick(row, "rating","score"),
            "status": pick(row, "status","estado"),
            "tags": pick(row, "tags"),
            "notes": pick(row, "notes","nota","observaciones"),
            "updated_at": pick(row, "updated_at"),
        }
        # limpia tipos básicos
        if payload["age"] not in (None, ""):
            try: payload["age"] = int(payload["age"])
            except: payload["age"] = None
        if payload["value_mil"] not in (None, ""):
            try: payload["value_mil"] = float(payload["value_mil"])
            except: payload["value_mil"] = None
        if payload["rating"] not in (None, ""):
            try:
                r = int(payload["rating"])
                payload["rating"] = max(1, min(5, r))
            except:
                payload["rating"] = 3
        payload = _sanitize_entry(payload)
        # si existe id, actualiza; si no, añade
        existing = next((e for e in data.get("entries", []) if e.get("id")==payload["id"]), None)
        if existing:
            existing.update({k:v for k,v in payload.items() if k!="id"})
        else:
            data.setdefault("entries", []).append(payload)
    save_shortlist(shortlist, data)
