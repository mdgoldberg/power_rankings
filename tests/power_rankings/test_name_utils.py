import polars as pl

from power_rankings.name_utils import canonicalize_team_names


def test_canonicalize_team_names_tracks_latest_display():
    df = pl.DataFrame(
        {
            "team": ["MATTHEW GOLDBERG", "Matt Goldberg", "Chris Ptak"],
            "opponent": ["Chris Ptak", "Joe Gowetski", "MATTHEW GOLDBERG"],
            "season": [2023, 2024, 2024],
            "week": [2, 1, 3],
        }
    )

    normalized, display_names = canonicalize_team_names(df)

    assert normalized["team"].to_list() == [
        "Matt Goldberg",
        "Matt Goldberg",
        "Christopher Ptak",
    ]
    assert normalized["opponent"].to_list() == [
        "Christopher Ptak",
        "Joseph Gowetski",
        "Matt Goldberg",
    ]
    assert display_names == {
        "Matt Goldberg": "Matt Goldberg",
        "Christopher Ptak": "Chris Ptak",
    }
