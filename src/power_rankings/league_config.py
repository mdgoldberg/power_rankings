from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import tomllib


class LeagueConfigError(RuntimeError):
    """Base class for league configuration related problems."""


class LeagueNotFoundError(LeagueConfigError):
    """Raised when a requested league name is not found in the configuration file."""


class LeagueIdMismatchError(LeagueConfigError):
    """Raised when a provided league_id conflicts with the configured value."""


@lru_cache
def _load_from_path(path: Path) -> dict[str, int]:
    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    mapping: dict[str, int] = {}
    for key, value in raw.items():
        if isinstance(value, dict):
            if "league_id" not in value:
                raise LeagueConfigError(
                    f"League '{key}' is missing 'league_id' in configuration file {path}."
                )
            mapping[key] = int(value["league_id"])
        else:
            mapping[key] = int(value)
    return mapping


def load_league_mapping(leagues_file: Path | None = None) -> dict[str, int]:
    candidates = []
    if leagues_file is not None:
        specified = Path(leagues_file).expanduser()
        if not specified.exists():
            raise LeagueConfigError(f"Leagues configuration '{specified}' does not exist.")
        candidates.append(specified)
    else:
        cwd = Path.cwd().resolve()
        search_roots = (cwd,) + tuple(cwd.parents)
        for root in search_roots:
            candidates.append(root / "leagues.toml")
        package_default = Path(__file__).resolve().parent / "leagues.toml"
        project_default = Path(__file__).resolve().parents[2] / "leagues.toml"
        candidates.extend([package_default, project_default])

    for candidate in candidates:
        if candidate.exists():
            return _load_from_path(candidate.resolve())

    return {}


def resolve_league_id(
    league_id: int | None,
    league_name: str | None,
    leagues_file: Path | None = None,
) -> int | None:
    """
    Resolve a league identifier from either a direct ID or a configured league name.

    Returns the provided league_id if given, otherwise looks up the name in the config.
    """
    if league_id is not None and league_name is not None:
        mapping = load_league_mapping(leagues_file)
        config_id = mapping.get(league_name)
        if config_id is None:
            raise LeagueNotFoundError(
                f"League '{league_name}' was not found in the leagues configuration."
            )
        if config_id != league_id:
            raise LeagueIdMismatchError(
                f"Provided league ID {league_id} conflicts with configured ID {config_id} for '{league_name}'."
            )
        return league_id

    if league_id is not None:
        return league_id

    if league_name is None:
        return None

    mapping = load_league_mapping(leagues_file)
    if not mapping:
        raise LeagueConfigError(
            "No leagues configuration found. Provide --league-id or create leagues.toml."
        )

    resolved = mapping.get(league_name)
    if resolved is None:
        available = ", ".join(sorted(mapping))
        raise LeagueNotFoundError(
            f"League '{league_name}' not found. Available leagues: {available}."
        )

    return resolved
