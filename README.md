# Power Rankings

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](pyproject.toml)
[![Tests](https://img.shields.io/badge/tests-pytest-green.svg)](tests/test_web_fetch.py)
[![Playwright](https://img.shields.io/badge/ui%20automation-Playwright-purple.svg)](src/power_rankings/web_fetch.py)

## What the project does

Power Rankings is a Typer-based CLI toolkit for ingesting ESPN fantasy football schedules, computing
season and multi-season analytics, and exporting summary plots. The core commands live under
`src/power_rankings/` and share a pipeline that downloads (or reuses cached) ESPN HTML schedules,
parses weekly matchups into pandas dataframes, and prints tables or plots that highlight actual vs.
expected wins, luck, points for/against, and team-specific storylines.

## Why the project is useful

- **Automated data collection** – Uses Playwright to log in to ESPN with stored credentials and save
  each season’s schedule HTML under `html/<league>/<season>.html`, so you always analyze fresh data.
- **Consistent metrics** – `season_summary.get_summary_table` powers all CLIs, ensuring “Actual” vs.
  “Expected” wins, “Luck,” `PF/PA`, and top/bottom weekly finishes are comparable across seasons.
- **Multiple entry points** – Run `power-rankings` for one season, `all-time` for historical rollups,
  `team-spotlight` for emoji-enhanced narratives, or `team-season-rankings` to compare teams across
  leagues.
- **Shareable outputs** – Save plots to `out/` for dashboards or export CSV-like tables directly from
  the CLI for downstream processing.

## Architecture overview

Power Rankings uses a shared pipeline to ingest ESPN fantasy schedules, transform them into analytics
tables, and expose those results through Typer entrypoints.

### High-level flow

- **Fetch or load HTML** – Every CLI funnels through `cli_common.ensure_schedule_or_exit`, which
  either validates a user-supplied HTML file or triggers Playwright-based scraping
  (`web_fetch.download_schedule_html`) using credentials and league metadata from `leagues.toml`.
- **Parse schedule tables** – `parse_utils.get_inputs` loads the stored HTML and uses PyQuery to walk
  the matchup tables. It emits a normalized pandas `DataFrame` with one row per team per week
  containing `team`, `opponent`, `score`, `opp_score`, derived `wins`, and the inferred `season`.
- **Aggregate season metrics** – `season_summary.get_summary_table` slices the dataframe to the
  requested weeks and computes aggregate statistics (wins/ties/losses, expected wins, luck, PF/PA,
  weekly top/bottom finishes, etc.). This is the shared core for `power-rankings`, `all-time`, and
  the plotting helpers.
- **Present via CLI** – Each entrypoint (`power_rankings.power_rankings`, `power_rankings.all_time`,
  `power_rankings.team_spotlight`) wires Typer options to the shared helpers and prints/plots the
  resulting tables.

### CLI entry points

- `power-rankings` – Single-season standings table with optional plots. Handles fetching, week
  bounds, and printing the summary table.
- `all-time` – Iterates over a range of seasons, fetches each HTML schedule, aggregates per-manager
  statistics across seasons, then prints the combined table.
- `team-spotlight` – Focuses on one manager; shares the same HTML parsing but applies bespoke
  analysis/visualization (see `team_spotlight.py`).
- `team-season-rankings` – Compares individual team seasons across leagues and seasons by reusing
  the shared summary tables.

All CLIs share logging, credential, league, and filesystem options defined in `cli_common.py`,
keeping UX consistent.

### Data model details

- **Raw rows**: `week`, `team`, `opponent`, `score`, `opp_score`, `wins`, `season`.
- **Derived aggregates per team (columns from `get_summary_table`)**:
  - `W`, `T`, `L` – Head-to-head tallies computed against every opponent in the same week.
  - `Pct` – Expected win percentage (`(W + 0.5*T) / (W + T + L)`).
  - `Actual` – Real wins from actual match outcomes; treated as ints when there are no ties.
  - `Exp` – Expected wins over the games played (`Pct * games_played`).
  - `Luck` – `Actual - Exp`, highlighting over/under-performance.
  - `Proj` – Projection for the rest of the season based on remaining weeks (14 post-2020, otherwise
    13).
  - `PF` / `PA` – Total points for/against.
  - `Max` / `Min` – Best and worst weekly scores logged by the team.
  - `Top1`, `Bot1`, `Top3`, `Bot3` – Frequency of finishing in the top/bottom 1 or 3 scores for a
    given week.
  - `Carpe` – Ratio of actual wins to the weekly-adjusted expected wins metric.

Downstream tables (CLI prints and optional plots) are sorted by `Pct` descending and rounded to
three decimals before display.

### Future storage considerations

The current architecture is file-backed: HTML sits under `html/<league>/<season>.html`, derivatives
live only in memory, and plots go wherever `--out-dir` points. Introducing a database layer will
mainly affect the “Fetch or load HTML” step; all downstream code already consumes pandas dataframes,
so a future ingestion pipeline can hydrate the same schema from persisted tables instead of direct
HTML parsing.

## Getting started

### Prerequisites

- Python 3.12 (enforced by `pyproject.toml`)
- [uv](https://github.com/astral-sh/uv) for dependency management
- Chromium browsers installed for Playwright scraping
- ESPN login with access to the target leagues

### Install dependencies

```bash
uv sync
uv run playwright install chromium
```

`uv sync` installs both runtime and `[dev]` dependencies, so `uv run …` uses the project’s lockfile.

### Configure leagues and credentials

Map friendly league names to ESPN IDs in [`leagues.toml`](leagues.toml):

```toml
[jlssffl]
league_id = 329301
```

Store ESPN credentials via environment variables or CLI flags:

```bash
export ESPN_USERNAME="name@example.com"
export ESPN_PASSWORD="app-specific-password"
```

Playwright caches login state in `~/.cache/power_rankings/espn_state.json`. If a stored session
expires, re-run a command with `--headless/--no-headless` as needed or use
[`debug_storage_state.py`](debug_storage_state.py) to inspect the saved state.

### CLI quick reference

| Command | Purpose | Example |
| --- | --- | --- |
| `power-rankings` | Single-season summary with optional plots | `uv run power-rankings --league jlssffl --season 2024 --out-dir out/2024` |
| `all-time` | Aggregate multiple seasons | `uv run all-time 2019 2024 --league jlssffl --out-dir out/all-time` |
| `team-spotlight` | Narrative of one owner’s season | `uv run team-spotlight "Matt Goldberg" --league jlssffl --season 2024 --out-dir out/spotlight` |
| `team-season-rankings` | Cross-league, cross-season comparisons | `uv run team-season-rankings --league jlssffl --league hoedown --start-season 2018 --end-season 2024` |

All commands accept shared options from `cli_common.py`:

- `--offline` – Skip auto-fetching and read a saved HTML file (pass the file path as the positional
  argument). Cached files live under `html/<league>/`.
- `--download-dir` – Override where HTML is stored.
- `--refresh` – Force re-download even when a cached file exists.
- `--headless/--no-headless` – Control Chromium visibility if manual MFA prompts are expected.

#### Examples

- Use local HTML and create charts:

  ```bash
  uv run power-rankings html/jlssffl/2023.html --offline --out-dir out/2023
  ```

- Auto-fetch five years of data and print cumulative standings:

  ```bash
  uv run all-time 2020 2024 --league jlssffl --download-dir html/jlssffl
  ```

- Compare every stored team season, sorted by `Proj` and limited to games through Week 10:

  ```bash
  uv run team-season-rankings --league jlssffl --end-week 10 --sort-column Proj --sort-direction desc
  ```

### Testing and quality checks

```bash
uv run pytest          # entire suite
uv run pytest tests/test_web_fetch.py  # focused Playwright mocks
uv run black src tests
uv run ruff check src tests
```

`tests/test_web_fetch.py` demonstrates how network calls are mocked; follow that pattern for any new
automation logic. Save generated plots to `out/` and keep deterministic fixtures (if needed) under
`tests/fixtures/`.

## Where to get help

- [Architecture overview](#architecture-overview) – Data flow, CLI interactions, and data model.
- [AGENTS.md](AGENTS.md) – Repository conventions, testing requirements, and release expectations.
- [`debug_storage_state.py`](debug_storage_state.py) – Diagnose Playwright login sessions.
- [`tests/test_web_fetch.py`](tests/test_web_fetch.py) – Reference for stubbing ESPN scraping.
- File an issue or start a discussion in the repository when you need new league metadata, CLI
  flags, or help debugging Playwright.

## Who maintains and contributes

The project is maintained by Matthew Goldberg and an open-source contributor group focused on
fantasy analytics tooling. Contributions are welcome:

1. Review the guidelines in [AGENTS.md](AGENTS.md) (structure, style, testing, conventional commits).
2. Create a feature branch, make focused changes, and update relevant docs (README, ARCHITECTURE,
   etc.).
3. Run `uv run pytest -k <target> --maxfail=1`, plus `uv run black` and `uv run ruff`, before
   opening a pull request.
4. Use descriptive commit messages (`feat(all-time): add SOS projection`) and document any data
   prerequisites (league IDs, HTML fixtures, screenshots from `out/`).

For questions about roadmap or release cadence, open a GitHub issue and tag @matthew-goldberg (or
the current maintainer) to start the conversation.
