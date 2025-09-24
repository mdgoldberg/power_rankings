#! /usr/bin/env python3
from functools import reduce
import typer

from pathlib import Path
from power_rankings.parse_utils import get_inputs, most_recent_week
from power_rankings.season_summary import get_summary_table, plot_season_graphs

DUPES = {
    "MATTHEW GOLDBERG": "Matt Goldberg",
    "mitch hildreth, I. Reese": "mitch hildreth",
    "Joe Gowetski": "Joseph Gowetski",
    "Chris Ptak": "Christopher Ptak",
}


def main(base_filename: str, out_dir: Path, start_year: int, end_year: int):
    summaries = []
    for season in range(start_year, end_year + 1):
        season_filepath = Path(f"{base_filename}{season}.html")
        df = get_inputs(season_filepath)
        df = df.replace(DUPES)
        start_week = 1
        last_end_week = 13 if season <= 2020 else 14
        most_recent = most_recent_week(df)
        end_week = min(most_recent, last_end_week)
        year_summary = get_summary_table(df, start_week, end_week)
        summaries.append(year_summary)

        season_dir = out_dir / str(season)
        season_dir.mkdir(parents=True, exist_ok=True)
        plot_season_graphs(df, start_week, end_week, season_dir)

    aggregated = reduce(lambda a, b: a.add(b, fill_value=0), summaries)
    cols = [
        "W",
        "T",
        "L",
        "Pct",
        "Actual",
        "Exp",
        "Luck",
        "PF",
        "PA",
        "Top1",
        "Bot1",
        "Top3",
        "Bot3",
    ]
    aggregated["Pct"] = (aggregated["W"] + 0.5 * aggregated["T"]) / (
        aggregated["W"] + aggregated["T"] + aggregated["L"]
    )
    aggregated = aggregated[cols].sort_values("Pct", ascending=False).round(3)

    print()
    print(aggregated)
    print()


def cli():
    typer.run(main)


if __name__ == "__main__":
    cli()
