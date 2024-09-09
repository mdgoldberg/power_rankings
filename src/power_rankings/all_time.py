#! /usr/bin/env python3
import polars as pl
from functools import reduce
import typer

from pathlib import Path
from power_rankings.parse_utils import get_inputs
from power_rankings.season_summary import get_summary_table, plot_season_graphs

DUPES = {
    "MATTHEW GOLDBERG": "Matt Goldberg",
    "mitch hildreth, I. Reese": "mitch hildreth",
    "Joe Gowetski": "Joseph Gowetski",
}


def main(base_filename: str, out_dir: Path, start_year: int, end_year: int = 2023):
    # rfs = {
    #     "Expected Wins": rank_functions.expected_wins,
    #     "Pct": rank_functions.expected_win_pct,
    #     "Luck Wins": rank_functions.luck_rankings,
    #     "Wins": rank_functions.get_wins,
    #     "Points For": rank_functions.points_for,
    # }
    summaries = []
    for season in range(start_year, end_year + 1):
        season_filepath = Path(f"{base_filename}{season}.html")
        df = get_inputs(season_filepath)
        df = df.with_columns(pl.col("team", "opponent").replace(DUPES))
        start_week = 1
        end_week = 13 if season <= 2020 else 14
        year_summary = get_summary_table(df, start_week, end_week)
        summaries.append(year_summary)

        season_dir = out_dir / str(season)
        season_dir.mkdir(parents=True, exist_ok=True)
        # plot_season_graphs(df, start_week, end_week, season_dir)

    aggregated = reduce(lambda a, b: a.add(b, fill_value=0), summaries)
    cols = [
        "W",
        "T",
        "L",
        "ExpWinPct",
        "ActualWins",
        "ExpWins",
        "Luck",
        "PF",
        "PA",
        "Top1",
        "Top3",
        "Bot3",
        "Bot1",
    ]
    aggregated["ExpWinPct"] = (aggregated["W"] + 0.5 * aggregated["T"]) / (
        aggregated["W"] + aggregated["T"] + aggregated["L"]
    )
    aggregated = aggregated[cols].sort_values("ExpWinPct", ascending=False).round(4)

    print()
    print(aggregated)
    print()


def cli():
    typer.run(main)


if __name__ == "__main__":
    cli()
