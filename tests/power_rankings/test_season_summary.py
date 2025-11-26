from pathlib import Path

import polars as pl

from power_rankings.season_summary import get_summary_table, plot_season_graphs


def _sample_results() -> pl.DataFrame:
    return pl.DataFrame(
        [
            {
                "team": "A",
                "opponent": "B",
                "score": 100,
                "opp_score": 90,
                "week": 1,
                "season": 2024,
            },
            {
                "team": "B",
                "opponent": "A",
                "score": 90,
                "opp_score": 100,
                "week": 1,
                "season": 2024,
            },
            {"team": "A", "opponent": "B", "score": 80, "opp_score": 80, "week": 2, "season": 2024},
            {"team": "B", "opponent": "A", "score": 80, "opp_score": 80, "week": 2, "season": 2024},
        ]
    )


def test_get_summary_table_computes_expected_metrics():
    df = _sample_results()

    summary = get_summary_table(df, start_week=1, end_week=2)
    summary_lookup = {row["team"]: row for row in summary.to_dicts()}

    assert "Actual" not in summary.columns
    assert "Exp_numeric" not in summary.columns
    assert "Proj_numeric" not in summary.columns
    assert summary_lookup["A"]["W"] == 1
    assert summary_lookup["A"]["T"] == 1
    assert summary_lookup["A"]["L"] == 0
    assert summary_lookup["A"]["Pct"] == 0.75
    assert summary_lookup["A"]["Record"] == "1-0-1"
    assert summary_lookup["A"]["Exp"] == "1.5-0.5"
    assert summary_lookup["A"]["Luck"] == 0
    assert summary_lookup["A"]["Proj"] == "10.5-2.5"
    assert summary_lookup["A"]["PF"] == 180
    assert summary_lookup["A"]["PA"] == 170
    assert summary_lookup["A"]["Top1"] == 2
    assert summary_lookup["A"]["Bot1"] == 1
    assert summary_lookup["A"]["Faced-Bot1"] == 2
    assert summary_lookup["A"]["Top3"] == 0
    assert summary_lookup["A"]["Bot3"] == 0

    assert summary_lookup["B"]["W"] == 0
    assert summary_lookup["B"]["T"] == 1
    assert summary_lookup["B"]["L"] == 1
    assert summary_lookup["B"]["Pct"] == 0.25
    assert summary_lookup["B"]["Record"] == "0-1-1"
    assert summary_lookup["B"]["Exp"] == "0.5-1.5"
    assert summary_lookup["B"]["Luck"] == 0
    assert summary_lookup["B"]["Proj"] == "3.5-9.5"
    assert summary_lookup["B"]["Faced-Bot1"] == 1


def test_plot_season_graphs_writes_output(tmp_path: Path):
    df = _sample_results()

    plot_season_graphs(df, start_week=1, end_week=2, out_dir=tmp_path)

    expected_files = [
        "plot_Expected Wins.png",
        "plot_Wins.png",
        "plot_Expected Win%.png",
        "plot_Points Per Game.png",
        "plot_PF.png",
    ]
    for filename in expected_files:
        assert (tmp_path / filename).exists()
