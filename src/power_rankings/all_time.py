#! /usr/bin/env python3
from functools import reduce
from pathlib import Path

import typer

from power_rankings import cli_common
from power_rankings.parse_utils import get_inputs, most_recent_week
from power_rankings.season_summary import get_summary_table, plot_season_graphs

DUPES = {
    "MATTHEW GOLDBERG": "Matt Goldberg",
    "mitch hildreth, I. Reese": "mitch hildreth",
    "Joe Gowetski": "Joseph Gowetski",
    "Chris Ptak": "Christopher Ptak",
}


def main(
    base_filename: str | None = typer.Argument(
        None,
        help="Prefix for stored HTML files (e.g. html/jlssffl/).",
    ),
    out_dir: Path | None = typer.Argument(None, file_okay=False),
    start_year: int = typer.Argument(..., help="First season (inclusive)."),
    end_year: int = typer.Argument(..., help="Last season (inclusive)."),
    offline: bool = cli_common.offline_option(),
    league: str | None = cli_common.league_option(),
    league_id: int | None = cli_common.league_id_option(),
    download_dir: Path | None = cli_common.download_dir_option(),
    leagues_file: Path | None = cli_common.leagues_file_option(),
    refresh: bool = cli_common.refresh_option(),
    headless: bool = cli_common.headless_option(default=True),
    username: str | None = cli_common.username_option(),
    password: str | None = cli_common.password_option(),
    log_level: str = cli_common.log_level_option(),
):
    cli_common.configure_logging(log_level)

    auto_fetch = cli_common.resolve_auto_fetch(offline)
    summaries = []
    if base_filename is None and not auto_fetch:
        typer.secho("Provide base_filename or omit --offline to auto-fetch schedules.", fg="red", err=True)
        raise typer.Exit(code=2)
    if auto_fetch and league_id is None and league is None:
        typer.secho("Provide --league-id or --league when auto-fetching schedules.", fg="red", err=True)
        raise typer.Exit(code=2)

    for season in range(start_year, end_year + 1):
        season_path = _season_path(
            base_filename=base_filename,
            download_dir=download_dir,
            league_id=league_id,
            league_name=league,
            season=season,
        )
        html_path = cli_common.ensure_schedule_or_exit(
            season_path,
            auto_fetch=auto_fetch,
            league_id=league_id,
            league_name=league,
            leagues_file=leagues_file,
            season=season,
            download_dir=download_dir,
            force_refresh=refresh,
            headless=headless,
            username=username,
            password=password,
        )

        season_filepath = html_path
        df = get_inputs(season_filepath)
        df = df.replace(DUPES)
        start_week = 1
        last_end_week = 13 if season <= 2020 else 14
        most_recent = most_recent_week(df)
        end_week = min(most_recent, last_end_week)
        year_summary = get_summary_table(df, start_week, end_week)
        summaries.append(year_summary)

        if out_dir is not None:
            season_dir = out_dir / str(season)
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


def _season_path(
    base_filename: str | None,
    download_dir: Path | None,
    league_id: int | None,
    league_name: str | None,
    season: int,
) -> Path | None:
    if base_filename is not None:
        return Path(f"{base_filename}{season}.html")

    if league_id is None and league_name is None:
        return None

    target_dir = download_dir
    if target_dir is None:
        if league_name:
            target_dir = Path("html") / league_name
        elif league_id is not None:
            target_dir = Path("html") / f"league_{league_id}"
        else:
            return None
    return target_dir / f"{season}.html"


def cli():
    typer.run(main)


if __name__ == "__main__":
    cli()
