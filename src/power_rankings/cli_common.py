from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import typer

from power_rankings.league_config import LeagueConfigError
from power_rankings.web_fetch import (
    LoginAutomationError,
    MissingCredentialsError,
    ensure_schedule_file,
)

_LOG_LEVELS = {
    "critical": logging.CRITICAL,
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
}


def offline_option() -> bool:
    return typer.Option(
        False,
        "--offline",
        help="Skip downloading schedules; requires local HTML files.",
    )


def league_option() -> str | None:
    return typer.Option(
        None,
        "--league",
        help="League name (from leagues.toml) used when downloading schedules.",
    )


def league_id_option() -> int | None:
    return typer.Option(
        None,
        help="ESPN league identifier to fetch when auto-fetching.",
    )


def season_option() -> int | None:
    return typer.Option(
        None,
        help="Season (year) to fetch when auto-fetching. Defaults to current year.",
    )


def download_dir_option() -> Path | None:
    return typer.Option(
        None,
        file_okay=False,
        help="Directory to store downloaded HTML (defaults to html/<league>/).",
    )


def leagues_file_option() -> Path | None:
    return typer.Option(
        None,
        dir_okay=False,
        help="Path to leagues.toml mapping league names to IDs.",
    )


def refresh_option() -> bool:
    return typer.Option(
        False,
        "--refresh",
        help="Force re-download even if a cached file exists.",
    )


def headless_option(default: bool) -> bool:
    return typer.Option(
        default,
        "--headless/--no-headless",
        help="Run the browser in headless mode while auto-fetching.",
    )


def username_option() -> str | None:
    return typer.Option(
        None,
        help="ESPN username/email (overrides ESPN_USERNAME env var).",
    )


def password_option() -> str | None:
    return typer.Option(
        None,
        help="ESPN password (overrides ESPN_PASSWORD env var).",
    )


def log_level_option() -> str:
    return typer.Option(
        "info",
        "--log-level",
        show_default=True,
        help="Logging verbosity (choose from: debug, info, warning, error, critical).",
        callback=_normalize_log_level,
    )


def _normalize_log_level(level: str | None) -> str:
    if level is None:
        return "info"
    normalized = level.strip().lower()
    if normalized == "warn":
        normalized = "warning"
    if normalized not in _LOG_LEVELS:
        raise typer.BadParameter("Log level must be one of: debug, info, warning, error, critical.")
    return normalized


def configure_logging(level: str) -> None:
    numeric_level = _LOG_LEVELS[level]
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(numeric_level)
    else:
        logging.basicConfig(
            level=numeric_level,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )


def resolve_auto_fetch(offline: bool) -> bool:
    return not offline


def resolve_season(auto_fetch: bool, season: int | None) -> int | None:
    if auto_fetch and season is None:
        return date.today().year
    return season


def ensure_schedule_or_exit(
    html_filename: Path | None,
    *,
    auto_fetch: bool,
    league_id: int | None,
    league_name: str | None,
    leagues_file: Path | None,
    season: int | None,
    download_dir: Path | None,
    force_refresh: bool,
    headless: bool,
    username: str | None,
    password: str | None,
) -> Path:
    try:
        return ensure_schedule_file(
            html_filename,
            auto_fetch=auto_fetch,
            league_id=league_id,
            league_name=league_name,
            leagues_file=leagues_file,
            season=season,
            download_dir=download_dir,
            force_refresh=force_refresh,
            headless=headless,
            username=username,
            password=password,
        )
    except MissingCredentialsError as exc:
        typer.secho(str(exc), fg="red", err=True)
        raise typer.Exit(code=2) from exc
    except LeagueConfigError as exc:
        typer.secho(str(exc), fg="red", err=True)
        raise typer.Exit(code=2) from exc
    except LoginAutomationError as exc:
        typer.secho(f"Automated login failed: {exc}", fg="red", err=True)
        raise typer.Exit(code=3) from exc
