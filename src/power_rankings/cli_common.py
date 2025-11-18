import logging
import sys
from datetime import date
from pathlib import Path
from typing import NoReturn, TextIO

from cyclopts import Parameter
from cyclopts.validators import Path as PathValidator

from power_rankings.league_config import LeagueConfigError, PRIMARY_CONFIG_NAME
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


def _exit_with(message: str, exit_code: int, *, stream: TextIO) -> NoReturn:
    print(message, file=stream)
    raise SystemExit(exit_code)


def abort(message: str, *, exit_code: int = 2) -> NoReturn:
    _exit_with(message, exit_code, stream=sys.stderr)


def warn_and_exit(message: str, *, exit_code: int = 0) -> NoReturn:
    _exit_with(message, exit_code, stream=sys.stdout)


def offline_option() -> Parameter:
    return Parameter(
        help="Skip downloading schedules; requires local HTML files.",
        show_default=True,
    )


def league_option() -> Parameter:
    return Parameter(
        help=f"League name (from {PRIMARY_CONFIG_NAME}) used when downloading schedules.",
    )


def league_id_option() -> Parameter:
    return Parameter(
        help="ESPN league identifier to fetch when auto-fetching.",
    )


def season_option() -> Parameter:
    return Parameter(
        help="Season (year) to fetch when auto-fetching. Defaults to current year.",
    )


def download_dir_option() -> Parameter:
    return Parameter(
        help="Directory to store downloaded HTML (defaults to html/<league>/).",
        validator=PathValidator(file_okay=False),
    )


def leagues_file_option() -> Parameter:
    return Parameter(
        help=f"Path to {PRIMARY_CONFIG_NAME} mapping league names to IDs.",
        validator=PathValidator(dir_okay=False),
    )


def refresh_option() -> Parameter:
    return Parameter(
        help="Force re-download even if a cached file exists.",
        show_default=True,
    )


def headless_option() -> Parameter:
    return Parameter(
        show_default=True,
        help="Run the browser in headless mode while auto-fetching.",
    )


def username_option() -> Parameter:
    return Parameter(
        help="ESPN username/email (overrides ESPN_USERNAME env var).",
    )


def password_option() -> Parameter:
    return Parameter(
        help="ESPN password (overrides ESPN_PASSWORD env var).",
    )


def log_level_option() -> Parameter:
    return Parameter(
        help="Logging verbosity (choose from: debug, info, warning, error, critical).",
        show_default=True,
    )


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


def normalize_log_level(level: str | None) -> str:
    if level is None:
        return "info"
    normalized = level.strip().lower()
    if normalized == "warn":
        normalized = "warning"
    if normalized not in _LOG_LEVELS:
        raise ValueError("Log level must be one of: debug, info, warning, error, critical.")
    return normalized


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
        abort(str(exc), exit_code=2)
    except LeagueConfigError as exc:
        abort(str(exc), exit_code=2)
    except LoginAutomationError as exc:
        abort(f"Automated login failed: {exc}", exit_code=3)
