# Repository Guidelines

## Project Structure & Module Organization
CLI entry points and shared helpers live under `src/power_rankings/`: `power_rankings.py` and
`all_time.py` expose Typer commands, `team_spotlight.py` and `team_season_rankings.py` drive
story-driven outputs, `cli_common.py` coordinates ESPN scraping, while `season_summary.py` and
`parse_utils.py` handle analytics. Cached HTML is stored at `html/<league>/<season>.html`; derived
plots or tables go to `out/`. League metadata sits in `leagues.yaml`, and notebook experiments stay
in `model.ipynb`. Tests mirror the package layout inside `tests/`, with fixtures near the specs they
serve.

## Build, Test, and Development Commands
Install dependencies once with `uv sync`, then add browsers via
`uv run playwright install chromium`. Run the main season CLI through
`uv run power-rankings --league jlssffl --season 2024 --out-dir out/2024`. Aggregations or
narratives use `uv run all-time ...`, `uv run team-spotlight ...`, and
`uv run team-season-rankings ...`. Format the codebase with `uv run black src tests` and lint via
`uv run ruff check src tests`. Execute the suite using `uv run pytest` or target a module, e.g.
`uv run pytest tests/test_web_fetch.py` when iterating on scraping utilities.

## Coding Style & Naming Conventions
Target Python 3.12 and keep functions small, pure, and typed when feasible. Follow Black/ruff’s
100-character width, prefer f-strings, and keep imports grouped standard/library/local. Name Typer
commands with hyphenated CLI identifiers (e.g., `team-season-rankings`) and snake_case for modules.
Avoid committing notebooks or artifacts outside `model.ipynb` and `out/`.

## Testing Guidelines
Pytest powers all regression checks. Mirror the folder structure (`tests/power_rankings/…`) and name
new files `test_<feature>.py`. Mock Playwright I/O as shown in `tests/test_web_fetch.py` so suites
run offline. When adding analytics, seed pandas DataFrames with deterministic data and assert both
table shape and derived columns (Pct, Luck, PF/PA). Update fixtures whenever HTML contracts change
so CLI pipelines stay reproducible.

## Commit & Pull Request Guidelines
Commits follow conventional prefixes (`feat`, `docs`, `chore`) with optional scopes
(`feat(cli): ...`). Keep messages imperative and describe the observable behavior change. Each PR
should link issues when relevant, summarize CLI/UI impacts, note new league requirements, and attach
sample outputs from `out/` if visuals changed. Ensure `uv run pytest`, `uv run black`, and
`uv run ruff check` pass before requesting review.

## Security & Configuration Tips
Never commit secrets; load ESPN credentials via `ESPN_USERNAME`/`ESPN_PASSWORD` or CLI flags.
Regenerate Playwright storage with `uv run power-rankings --refresh` if sessions expire, and inspect
saved auth state via `python debug_storage_state.py`. Keep `leagues.toml` IDs accurate and scrub
personally identifiable information from committed HTML captures.
