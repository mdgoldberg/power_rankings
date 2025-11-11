# Power Rankings

This project collects fantasy football league data and produces power rankings based on historic
performance. The CLI can plot season summaries, evaluate all-time rankings, and now automates
schedule downloads from ESPN using Playwright.

## Requirements

- Python 3.12 (as declared in `pyproject.toml`)
- Optional: Playwright browsers installed via `playwright install` before running auto-fetch.

## Usage

- `power-rankings all-time` generates tables and graphs for a range of seasons; pass `--offline`
  with stored HTML files or omit it to auto-download schedules via ESPN login (see CLI help for
  credentials, league flags, and headless controls).
- `power-rankings team-spotlight` and other scripts remain available per `pyproject.toml`.

## Testing

Run the targeted test suite with:

```
uv run pytest tests/test_web_fetch.py
```

Adjust the command when adding future tests.
