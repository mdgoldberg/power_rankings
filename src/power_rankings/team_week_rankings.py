import logging
import re
from pathlib import Path
from typing import Annotated, Iterable

import polars as pl
from cyclopts import Parameter, run
from cyclopts.validators import Number
from rich.console import Console
from rich.table import Table

from power_rankings import cli_common
from power_rankings.league_config import PRIMARY_CONFIG_NAME, load_league_mapping
from power_rankings.name_utils import canonicalize_team_names
from power_rankings.parse_utils import get_inputs, most_recent_week

logger = logging.getLogger(__name__)


def main(
    start_season: Annotated[
        int | None, Parameter(help="Earliest season (year) to include.")
    ] = None,
    end_season: Annotated[int | None, Parameter(help="Latest season (year) to include.")] = None,
    leagues: Annotated[
        list[str] | None,
        Parameter(
            name=("league", "-l"),
            help=f"League name from {PRIMARY_CONFIG_NAME}. Repeat the option to include multiple leagues.",
            show_default=False,
        ),
    ] = None,
    end_week: Annotated[
        int | None,
        Parameter(
            help="Cutoff week (inclusive) when computing each season summary.",
            validator=Number(gte=1, lte=18),
        ),
    ] = None,
    sort_column: Annotated[
        str,
        Parameter(help="Output column to sort by. Must match one of the table headers."),
    ] = "Score",
    sort_direction: Annotated[
        str,
        Parameter(help="Sorting direction for the selected column (asc or desc)."),
    ] = "desc",
    offline: Annotated[bool, cli_common.offline_option()] = False,
    download_dir: Annotated[Path | None, cli_common.download_dir_option()] = None,
    leagues_file: Annotated[Path | None, cli_common.leagues_file_option()] = None,
    refresh: Annotated[bool, cli_common.refresh_option()] = False,
    headless: Annotated[bool, cli_common.headless_option()] = True,
    username: Annotated[str | None, cli_common.username_option()] = None,
    password: Annotated[str | None, cli_common.password_option()] = None,
    log_level: Annotated[str, cli_common.log_level_option()] = "info",
) -> None:
    """Rank individual team performances by week across one or more leagues."""
    log_level = cli_common.normalize_log_level(log_level)
    cli_common.configure_logging(log_level)

    auto_fetch = cli_common.resolve_auto_fetch(offline)

    try:
        sort_dir = _normalize_sort_direction(sort_direction)
    except ValueError as exc:
        cli_common.abort(str(exc), exit_code=2)

    league_mapping = load_league_mapping(leagues_file)
    try:
        selected_leagues = _resolve_leagues(leagues, league_mapping)
    except ValueError as exc:
        cli_common.abort(str(exc), exit_code=2)

    try:
        seasons = _resolve_seasons(start_season, end_season, selected_leagues, download_dir)
    except ValueError as exc:
        cli_common.abort(str(exc), exit_code=2)

    if not seasons:
        cli_common.abort(
            "No seasons to process; provide --start-season/--end-season or download HTML first.",
            exit_code=2,
        )

    frames: list[pl.DataFrame] = []
    latest_names: dict[str, tuple[int, str]] = {}
    for league_name in selected_leagues:
        for season in seasons:
            season_dir = _season_dir(league_name, download_dir)
            html_arg = None if auto_fetch else season_dir / f"{season}.html"
            try:
                resolved_html = cli_common.ensure_schedule_or_exit(
                    html_arg,
                    auto_fetch=auto_fetch,
                    league_id=None,
                    league_name=league_name,
                    leagues_file=leagues_file,
                    season=season,
                    download_dir=season_dir,
                    force_refresh=refresh,
                    headless=headless,
                    username=username,
                    password=password,
                )
            except SystemExit:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Failed to retrieve schedule for league '%s' season %s: %s",
                    league_name,
                    season,
                    exc,
                    exc_info=True,
                )
                raise

            weekly, display_names = _build_team_week_table(resolved_html, end_week)
            for canonical, display in display_names.items():
                existing = latest_names.get(canonical)
                if existing is None or season >= existing[0]:
                    latest_names[canonical] = (season, display)

            if weekly.is_empty():
                logger.info(
                    "Season %s for league '%s' has no completed weeks; skipping.",
                    season,
                    league_name,
                )
                continue

            weekly = weekly.with_columns(
                League=pl.lit(league_name),
                Season=pl.lit(season),
            )
            ordered = _order_columns(weekly)
            frames.append(ordered)

    if not frames:
        cli_common.warn_and_exit("No completed team weeks were found for the requested filters.")

    combined = pl.concat(frames, how="diagonal")
    display_lookup = {team: display for team, (_, display) in latest_names.items()}
    combined = combined.with_columns(
        Team=pl.col("Team").map_elements(lambda name: display_lookup.get(name, name))
    )
    if sort_column not in combined.columns:
        cli_common.abort(
            f"sort_column '{sort_column}' must be one of: {', '.join(combined.columns)}",
            exit_code=2,
        )
    ascending = sort_dir == "asc"
    combined = combined.sort(sort_column, descending=not ascending)

    console = Console()
    table = Table(show_header=True, header_style="bold")
    for col in combined.columns:
        table.add_column(col)
    for row in combined.iter_rows(named=True):
        table.add_row(*[str(row[col]) for col in combined.columns])

    console.print()
    console.print(table)
    console.print()


def _normalize_sort_direction(direction: str) -> str:
    norm = (direction or "").strip().lower()
    if norm not in ("asc", "desc"):
        raise ValueError("sort-direction must be either 'asc' or 'desc'.")
    return norm


def _resolve_leagues(
    requested: Iterable[str] | None,
    mapping: dict[str, int],
) -> list[str]:
    if not mapping:
        raise ValueError(
            f"No leagues are configured. Create {PRIMARY_CONFIG_NAME} or pass --leagues-file."
        )

    if not requested:
        return sorted(mapping.keys())

    normalized_order = list(dict.fromkeys(requested))
    missing = [name for name in normalized_order if name not in mapping]
    if missing:
        raise ValueError(
            f"Unknown league(s): {', '.join(missing)}. Available: {', '.join(sorted(mapping))}"
        )
    return normalized_order


def _resolve_seasons(
    start: int | None,
    end: int | None,
    leagues: Iterable[str],
    download_root: Path | None,
) -> list[int]:
    if start is not None or end is not None:
        if start is None:
            start = end
        if end is None:
            end = start
        assert start is not None and end is not None
        if start > end:
            raise ValueError("--start-season cannot be greater than --end-season.")
        return list(range(start, end + 1))

    seasons: set[int] = set()
    for league in leagues:
        seasons.update(_discover_available_seasons(league, download_root))
    return sorted(seasons)


def _discover_available_seasons(league: str, download_root: Path | None) -> set[int]:
    base = _base_download_dir(download_root) / league
    if not base.exists():
        return set()
    seasons: set[int] = set()
    pattern = re.compile(r"(20\d{2})")
    for html_file in base.glob("*.html"):
        match = pattern.search(html_file.name)
        if match:
            seasons.add(int(match.group(1)))
    return seasons


def _build_team_week_table(
    html_path: Path, requested_end_week: int | None
) -> tuple[pl.DataFrame, dict[str, str]]:
    df = get_inputs(html_path)
    df, display_names = canonicalize_team_names(df)
    if df.is_empty():
        return pl.DataFrame(), {}

    season_year = int(df.get_column("season").unique().item())
    default_last_week = 14 if season_year > 2020 else 13
    most_recent = most_recent_week(df)
    cutoff = min(most_recent, default_last_week)
    if requested_end_week is not None:
        cutoff = min(cutoff, requested_end_week)
    if cutoff < 1:
        return pl.DataFrame(), {}

    missing_scores = df.filter(pl.col("score").is_null() | pl.col("opp_score").is_null())
    if not missing_scores.is_empty():
        logger.warning(
            "Dropping %s rows with missing scores from %s (season %s, weeks up to %s).",
            missing_scores.height,
            html_path.name,
            season_year,
            cutoff,
        )

    complete = df.filter(
        pl.col("week").is_between(1, cutoff, closed="both")
        & pl.col("score").is_not_null()
        & pl.col("opp_score").is_not_null()
    )
    if complete.is_empty():
        return pl.DataFrame(), display_names

    weekly = _compute_week_metrics(complete)
    return weekly, display_names


def _compute_week_metrics(df: pl.DataFrame) -> pl.DataFrame:
    ranked = df.with_columns(
        Result=pl.when(pl.col("score") > pl.col("opp_score"))
        .then(pl.lit("W"))
        .when(pl.col("score") == pl.col("opp_score"))
        .then(pl.lit("T"))
        .otherwise(pl.lit("L")),
        Margin=pl.col("score") - pl.col("opp_score"),
        Rank=pl.col("score").rank(method="min", descending=True).over("week").cast(pl.Int64),
        DenseRank=pl.col("score").rank(method="dense", descending=True).over("week").cast(pl.Int64),
        WeekSize=pl.len().over("week").cast(pl.Int64),
        WeekMax=pl.col("score").max().over("week"),
        WeekMin=pl.col("score").min().over("week"),
    )

    dense_scores = (
        ranked.group_by(["week", "DenseRank"])
        .agg(ScoreForDense=pl.col("score").max())
        .with_columns(
            DenseRank=pl.col("DenseRank").cast(pl.Int64),
        )
    )

    with_neighbors = (
        ranked.with_columns(
            LowerDense=pl.col("DenseRank") + 1,
            HigherDense=pl.col("DenseRank") - 1,
        )
        .join(
            dense_scores.rename({"DenseRank": "LowerDense", "ScoreForDense": "LowerScore"}),
            on=["week", "LowerDense"],
            how="left",
        )
        .join(
            dense_scores.rename({"DenseRank": "HigherDense", "ScoreForDense": "HigherScore"}),
            on=["week", "HigherDense"],
            how="left",
        )
    )

    rank_lookup = with_neighbors.select(["week", "team", "Rank"]).rename(
        {"team": "opponent", "Rank": "OppRank"}
    )

    enriched = (
        with_neighbors.join(rank_lookup, on=["week", "opponent"], how="left")
        .with_columns(
            PointsBackTop=pl.col("WeekMax") - pl.col("score"),
            PointsAheadBottom=pl.col("score") - pl.col("WeekMin"),
            GapToNextHigher=pl.when(pl.col("HigherScore").is_not_null())
            .then(pl.col("HigherScore") - pl.col("score"))
            .otherwise(None),
            GapToNextLower=pl.when(pl.col("LowerScore").is_not_null())
            .then(pl.col("score") - pl.col("LowerScore"))
            .otherwise(None),
        )
        .with_columns(
            pl.col("week").cast(pl.Int64).alias("Week"),
            pl.col("team").alias("Team"),
            pl.col("opponent").alias("Opponent"),
            pl.col("score").alias("Score"),
            pl.col("opp_score").alias("OppScore"),
        )
        .with_columns(
            pl.col(
                [
                    "Score",
                    "OppScore",
                    "Margin",
                    "PointsBackTop",
                    "PointsAheadBottom",
                    "GapToNextHigher",
                    "GapToNextLower",
                ]
            ).round(1)
        )
    )

    keep = [
        "Week",
        "Team",
        "Opponent",
        "Rank",
        "OppRank",
        "Result",
        "Score",
        "OppScore",
        "Margin",
        "PointsBackTop",
        "PointsAheadBottom",
        "GapToNextHigher",
        "GapToNextLower",
        "WeekSize",
    ]
    return enriched.select(keep)


def _order_columns(df: pl.DataFrame) -> pl.DataFrame:
    ordered = [col for col in ("League", "Season", "Week", "Team") if col in df.columns]
    ordered.extend([col for col in df.columns if col not in ordered])
    return df.select(ordered)


def _season_dir(league: str, download_root: Path | None) -> Path:
    base_dir = _base_download_dir(download_root) / league
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def _base_download_dir(download_root: Path | None) -> Path:
    if download_root is not None:
        return download_root
    return Path("html")


def cli() -> None:
    run(main)


if __name__ == "__main__":
    cli()
