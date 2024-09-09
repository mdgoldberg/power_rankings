from pathlib import Path
from typing import Any
from pyquery import PyQuery as pq
import re
import numpy as np
import polars as pl


def try_float(x: Any) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def get_inputs(filename: Path) -> pl.DataFrame:
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
                "away": re.sub(r"\s+", " ", str(tds.eq(1).text()).strip()),
                "away_score_str": str(tds.eq(2).text()).strip(),
                "home_score_str": str(tds.eq(3).text()).strip(),
                "home": re.sub(r"\s+", " ", str(tds.eq(4).text()).strip()),
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

    df = pl.DataFrame(rows)

    wins_col = (
        pl.when(pl.col("score") == pl.col("opp_score"))
        .then(0.5)
        .otherwise((pl.col("score") > pl.col("opp_score")).cast(pl.Float64))
    )

    year_match = re.search(r"(20\d{2})", str(filename.resolve()))
    year = int(year_match.group(1)) if year_match else np.nan

    df = df.with_columns(wins=wins_col, season=pl.lit(year)).sort(
        ["season", "week", "score"], descending=[True, False, True]
    )
    return df


def most_recent_week(df: pl.DataFrame) -> int:
    earliest_future = int(df.select(pl.col("week")).max().item() + 1)
    for (wk,), group in sorted(df.group_by("week")):
        assert isinstance(wk, int)
        if wk < earliest_future and not group.get_column("score").is_not_null().any():
            earliest_future = wk
    return earliest_future - 1
