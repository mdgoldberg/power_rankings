from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Iterable

import pandas as pd
import typer

from power_rankings import cli_common
from power_rankings.league_config import load_league_mapping
from power_rankings.name_utils import canonicalize_team_names
from power_rankings.parse_utils import get_inputs, most_recent_week
from power_rankings.season_summary import get_summary_table

logger = logging.getLogger(__name__)


def main(
    start_season: int | None = typer.Option(
        None,
        "--start-season",
        help="Earliest season (year) to include.",
    ),
    end_season: int | None = typer.Option(
        None,
        "--end-season",
        help="Latest season (year) to include.",
    ),
    leagues: list[str] | None = typer.Option(
        None,
        "--league",
        "-l",
        help="League name from leagues.toml. Repeat the option to include multiple leagues.",
        show_default=False,
        rich_help_panel="Filters",
    ),
    end_week: int | None = typer.Option(
        None,
        "--end-week",
        min=1,
        max=18,
        help="Cutoff week (inclusive) when computing each season summary.",
    ),
    sort_column: str = typer.Option(
        "Pct",
        "--sort-column",
        help="Output column to sort by. Must match one of the table headers.",
    ),
    sort_direction: str = typer.Option(
        "desc",
        "--sort-direction",
        help="Sorting direction for the selected column (asc or desc).",
    ),
    offline: bool = cli_common.offline_option(),
    download_dir: Path | None = cli_common.download_dir_option(),
    leagues_file: Path | None = cli_common.leagues_file_option(),
    refresh: bool = cli_common.refresh_option(),
    headless: bool = cli_common.headless_option(default=True),
    username: str | None = cli_common.username_option(),
    password: str | None = cli_common.password_option(),
    log_level: str = cli_common.log_level_option(),
):
    """Compare team seasons across one or more leagues."""
    cli_common.configure_logging(log_level)
    auto_fetch = cli_common.resolve_auto_fetch(offline)
    sort_dir = _normalize_sort_direction(sort_direction)

    league_mapping = load_league_mapping(leagues_file)
    selected_leagues = _resolve_leagues(leagues, league_mapping)

    seasons = _resolve_seasons(start_season, end_season, selected_leagues, download_dir)
    if not seasons:
        typer.secho("No seasons to process; provide --start-season/--end-season or download HTML first.", fg="red", err=True)
        raise typer.Exit(code=2)

    frames: list[pd.DataFrame] = []
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
            except typer.Exit:
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

            season_summary, season_display = _build_team_season_summary(resolved_html, end_week)
            for canonical, display in season_display.items():
                existing = latest_names.get(canonical)
                if existing is None or season >= existing[0]:
                    latest_names[canonical] = (season, display)

            if season_summary.empty:
                logger.info(
                    "Season %s for league '%s' has no completed weeks; skipping.",
                    season,
                    league_name,
                )
                continue
            season_summary.insert(0, "Season", season)
            season_summary.insert(1, "Team", season_summary.pop("Team"))
            frames.append(season_summary)

    if not frames:
        typer.secho("No completed team seasons were found for the requested filters.", fg="yellow")
        raise typer.Exit(code=0)

    combined = pd.concat(frames, ignore_index=True)
    display_lookup = {team: display for team, (_, display) in latest_names.items()}
    combined["Team"] = combined["Team"].map(lambda name: display_lookup.get(name, name))
    if sort_column not in combined.columns:
        raise ValueError(
            f"sort_column '{sort_column}' must be one of: {', '.join(combined.columns)}"
        )
    ascending = sort_dir == "asc"
    combined = combined.sort_values(sort_column, ascending=ascending).reset_index(drop=True)

    pd.set_option("display.max_rows", 200)
    print()
    print(combined)
    print()


def _normalize_sort_direction(direction: str) -> str:
    norm = (direction or "").strip().lower()
    if norm not in ("asc", "desc"):
        raise typer.BadParameter("sort-direction must be either 'asc' or 'desc'.")
    return norm


def _resolve_leagues(
    requested: Iterable[str] | None,
    mapping: dict[str, int],
) -> list[str]:
    if not mapping:
        raise typer.BadParameter(
            "No leagues are configured. Create leagues.toml or pass --leagues-file."
        )

    if not requested:
        return sorted(mapping.keys())

    normalized_order = list(dict.fromkeys(requested))
    missing = [name for name in normalized_order if name not in mapping]
    if missing:
        raise typer.BadParameter(
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
            raise typer.BadParameter("--start-season cannot be greater than --end-season.")
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


def _build_team_season_summary(
    html_path: Path, requested_end_week: int | None
) -> tuple[pd.DataFrame, dict[str, str]]:
    df = get_inputs(html_path)
    df, display_names = canonicalize_team_names(df)
    if df.empty:
        return pd.DataFrame(), {}

    season_year = int(df["season"].unique().item())
    default_last_week = 14 if season_year > 2020 else 13
    most_recent = most_recent_week(df)
    cutoff = min(most_recent, default_last_week)
    if requested_end_week is not None:
        cutoff = min(cutoff, requested_end_week)
    if cutoff < 1:
        return pd.DataFrame(), {}

    summary = get_summary_table(df, 1, cutoff)
    summary = summary.reset_index().rename(columns={"index": "Team"})
    ordered_cols = ["Team"] + [col for col in summary.columns if col != "Team"]
    return summary.loc[:, ordered_cols], display_names


def _season_dir(league: str, download_root: Path | None) -> Path:
    base_dir = _base_download_dir(download_root) / league
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def _base_download_dir(download_root: Path | None) -> Path:
    if download_root is not None:
        return download_root
    return Path("html")


def cli():
    typer.run(main)


if __name__ == "__main__":
    cli()
