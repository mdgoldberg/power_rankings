from pathlib import Path
from typing import Annotated

import polars as pl
from cyclopts import Parameter, run
from cyclopts.validators import Path as PathValidator
from rich.console import Console
from rich.table import Table

from power_rankings import cli_common
from power_rankings.name_utils import canonical_team_label, canonicalize_team_names
from power_rankings.parse_utils import get_inputs, most_recent_week


# Keep these single-codepoint to avoid Rich width miscalculations that offset table columns.
EMOJI = {
    "Lucky": "🙂",
    "VLucky": "🤪",
    "Lotto": "💸",
    "KeyWin": "😤",
    "BuiltDiff": "📣",
    "MissedOpp": "🤦",
    "Beefed": "🙈",
    "Unlucky": "😖",
    "VUnlucky": "🙃",
    "KYS": "🔫",
}


def main(
    owner_name: str,
    html_filename: Annotated[
        Path | None,
        Parameter(
            help="Path to a saved schedule HTML file; auto-downloads if omitted.",
            validator=PathValidator(dir_okay=False),
        ),
    ] = None,
    out_dir: Annotated[
        Path | None,
        Parameter(
            help="Directory to store generated plots (optional).",
            validator=PathValidator(file_okay=False),
        ),
    ] = None,
    start_week: Annotated[int | None, Parameter(help="First week (inclusive).")] = None,
    end_week: Annotated[int | None, Parameter(help="Last week (inclusive).")] = None,
    offline: Annotated[bool, cli_common.offline_option()] = False,
    league: Annotated[str | None, cli_common.league_option()] = None,
    league_id: Annotated[int | None, cli_common.league_id_option()] = None,
    season: Annotated[int | None, cli_common.season_option()] = None,
    download_dir: Annotated[Path | None, cli_common.download_dir_option()] = None,
    leagues_file: Annotated[Path | None, cli_common.leagues_file_option()] = None,
    refresh: Annotated[bool, cli_common.refresh_option()] = False,
    headless: Annotated[bool, cli_common.headless_option()] = True,
    username: Annotated[str | None, cli_common.username_option()] = None,
    password: Annotated[str | None, cli_common.password_option()] = None,
    log_level: Annotated[str, cli_common.log_level_option()] = "info",
) -> None:
    """Generates rankings for a given season, given the HTML of the schedule and results."""
    log_level = cli_common.normalize_log_level(log_level)
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

    df_polars = get_inputs(html_path)
    df_polars, display_names = canonicalize_team_names(df_polars)

    if start_week is None:
        start_week = 1

    most_recent = most_recent_week(df_polars)
    if end_week is None:
        end_week = most_recent
    else:
        end_week = min(end_week, most_recent)

    df = df_polars.filter(pl.col("week").is_between(start_week, end_week, closed="both"))
    df = df.with_columns(
        result=pl.when(pl.col("wins") == 1.0)
        .then(pl.lit("W"))
        .when(pl.col("wins") == 0.5)
        .then(pl.lit("T"))
        .otherwise(pl.lit("L")),
        week_rank=pl.col("score").rank(method="average", descending=True).over("week"),
        week_opp_rank=pl.col("opp_score").rank(method="average", descending=True).over("week"),
        team_lower=pl.col("team").str.to_lowercase(),
    )

    owner_query = owner_name.lower()
    canonical_query = canonical_team_label(owner_name).lower()
    owner_df = df.filter(
        pl.col("team_lower").str.contains(owner_query)
        | pl.col("team_lower").str.contains(canonical_query)
    ).drop("team_lower")

    owner_df = owner_df.sort("week").with_columns(
        totWins=(pl.col("result") == "W").cast(pl.Int64).cum_sum(),
        totLosses=(pl.col("result") == "L").cast(pl.Int64).cum_sum(),
        team=pl.col("team").map_elements(lambda name: display_names.get(name, name)),
        opponent=pl.col("opponent").map_elements(lambda name: display_names.get(name, name)),
    )

    owner_df = owner_df.select(
        "week",
        "totWins",
        "totLosses",
        "team",
        "result",
        "opponent",
        "score",
        "opp_score",
        "week_rank",
        "week_opp_rank",
    )

    num_players = df_polars.select(pl.col("team").n_unique()).item()
    nplayers_p1 = num_players + 1

    wins = owner_df.filter(pl.col("result") == "W").with_columns(
        Lucky=pl.when(pl.col("week_rank") >= 0.5 * nplayers_p1)
        .then(pl.lit(EMOJI["Lucky"]))
        .otherwise(pl.lit("")),
        VLucky=pl.when(pl.col("week_rank") >= 0.65 * nplayers_p1)
        .then(pl.lit(EMOJI["VLucky"]))
        .otherwise(pl.lit("")),
        Lotto=pl.when(pl.col("week_rank") >= 0.8 * nplayers_p1)
        .then(pl.lit(EMOJI["Lotto"]))
        .otherwise(pl.lit("")),
        KeyWin=pl.when(pl.col("week_opp_rank") <= 0.5 * nplayers_p1)
        .then(pl.lit(EMOJI["KeyWin"]))
        .otherwise(pl.lit("")),
        BuiltDiff=pl.when(pl.col("week_opp_rank") <= 0.25 * nplayers_p1)
        .then(pl.lit(EMOJI["BuiltDiff"]))
        .otherwise(pl.lit("")),
    )

    ties = owner_df.filter(pl.col("result") == "T")

    losses = owner_df.filter(pl.col("result") == "L").with_columns(
        MissedOpp=pl.when(pl.col("week_opp_rank") >= 0.5 * nplayers_p1)
        .then(pl.lit(EMOJI["MissedOpp"]))
        .otherwise(pl.lit("")),
        Beefed=pl.when(pl.col("week_opp_rank") >= 0.7 * nplayers_p1)
        .then(pl.lit(EMOJI["Beefed"]))
        .otherwise(pl.lit("")),
        Unlucky=pl.when(pl.col("week_rank") <= 0.5 * nplayers_p1)
        .then(pl.lit(EMOJI["Unlucky"]))
        .otherwise(pl.lit("")),
        VUnlucky=pl.when(pl.col("week_rank") <= 0.3 * nplayers_p1)
        .then(pl.lit(EMOJI["VUnlucky"]))
        .otherwise(pl.lit("")),
        KYS=pl.when(pl.col("week_rank") <= 0.2 * nplayers_p1)
        .then(pl.lit(EMOJI["KYS"]))
        .otherwise(pl.lit("")),
    )

    console = Console()

    def _print_table(title: str, frame: pl.DataFrame) -> None:
        console.print()
        console.print(title)
        table = Table(show_header=True, header_style="bold")
        for col in frame.columns:
            table.add_column(col)
        for row in frame.iter_rows(named=True):
            table.add_row(*[str(row[col]) for col in frame.columns])
        console.print(table)

    _print_table("Results:", owner_df)
    _print_table("Wins:", wins)
    _print_table("Losses:", losses)
    if not ties.is_empty():
        _print_table("Ties (!! 👔 !!):", ties)


def cli() -> None:
    run(main)


if __name__ == "__main__":
    cli()
