from pathlib import Path
from typing import Annotated

from cyclopts import Parameter, run
from cyclopts.validators import Path as PathValidator

from power_rankings import cli_common
from power_rankings.name_utils import canonical_team_label, canonicalize_team_names
from power_rankings.parse_utils import get_inputs, most_recent_week


def main(
    owner_name: str,
    html_filename: Annotated[
        Path | None,
        Parameter(
            help="Path to a saved schedule HTML file; auto-downloads if omitted.",
            validator=PathValidator(dir_okay=False),
        ),
    ] = None,
    out_dir: Annotated[
        Path | None,
        Parameter(
            help="Directory to store generated plots (optional).",
            validator=PathValidator(file_okay=False),
        ),
    ] = None,
    start_week: Annotated[int | None, Parameter(help="First week (inclusive).")] = None,
    end_week: Annotated[int | None, Parameter(help="Last week (inclusive).")] = None,
    offline: Annotated[bool, cli_common.offline_option()] = False,
    league: Annotated[str | None, cli_common.league_option()] = None,
    league_id: Annotated[int | None, cli_common.league_id_option()] = None,
    season: Annotated[int | None, cli_common.season_option()] = None,
    download_dir: Annotated[Path | None, cli_common.download_dir_option()] = None,
    leagues_file: Annotated[Path | None, cli_common.leagues_file_option()] = None,
    refresh: Annotated[bool, cli_common.refresh_option()] = False,
    headless: Annotated[bool, cli_common.headless_option()] = True,
    username: Annotated[str | None, cli_common.username_option()] = None,
    password: Annotated[str | None, cli_common.password_option()] = None,
    log_level: Annotated[str, cli_common.log_level_option()] = "info",
) -> None:
    """Generates rankings for a given season, given the HTML of the schedule and results."""
    log_level = cli_common.normalize_log_level(log_level)
    cli_common.configure_logging(log_level)

    auto_fetch = cli_common.resolve_auto_fetch(offline)
    resolved_season = cli_common.resolve_season(auto_fetch, season)

    html_path = cli_common.ensure_schedule_or_exit(
        html_filename,
        auto_fetch=auto_fetch,
        league_id=league_id,
        league_name=league,
        leagues_file=leagues_file,
        season=resolved_season,
        download_dir=download_dir,
        force_refresh=refresh,
        headless=headless,
        username=username,
        password=password,
    )

    df = get_inputs(html_path)
    df, display_names = canonicalize_team_names(df)

    if start_week is None:
        start_week = 1

    most_recent = most_recent_week(df)
    if end_week is None:
        end_week = most_recent
    else:
        end_week = min(end_week, most_recent)

    df = df.loc[(start_week <= df.week) & (df.week <= end_week)]

    df["week_rank"] = df.groupby("week").score.rank(ascending=False)
    df["week_opp_rank"] = df.groupby("week").opp_score.rank(ascending=False)
    owner_query = owner_name.lower()
    canonical_query = canonical_team_label(owner_name).lower()
    matches = df.team.str.lower().str.contains(owner_query)
    if canonical_query != owner_query:
        matches |= df.team.str.lower().str.contains(canonical_query)
    owner_df = df.loc[matches].copy()
    owner_df["result"] = owner_df.wins.map(lambda w: "W" if w == 1.0 else "T" if w == 0.5 else "L")
    owner_df["totWins"] = (owner_df.result == "W").cumsum()
    owner_df["totLosses"] = (owner_df.result == "L").cumsum()
    owner_df = owner_df[
        [
            "week",
            "totWins",
            "totLosses",
            "team",
            "result",
            "opponent",
            "score",
            "opp_score",
            "week_rank",
            "week_opp_rank",
        ]
    ].set_index("week")
    owner_df["team"] = owner_df["team"].map(lambda name: display_names.get(name, name))
    owner_df["opponent"] = owner_df["opponent"].map(lambda name: display_names.get(name, name))

    wins = owner_df.loc[owner_df.result == "W"]
    num_players = len(df.team.unique())
    nplayers_p1 = num_players + 1
    wins["Lucky"] = (wins.week_rank >= 0.5 * nplayers_p1).map(lambda b: "☺️" if b else "")
    wins["VLucky"] = (wins.week_rank >= 0.65 * nplayers_p1).map(lambda b: "🤪" if b else "")
    wins["Lotto"] = (wins.week_rank >= 0.8 * nplayers_p1).map(lambda b: "💸" if b else "")
    wins["KeyWin"] = (wins.week_opp_rank <= 0.5 * nplayers_p1).map(lambda b: "😤" if b else "")
    wins["BuiltDiff"] = (wins.week_opp_rank <= 0.25 * nplayers_p1).map(lambda b: "🗣️" if b else "")

    ties = owner_df.loc[owner_df.result == "T"]

    losses = owner_df.loc[owner_df.result == "L"]
    losses["MissedOpp"] = (losses.week_opp_rank >= 0.5 * nplayers_p1).map(
        lambda b: "🤦‍♂️" if b else ""
    )
    losses["Beefed"] = (losses.week_opp_rank >= 0.7 * nplayers_p1).map(lambda b: "🙈" if b else "")
    losses["Unlucky"] = (losses.week_rank <= 0.5 * nplayers_p1).map(lambda b: "😖" if b else "")
    losses["VUnlucky"] = (losses.week_rank <= 0.3 * nplayers_p1).map(lambda b: "🙃" if b else "")
    losses["KYS"] = (losses.week_rank <= 0.2 * nplayers_p1).map(lambda b: "🔫" if b else "")

    print()
    print("Results:")
    print(owner_df)
    print()
    print("Wins:")
    print(wins)
    print()
    print("Losses:")
    print(losses)
    print()
    if not ties.empty:
        print("Ties (!! 👔 !!):")
        print(ties)
        print()


def cli() -> None:
    run(main)


if __name__ == "__main__":
    cli()
