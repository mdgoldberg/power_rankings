from pathlib import Path

import typer

from power_rankings import cli_common
from power_rankings.parse_utils import get_inputs, most_recent_week


def main(
    owner_name: str,
    html_filename: Path | None = typer.Argument(None, dir_okay=False),
    out_dir: Path | None = typer.Argument(None, file_okay=False),
    start_week: int | None = None,
    end_week: int | None = None,
    offline: bool = cli_common.offline_option(),
    league: str | None = cli_common.league_option(),
    league_id: int | None = cli_common.league_id_option(),
    season: int | None = cli_common.season_option(),
    download_dir: Path | None = cli_common.download_dir_option(),
    leagues_file: Path | None = cli_common.leagues_file_option(),
    refresh: bool = cli_common.refresh_option(),
    headless: bool = cli_common.headless_option(default=True),
    username: str | None = cli_common.username_option(),
    password: str | None = cli_common.password_option(),
    log_level: str = cli_common.log_level_option(),
):
    """Generates rankings for a given season, given the HTML of the schedule
    and results."""
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
    owner_df = df.loc[df.team.str.lower().str.contains(owner_name.lower())]
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


def cli():
    typer.run(main)


if __name__ == "__main__":
    cli()
