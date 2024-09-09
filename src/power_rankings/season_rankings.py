from pathlib import Path

import typer

from power_rankings.parse_utils import get_inputs, most_recent_week
from power_rankings.season_summary import get_summary_table, plot_season_graphs


def main(
    html_filename: Path = typer.Argument(..., exists=True, dir_okay=False),
    out_dir: Path = typer.Argument(..., file_okay=False),
    start_week: int | None = None,
    end_week: int | None = None,
):
    """Generates rankings for a given season, given the HTML of the schedule
    and results."""
    df = get_inputs(html_filename)

    if start_week is None:
        start_week = 1

    most_recent = most_recent_week(df)
    if end_week is None:
        end_week = most_recent
    else:
        end_week = min(end_week, most_recent)

    out_dir.mkdir(parents=True, exist_ok=True)

    summary_table = get_summary_table(df, start_week, end_week)

    # plot_season_graphs(df, start_week, end_week, out_dir)

    print()
    print(summary_table)
    print()


def cli():
    typer.run(main)


if __name__ == "__main__":
    cli()
