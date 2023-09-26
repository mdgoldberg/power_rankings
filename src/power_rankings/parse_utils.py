from pathlib import Path
from typing import Any
from pyquery import PyQuery as pq
import re
import numpy as np
import pandas as pd


def try_float(x: Any) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def get_inputs(filename: Path) -> pd.DataFrame:
    with open(filename) as f:
        html = f.read()

    doc = pq(html)
    tables = doc("div.matchup--table table.Table")
    rows = []
    for i, table in enumerate(tables.items()):
        for tr in table("tbody tr").items():
            tds = tr("td")
            game = {
                "week": i + 1,
                "away": re.sub(r"\s+", " ", tds.eq(1).text().strip()),
                "away_score_str": tds.eq(2).text().strip(),
                "home_score_str": tds.eq(3).text().strip(),
                "home": re.sub(r"\s+", " ", tds.eq(4).text().strip()),
            }
            home_entry = {
                "week": game["week"],
                "team": game["home"],
                "opponent": game["away"],
                "score": try_float(game["home_score_str"]),
                "opp_score": try_float(game["away_score_str"]),
            }
            away_entry = {
                "week": game["week"],
                "team": game["away"],
                "opponent": game["home"],
                "score": try_float(game["away_score_str"]),
                "opp_score": try_float(game["home_score_str"]),
            }
            rows.append(home_entry)
            rows.append(away_entry)

    df = pd.DataFrame(rows)

    def wins_func(team_score, opp_score):
        """Two arguments are team and opponent scores. Returns 1 if team won,
        0.5 if tied, 0 if team lost."""
        return (
            1.0 * (team_score > opp_score) + 0.5 * (team_score == opp_score)
            if team_score + opp_score > 0.0
            else 0.0
        )

    df["wins"] = [wins_func(score, opp) for score, opp in zip(df.score, df.opp_score)]
    year_match = re.search(r"(20\d{2})", str(filename.resolve()))
    year = int(year_match.group(1)) if year_match else np.nan
    df["season"] = year
    df = df.sort_values(["season", "week", "score"], ascending=(False, True, False))
    return df


def most_recent_week(df: pd.DataFrame) -> int:
    earliest_future = int(df.week.max().item() + 1)
    for wk, group in df.groupby("week"):
        assert isinstance(wk, int)
        if wk < earliest_future and not group.score.any():
            earliest_future = wk
    return earliest_future - 1
