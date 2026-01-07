from pathlib import Path

import pytest

from power_rankings import team_season_rankings as tsr


def _write_team_schedule(tmp_path: Path) -> Path:
    html = """
    <div class="matchup--table">
      <table class="Table">
        <tbody>
          <tr><td>1</td><td>MATTHEW GOLDBERG</td><td>100</td><td>90</td><td>Chris Ptak</td></tr>
        </tbody>
      </table>
      <table class="Table">
        <tbody>
          <tr><td>2</td><td>Joe Gowetski</td><td>70</td><td>75</td><td>Matt Goldberg</td></tr>
        </tbody>
      </table>
    </div>
    """
    path = tmp_path / "league" / "2024.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html)
    return path


def test_build_team_season_summary_returns_expected_table(tmp_path: Path):
    html_path = _write_team_schedule(tmp_path)

    summary, display_names = tsr._build_team_season_summary(html_path, requested_end_week=None)

    assert summary.columns[0] == "Team"
    lookup = {row["Team"]: row for row in summary.to_dicts()}
    assert lookup["Matt Goldberg"]["W"] == 2
    assert lookup["Matt Goldberg"]["Pct"] == 1
    assert lookup["Christopher Ptak"]["L"] == 1
    assert lookup["Joseph Gowetski"]["L"] == 1
    assert display_names == {
        "Matt Goldberg": "Matt Goldberg",
        "Christopher Ptak": "Chris Ptak",
        "Joseph Gowetski": "Joe Gowetski",
    }


def test_normalize_sort_direction_validates_input():
    assert tsr._normalize_sort_direction("ASC") == "asc"
    assert tsr._normalize_sort_direction("desc") == "desc"
    with pytest.raises(ValueError):
        tsr._normalize_sort_direction("sideways")


def test_resolve_seasons_discovers_html_files(tmp_path: Path):
    league_dir = tmp_path / "html" / "demo"
    league_dir.mkdir(parents=True, exist_ok=True)
    (league_dir / "2019.html").write_text("2019")
    (league_dir / "2021.html").write_text("2021")

    seasons = tsr._resolve_seasons(
        start=None,
        end=None,
        leagues=["demo"],
        download_root=tmp_path / "html",
    )

    assert seasons == [2019, 2021]
