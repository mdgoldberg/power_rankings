# Architecture Overview

This doc summarizes how the current CLI stack ingests ESPN fantasy schedules, transforms them into analytics tables, and exposes those results through Cyclopts entrypoints.

## High-Level Flow

- **Fetch or load HTML** – Every CLI funnels through `cli_common.ensure_schedule_or_exit`, which either validates a user-supplied HTML file or triggers Playwright-based scraping (`web_fetch.download_schedule_html`) using credentials and league metadata from `leagues.toml`.
- **Parse schedule tables** – `parse_utils.get_inputs` loads the stored HTML and uses PyQuery to walk the matchup tables. It emits a normalized pandas `DataFrame` with one row per team per week containing `team`, `opponent`, `score`, `opp_score`, derived `wins`, and the inferred `season`.
- **Aggregate season metrics** – `season_summary.get_summary_table` slices the dataframe to the requested weeks and computes aggregate statistics (wins/ties/losses, expected wins, luck, PF/PA, weekly top/bottom finishes, etc.). This is the shared core for `power-rankings`, `all-time`, and the plotting helpers.
- **Present via CLI** – Each entrypoint (`power_rankings.power_rankings`, `power_rankings.all_time`, `power_rankings.team_spotlight`) wires Cyclopts options to the shared helpers and prints/plots the resulting tables.

## CLI Entry Points

- `power-rankings` – Single-season standings table with optional plots. Handles fetching, week bounds, and printing the summary table.
- `all-time` – Iterates over a range of seasons, fetches each HTML schedule, aggregates per-manager statistics across seasons, then prints the combined table.
- `team-spotlight` – Focuses on one manager; shares the same HTML parsing but applies bespoke analysis/visualization (see `team_spotlight.py`).

All CLIs share logging, credential, league, and filesystem options defined in `cli_common.py`, keeping UX consistent.

## Data Model Details

- **Raw rows**: `week`, `team`, `opponent`, `score`, `opp_score`, `wins`, `season`.
- **Derived aggregates per team (columns from `get_summary_table`)**:
  - `W`, `T`, `L` – Head-to-head tallies computed against every opponent in the same week.
  - `Pct` – Expected win percentage (`(W + 0.5*T) / (W + T + L)`).
  - `Actual` – Real wins from actual match outcomes; treated as ints when there are no ties.
  - `Exp` – Expected wins over the games played (`Pct * games_played`).
  - `Luck` – `Actual - Exp`, highlighting over/under-performance.
  - `Proj` – Projection for the rest of the season based on remaining weeks (14 post-2020, otherwise 13).
  - `PF` / `PA` – Total points for/against.
  - `Max` / `Min` – Best and worst weekly scores logged by the team.
  - `Top1`, `Bot1`, `Top3`, `Bot3` – Frequency of finishing in the top/bottom 1 or 3 scores for a given week.
  - `Carpe` – Ratio of actual wins to the weekly-adjusted expected wins metric.

Downstream tables (CLI prints and optional plots) are sorted by `Pct` descending and rounded to three decimals before display.

## Future Storage Considerations

The current architecture is file-backed: HTML sits under `html/<league>/<season>.html`, derivatives live only in memory, and plots go wherever `--out-dir` points. Introducing a database layer will mainly affect the “Fetch or load HTML” step; all downstream code already consumes pandas dataframes, so a future ingestion pipeline can hydrate the same schema from persisted tables instead of direct HTML parsing.
