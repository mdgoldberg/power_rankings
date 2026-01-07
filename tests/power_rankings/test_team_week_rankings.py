import logging
from pathlib import Path

import polars as pl

from power_rankings import team_week_rankings as twr


def _write_weekly_schedule(tmp_path: Path) -> Path:
    html = """
    <div class="matchup--table">
      <table class="Table">
        <tbody>
          <tr><td>1</td><td>Team A</td><td>110</td><td>90</td><td>Team B</td></tr>
          <tr><td>1</td><td>Team C</td><td>105</td><td>60</td><td>Team D</td></tr>
        </tbody>
      </table>
      <table class="Table">
        <tbody>
          <tr><td>2</td><td>Team A</td><td></td><td>80</td><td>Team C</td></tr>
        </tbody>
      </table>
    </div>
    """
    path = tmp_path / "league" / "2024.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html)
    return path


def test_build_team_week_table_computes_week_metrics(tmp_path: Path, caplog):
    html_path = _write_weekly_schedule(tmp_path)

    with caplog.at_level(logging.WARNING):
        weekly, display_names = twr._build_team_week_table(html_path, requested_end_week=None)

    assert "Dropping 2 rows with missing scores" in caplog.text
    assert display_names == {
        "Team A": "Team A",
        "Team B": "Team B",
        "Team C": "Team C",
        "Team D": "Team D",
    }

    assert weekly.shape == (4, 14)
    lookup = {(row["Week"], row["Team"]): row for row in weekly.to_dicts()}

    team_a = lookup[(1, "Team A")]
    assert team_a["Rank"] == 1
    assert team_a["OppRank"] == 3
    assert team_a["Margin"] == 20.0
    assert team_a["GapToNextLower"] == 5.0
    assert team_a["GapToNextHigher"] is None
    assert team_a["PointsBackTop"] == 0.0
    assert team_a["PointsAheadBottom"] == 50.0

    team_d = lookup[(1, "Team D")]
    assert team_d["Rank"] == 4
    assert team_d["OppRank"] == 2
    assert team_d["GapToNextHigher"] == 30.0
    assert team_d["GapToNextLower"] is None
    assert team_d["PointsAheadBottom"] == 0.0

    team_c = lookup[(1, "Team C")]
    assert team_c["GapToNextHigher"] == 5.0
    assert team_c["GapToNextLower"] == 15.0

    team_b = lookup[(1, "Team B")]
    assert team_b["GapToNextHigher"] == 15.0
    assert team_b["GapToNextLower"] == 30.0


def test_order_columns_places_context_leading():
    df = pl.DataFrame(
        {
            "Week": [1],
            "Team": ["Team A"],
            "Score": [100],
        }
    ).with_columns(League=pl.lit("demo"), Season=pl.lit(2024))

    ordered = twr._order_columns(df)

    assert ordered.columns[:4] == ["League", "Season", "Week", "Team"]
