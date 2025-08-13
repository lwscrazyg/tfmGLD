from adaptors.transfermarkt import get_market_value
from adaptors.soccerdata_fbref import FBrefStats
from models.players import Player

_fb = FBrefStats()  # instancia global; se cachea internamente

def fetch_player(name: str) -> Player | None:
    stats = _fb.get_player_stats(name)
    if stats is None:
        return None

    mv = get_market_value(name)  # puede ser None
    return Player(
        name=name,
        age=stats.get("age"),
        position=stats.get("position"),
        team=stats.get("team"),
        league=stats.get("league"),
        market_value_mil=mv,
        season=stats.get("season"),
        goals=stats.get("goals"),
        assists=stats.get("assists"),
        xG=stats.get("xG"),
        minutes=stats.get("minutes"),
    )
