from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any, TypeAlias, TypedDict

import yaml


PRIMARY_CONFIG_NAME = "leagues.yaml"


LeagueName: TypeAlias = str
LeagueIdentifier: TypeAlias = int
LeagueConfig = dict[LeagueName, LeagueIdentifier]


class LeagueRecord(TypedDict, total=False):
    league_id: LeagueIdentifier


LeagueValue = LeagueIdentifier | str | LeagueRecord | None
RawLeagueConfig: TypeAlias = dict[LeagueName, LeagueValue]


class LeagueConfigError(RuntimeError):
    """Base class for league configuration related problems."""


class LeagueNotFoundError(LeagueConfigError):
    """Raised when a requested league name is not found in the configuration file."""


class LeagueIdMismatchError(LeagueConfigError):
    """Raised when a provided league_id conflicts with the configured value."""


@lru_cache
def _load_from_path(path: Path) -> LeagueConfig:
    with path.open("r", encoding="utf-8") as handle:
        raw_data: Any = yaml.safe_load(handle) or {}

    if not isinstance(raw_data, Mapping):
        raise LeagueConfigError(
            f"Expected a mapping of league names in configuration file {path}, "
            f"but found {type(raw_data).__name__}."
        )

    raw_config: RawLeagueConfig = dict(raw_data)

    mapping: LeagueConfig = {}
    for key, value in raw_config.items():
        mapping[key] = _extract_league_id(key, value, path)
    return mapping


def _extract_league_id(league_name: str, value: LeagueValue, path: Path) -> int:
    record_value: Any
    if isinstance(value, Mapping):
        if "league_id" not in value:
            raise LeagueConfigError(
                f"League '{league_name}' is missing 'league_id' in configuration file {path}."
            )
        record_value = value["league_id"]
    else:
        record_value = value

    try:
        return int(record_value)
    except (TypeError, ValueError) as exc:
        raise LeagueConfigError(
            f"League '{league_name}' has an invalid league_id value {record_value!r} in {path}."
        ) from exc


def load_league_mapping(leagues_file: Path | None = None) -> LeagueConfig:
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
            candidates.append(root / PRIMARY_CONFIG_NAME)
        module_root = Path(__file__).resolve().parent
        project_root = Path(__file__).resolve().parents[2]
        candidates.append(module_root / PRIMARY_CONFIG_NAME)
        candidates.append(project_root / PRIMARY_CONFIG_NAME)

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
            f"No leagues configuration found. Provide --league-id or create {PRIMARY_CONFIG_NAME}."
        )

    resolved = mapping.get(league_name)
    if resolved is None:
        available = ", ".join(sorted(mapping))
        raise LeagueNotFoundError(
            f"League '{league_name}' not found. Available leagues: {available}."
        )

    return resolved
