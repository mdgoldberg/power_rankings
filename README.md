# Power Rankings

![Python 3.12+](https://img.shields.io/badge/python-3.12+-3776AB?logo=python&logoColor=white)
![Project Version](https://img.shields.io/badge/version-0.1.0-informational)

## What the project does

Power Rankings is a CLI toolkit for analyzing ESPN fantasy football leagues. It parses league schedule pages, calculates weekly and season-long efficiency metrics, and can optionally automate data collection with Playwright. The toolset generates tabular summaries, visualizations, and spotlight reports for individual managers across one or many seasons.

## Why the project is useful

- Generates expected win percentages, luck scores, and detailed standings from raw ESPN matchup data.
- Automates HTML retrieval with credentialed Playwright sessions so you avoid manual downloads.
- Produces season-long trend charts (expected wins, points for, etc.) to visualize trajectory.
- Aggregates multiple years into “all-time” leaderboards and per-manager highlight reels.
- Wraps everything in Typer-powered CLIs with sensible defaults and helpful error messaging.

## Getting started

### Prerequisites

- Python 3.12+
- playwright-browsers (`playwright install chromium`) for automated scraping
- An ESPN account for auto-fetching schedules (default behavior)

### Installation

Using [uv](https://github.com/astral-sh/uv) (recommended):

```bash
uv sync
uv run playwright install chromium
```

Using plain `pip`:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
pip install -e .
playwright install chromium
```

### Credentials

Set your ESPN credentials as environment variables when auto-fetching (the default):

```bash
export ESPN_USERNAME="you@example.com"
export ESPN_PASSWORD="your-password"
```

You can also pass `--username` and `--password` flags directly to each command.

## Usage examples

All CLIs can be executed with `uv run <script>` (or `python -m power_rankings.<module>`).

### Generate current-season rankings

```bash
uv run power-rankings --league jlssffl --season 2024 --out-dir out/2024
```

This downloads the schedule into `html/jlssffl/2024.html`, prints the standings table, and saves plots under `out/2024/`. Add `--download-dir` if you want the HTML cached somewhere other than `html/<league>/`.

### Use a locally saved HTML schedule

```bash
uv run power-rankings html/jlssffl/2023.html --start-week 1 --end-week 8
```

Add `--offline` if you want to rely solely on local files.

### Spotlight an individual manager

```bash
uv run team-spotlight "Matt Goldberg" html/jlssffl/2024.html
```

Generates weekly results, streaks, and “lucky/unlucky” indicators for the named manager.

### Build an all-time leaderboard

```bash
uv run all-time html/jlssffl/ 2015 2024
```

Schedules auto-download by default. Pass `--offline` if you already have local HTML files and want to skip fetching. Use `--download-dir` if you want to override the HTML cache path (`html/<league>/`).

### Compare historical team seasons

```bash
uv run team-season-rankings --league jlssffl --league hsac --start-season 2018 --end-season 2024 --end-week 10
```

This aggregates every team-season for the provided leagues, adds a `Season` column to the familiar power-rankings table, and sorts (default `Pct`) so you can stack current performance against historical peaks. Use `--sort-column`, `--sort-direction`, and repeatable `--league` filters to drill into specific narratives; add `--refresh` to re-download the underlying schedules.

## Configuration

- `leagues.toml` maps friendly league aliases to ESPN league IDs. Populate it with your leagues (see the provided examples) so you can call `--league <name>` instead of remembering numeric IDs.
- Use `--download-dir` to override the default HTML cache location (`html/<league>/`).
- Graph outputs are written to the directory supplied via `--out-dir`. Existing PNG examples are in `out/`.
- Adjust CLI verbosity with `--log-level` (shared across commands). Options include `debug`, `info`, `warning`, `error`, and `critical`.

## Where to get help

- Run `uv run <command> --help` for full CLI options.
- File an issue or start a discussion in the repository if you encounter bugs or have feature requests.
- Open a PR draft for collaborative debugging or implementation questions.

## Who maintains and contributes

The project is maintained by Matthew Goldberg. Contributions are welcome—please open an issue to propose significant changes and follow the upcoming contributing guide (will live under `docs/CONTRIBUTING.md`) before submitting pull requests. Pre-commit hooks (`uv run pre-commit run --all-files`) and formatters (`uv run black .`, `uv run ruff check .`) keep the codebase consistent.
