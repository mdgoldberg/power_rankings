from pathlib import Path

import typer

from power_rankings import cli_common
from power_rankings.name_utils import canonicalize_team_names
from power_rankings.parse_utils import get_inputs, most_recent_week
from power_rankings.season_summary import get_summary_table, plot_season_graphs


def main(
    html_filename: Path | None = typer.Argument(None, dir_okay=False),
    out_dir: Path | None = typer.Option(
        None,
        "--out-dir",
        file_okay=False,
        help="Directory to store generated plots.",
    ),
    start_week: int | None = None,
    end_week: int | None = None,
    offline: bool = cli_common.offline_option(),
    league: str | None = cli_common.league_option(),
    league_id: int | None = cli_common.league_id_option(),
    season: int | None = cli_common.season_option(),
    download_dir: Path | None = cli_common.download_dir_option(),
    leagues_file: Path | None = cli_common.leagues_file_option(),
    refresh: bool = cli_common.refresh_option(),
    headless: bool = cli_common.headless_option(default=False),
    username: str | None = cli_common.username_option(),
    password: str | None = cli_common.password_option(),
    log_level: str = cli_common.log_level_option(),
):
    """Generates rankings for a given season, given the HTML of the schedule
    and results."""
    cli_common.configure_logging(log_level)

    auto_fetch = cli_common.resolve_auto_fetch(offline)
    resolved_season = cli_common.resolve_season(auto_fetch, season)

    html_path = cli_common.ensure_schedule_or_exit(
        html_filename,
        auto_fetch=auto_fetch,
        league_id=league_id,
        league_name=league,
        leagues_file=leagues_file,
        season=resolved_season,
        download_dir=download_dir,
        force_refresh=refresh,
        headless=headless,
        username=username,
        password=password,
    )

    df = get_inputs(html_path)
    df, display_names = canonicalize_team_names(df)

    if start_week is None:
        start_week = 1

    most_recent = most_recent_week(df)
    if end_week is None:
        end_week = most_recent
    else:
        end_week = min(end_week, most_recent)

    summary_table = get_summary_table(df, start_week, end_week)
    summary_table = summary_table.rename(index=lambda name: display_names.get(name, name))

    if out_dir is not None:
        plot_season_graphs(df, start_week, end_week, out_dir)

    print()
    print(summary_table)
    print()


def cli():
    typer.run(main)


if __name__ == "__main__":
    cli()
