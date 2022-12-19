#! /usr/bin/env python3
import typer

from pathlib import Path
from power_rankings.parse_utils import get_inputs
from power_rankings.season_summary import get_summary_table

DUPES = {
    "MATTHEW GOLDBERG": "Matt Goldberg",
    "mitch hildreth, I. Reese": "mitch hildreth",
}


def main(base_filename: str, start_year: int, end_year: int = 2022):
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
        df = df.replace(DUPES)
        start_week = 1
        end_week = 13 if season <= 2020 else 14
        year_summary = get_summary_table(df, start_week, end_week)
        summaries.append(year_summary)

    cols = [
        "W",
        "T",
        "L",
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
    aggregated = sum(summaries)[cols]

    __import__("ipdb").set_trace()
    #
    # for title, counter in counters.items():
    #     print(("{} Rankings:".format(title)))
    #     for i, (name, num) in enumerate(counter.most_common()):
    #         print(("{:2}. {:18} {:.3f}".format(i + 1, name, num)))
    # print()


def cli():
    typer.run(main)


if __name__ == "__main__":
    cli()
