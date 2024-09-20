from pathlib import Path
from typing import Optional

import typer

from power_rankings.parse_utils import get_inputs, most_recent_week


def main(
    owner_name: str,
    html_filename: Path = typer.Argument(..., exists=True, dir_okay=False),
    out_dir: Path = typer.Argument(..., file_okay=False),
    start_week: Optional[int] = None,
    end_week: Optional[int] = None,
):
    """Generates rankings for a given season, given the HTML of the schedule
    and results."""
    df = get_inputs(html_filename)

    if start_week is None:
        start_week = 1

    most_recent = most_recent_week(df)
    if end_week is None:
        end_week = most_recent
    else:
        end_week = min(end_week, most_recent)

    out_dir.mkdir(parents=True, exist_ok=True)

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
