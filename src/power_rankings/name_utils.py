from typing import Any

import pandas as pd

DUPES: dict[str, str] = {
    "MATTHEW GOLDBERG": "Matt Goldberg",
    "mitch hildreth, I. Reese": "mitch hildreth",
    "Joe Gowetski": "Joseph Gowetski",
    "Chris Ptak": "Christopher Ptak",
}


def canonical_team_label(name: Any) -> Any:
    """
    Map a raw team name to its canonical identifier.

    Non-string values (e.g., NaN) are returned unchanged.
    """
    if not isinstance(name, str):
        return name
    return DUPES.get(name, name)


def canonicalize_team_names(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    """
    Replace duplicate/legacy team labels with canonical identifiers while tracking
    the most recently observed display name for each team.

    Returns a tuple of (normalized dataframe, display name map).
    """
    if df.empty:
        return df.copy(), {}

    normalized = df.copy()
    order_cols = [col for col in ("season", "week") if col in normalized.columns]
    sorted_df = normalized.sort_values(order_cols) if order_cols else normalized

    latest_display: dict[str, str] = {}
    for _, row in sorted_df.iterrows():
        team_name = row["team"]
        canonical = canonical_team_label(team_name)
        if isinstance(canonical, str) and isinstance(team_name, str):
            latest_display[canonical] = team_name

    normalized["team"] = normalized["team"].map(canonical_team_label)
    normalized["opponent"] = normalized["opponent"].map(canonical_team_label)
    return normalized, latest_display
