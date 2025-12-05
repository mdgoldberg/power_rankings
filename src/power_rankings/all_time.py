from pathlib import Path
from typing import Annotated

import polars as pl
from cyclopts import Parameter, run
from cyclopts.validators import Path as PathValidator
from rich.console import Console
from rich.table import Table

from power_rankings import cli_common
from power_rankings.name_utils import canonicalize_team_names
from power_rankings.parse_utils import get_inputs, most_recent_week
from power_rankings.season_summary import (
    get_summary_table,
    order_summary_columns,
    plot_season_graphs,
)


def main(
    start_year: Annotated[int, Parameter(help="First season (inclusive).")],
    end_year: Annotated[int, Parameter(help="Last season (inclusive).")],
    base_filename: Annotated[
        str | None,
        Parameter(help="Prefix for stored HTML files (e.g. html/jlssffl/)."),
    ] = None,
    out_dir: Annotated[
        Path | None,
        Parameter(
            help="Directory to store generated plots.",
            validator=PathValidator(file_okay=False),
        ),
    ] = None,
    offline: Annotated[bool, cli_common.offline_option()] = False,
    league: Annotated[str | None, cli_common.league_option()] = None,
    league_id: Annotated[int | None, cli_common.league_id_option()] = None,
    download_dir: Annotated[Path | None, cli_common.download_dir_option()] = None,
    leagues_file: Annotated[Path | None, cli_common.leagues_file_option()] = None,
    refresh: Annotated[bool, cli_common.refresh_option()] = False,
    headless: Annotated[bool, cli_common.headless_option()] = True,
    username: Annotated[str | None, cli_common.username_option()] = None,
    password: Annotated[str | None, cli_common.password_option()] = None,
    log_level: Annotated[str, cli_common.log_level_option()] = "info",
) -> None:
    log_level = cli_common.normalize_log_level(log_level)
    cli_common.configure_logging(log_level)

    auto_fetch = cli_common.resolve_auto_fetch(offline)
    if base_filename is None and not auto_fetch:
        cli_common.abort(
            "Provide base_filename or omit --offline to auto-fetch schedules.", exit_code=2
        )
    if auto_fetch and league_id is None and league is None:
        cli_common.abort(
            "Provide --league-id or --league when auto-fetching schedules.", exit_code=2
        )

    summaries: list[pl.DataFrame] = []
    latest_names: dict[str, str] = {}
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

        df = get_inputs(html_path)
        df, season_display = canonicalize_team_names(df)
        latest_names.update(season_display)
        start_week = 1
        last_end_week = 13 if season <= 2020 else 14
        most_recent = most_recent_week(df)
        end_week = min(most_recent, last_end_week)
        year_summary = get_summary_table(df, start_week, end_week, include_internal=True)
        summaries.append(year_summary)

        if out_dir is not None:
            season_dir = out_dir / str(season)
            plot_season_graphs(df, start_week, end_week, season_dir)

    if not summaries:
        cli_common.warn_and_exit("No summaries computed for the requested range.")

    stacked = pl.concat(summaries, how="diagonal")
    aggregated = (
        stacked.group_by("team")
        .agg(
            W=pl.col("W").sum(),
            T=pl.col("T").sum(),
            L=pl.col("L").sum(),
            actual_wins=pl.col("actual_wins").sum(),
            actual_losses=pl.col("actual_losses").sum(),
            actual_ties=pl.col("actual_ties").sum(),
            Exp_numeric=pl.col("Exp_numeric").sum(),
            games_played=pl.col("games_played").sum(),
            Luck=pl.col("Luck").sum(),
            PF=pl.col("PF").sum(),
            PA=pl.col("PA").sum(),
            Top1=pl.col("Top1").sum(),
            Bot1=pl.col("Bot1").sum(),
            **{"Faced-Bot1": pl.col("Faced-Bot1").sum()},
            Top3=pl.col("Top3").sum(),
            Bot3=pl.col("Bot3").sum(),
        )
        .with_columns(
            Pct=(pl.col("W") + 0.5 * pl.col("T")) / (pl.col("W") + pl.col("T") + pl.col("L")),
            exp_losses=pl.col("games_played") - pl.col("Exp_numeric"),
            record=pl.when(pl.col("actual_ties") > 0)
            .then(
                pl.concat_str(
                    [
                        pl.col("actual_wins").cast(pl.Utf8),
                        pl.lit("-"),
                        pl.col("actual_losses").cast(pl.Utf8),
                        pl.lit("-"),
                        pl.col("actual_ties").cast(pl.Utf8),
                    ]
                )
            )
            .otherwise(
                pl.concat_str(
                    [
                        pl.col("actual_wins").cast(pl.Utf8),
                        pl.lit("-"),
                        pl.col("actual_losses").cast(pl.Utf8),
                    ]
                )
            ),
            Exp=pl.concat_str(
                [
                    pl.col("Exp_numeric").round(3).cast(pl.Utf8),
                    pl.lit("-"),
                    pl.col("exp_losses").round(3).cast(pl.Utf8),
                ]
            ),
        )
        .rename({"record": "Record"})
        .drop(
            [
                "actual_wins",
                "actual_losses",
                "actual_ties",
                "Exp_numeric",
                "exp_losses",
                "games_played",
            ]
        )
        .sort("Pct", descending=True)
        .with_columns(pl.col(pl.Float64).round(3))
    )
    aggregated = aggregated.with_columns(
        team=pl.col("team").map_elements(lambda name: latest_names.get(name, name))
    )
    aggregated = order_summary_columns(aggregated)

    console = Console()
    table = Table(show_header=True, header_style="bold")
    for col in aggregated.columns:
        table.add_column(col)
    for row in aggregated.iter_rows(named=True):
        table.add_row(*[str(row[col]) for col in aggregated.columns])

    console.print()
    console.print(table)
    console.print()


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


def cli() -> None:
    run(main)


if __name__ == "__main__":
    cli()
