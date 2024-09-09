from pathlib import Path
import polars as pl

import typer

from power_rankings.parse_utils import get_inputs, most_recent_week


def main(
    owner_name: str,
    html_filename: Path = typer.Argument(..., exists=True, dir_okay=False),
    out_dir: Path = typer.Argument(..., file_okay=False),
    start_week: int | None = None,
    end_week: int | None = None,
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

    df = df.filter(pl.col("week").is_between(start_week, end_week, closed="both")).with_columns(
        week_rank=pl.col("score").rank(descending=True).over("week"),
        week_opp_rank=pl.col("opp_score").rank(descending=True).over("week"),
        result=pl.when(pl.col("wins") == 1.0)
        .then(pl.lit("W"))
        .when(pl.col("wins") == 0.5)
        .then(pl.lit("T"))
        .otherwise(pl.lit("L")),
    )

    owner_df = df.filter(
        pl.col("team").str.to_lowercase().str.contains(owner_name.lower(), strict=True)
    ).with_columns(
        tot_wins=(pl.col("result") == "W").cum_sum(),
        tot_losses=(pl.col("result") == "L").cum_sum(),
    )
    owner_df = owner_df[

            "week",
            "tot_wins",
            "tot_losses",
            "team",
            "result",
            "opponent",
            "score",
            "opp_score",
            "week_rank",
            "week_opp_rank",

    ].to_pandas().set_index("week")

    wins = owner_df.loc[owner_df.result == "W"]
    num_players = df.select(pl.col('team').n_unique()).item()
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
