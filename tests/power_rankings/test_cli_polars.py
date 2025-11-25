from pathlib import Path

import pytest

from power_rankings import cli_common, power_rankings, team_spotlight


def _write_sample_html(tmp_path: Path, filename: str = "sample_2024.html") -> Path:
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
    </div>
    """
    path = tmp_path / filename
    path.write_text(html)
    return path


def test_power_rankings_main_handles_polars(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    html_path = _write_sample_html(tmp_path, filename="league_2024.html")
    monkeypatch.setattr(cli_common, "ensure_schedule_or_exit", lambda *args, **kwargs: html_path)

    # Should not raise even though summary/printing flow uses Polars internally.
    power_rankings.main(html_filename=html_path, offline=True)


def test_team_spotlight_main_handles_polars(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    html_path = _write_sample_html(tmp_path, filename="league_2025.html")
    monkeypatch.setattr(cli_common, "ensure_schedule_or_exit", lambda *args, **kwargs: html_path)

    # Should not raise when filtering/weeks are processed with Polars before pandas.
    team_spotlight.main("Alpha", offline=True, league="demo", season=2025)
