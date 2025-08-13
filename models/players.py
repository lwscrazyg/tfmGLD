from __future__ import annotations
from pydantic import BaseModel

class Player(BaseModel):
    name: str
    age: int | None = None
    position: str | None = None
    team: str | None = None
    league: str | None = None
    market_value_mil: float | None = None
    season: str | None = None
    goals: int | None = None
    assists: int | None = None
    xG: float | None = None
    minutes: int | None = None
