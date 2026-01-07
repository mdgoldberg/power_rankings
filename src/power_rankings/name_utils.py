from typing import Any
import polars as pl

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


def canonicalize_team_names(df: pl.DataFrame) -> tuple[pl.DataFrame, dict[str, str]]:
    """
    Replace duplicate/legacy team labels with canonical identifiers while tracking
    the most recently observed display name for each team.

    Returns a tuple of (normalized dataframe, display name map).
    """
    if df.is_empty():
        return df.clone(), {}

    order_cols = [col for col in ("season", "week") if col in df.columns]
    sorted_df = df.sort(order_cols) if order_cols else df

    latest_display: dict[str, str] = {}
    for row in sorted_df.select("team").to_series():
        canonical = canonical_team_label(row)
        if isinstance(canonical, str) and isinstance(row, str):
            latest_display[canonical] = row

    normalized = df.with_columns(
        team=pl.col("team").map_elements(canonical_team_label),
        opponent=pl.col("opponent").map_elements(canonical_team_label),
    )
    return normalized, latest_display
