from pathlib import Path

import polars as pl

from power_rankings.parse_utils import get_inputs, most_recent_week


def _write_sample_html(tmp_path: Path) -> Path:
    html = """
    <div class="matchup--table">
      <table class="Table">
        <tbody>
          <tr><td>1</td><td>Alpha</td><td>110</td><td>90</td><td>Beta</td></tr>
          <tr><td>1</td><td>Gamma</td><td>70</td><td>65</td><td>Delta</td></tr>
        </tbody>
      </table>
      <table class="Table">
        <tbody>
          <tr><td>2</td><td>Alpha</td><td>80</td><td>80</td><td>Gamma</td></tr>
        </tbody>
      </table>
      <table class="Table">
        <tbody>
          <tr><td>3</td><td>Beta</td><td></td><td></td><td>Delta</td></tr>
        </tbody>
      </table>
    </div>
    """
    path = tmp_path / "sample_2024.html"
    path.write_text(html)
    return path


def test_get_inputs_parses_scores_and_wins(tmp_path: Path):
    html_path = _write_sample_html(tmp_path)

    df = get_inputs(html_path)

    assert df.get_column("season").unique().item() == 2024
    assert df.get_column("week").to_list() == [1, 1, 1, 1, 2, 2, 3, 3]

    expected_wins = {
        (1, "Alpha"): 1.0,
        (1, "Beta"): 0.0,
        (1, "Gamma"): 1.0,
        (1, "Delta"): 0.0,
        (2, "Alpha"): 0.5,
        (2, "Gamma"): 0.5,
        (3, "Beta"): 0.0,
        (3, "Delta"): 0.0,
    }
    assert set(df.columns) >= {"team", "opponent", "score", "opp_score", "wins"}
    for row in df.to_dicts():
        assert expected_wins[(row["week"], row["team"])] == row["wins"]

    null_scores = df.filter(pl.col("week") == 3).get_column("score")
    assert null_scores.is_null().all()


def test_most_recent_week_skips_future_weeks(tmp_path: Path):
    html_path = _write_sample_html(tmp_path)
    df = get_inputs(html_path)

    # Week 3 has no scores; the most recent completed week is 2.
    assert most_recent_week(df) == 2
