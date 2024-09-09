from typing import cast
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import polars as pl
from collections import Counter, defaultdict


def get_summary_table(all_df: pl.DataFrame, start_week: int, end_week: int):
    df = all_df.filter(pl.col("week").is_between(start_week, end_week, closed="both"))
    players = df.get_column("team").unique()

    column_counters = defaultdict(lambda: Counter({p: 0 for p in players}))

    for _, group in df.group_by("week"):
        for player in players:
            team_row = group.filter(pl.col("team") == player).get_column("score")
            if team_row.is_empty():
                continue

            score: float = team_row.item()
            if score is None:
                continue

            all_scores: list[tuple[str, float]] = [
                (row["team"], row["score"]) for row in group.select("team", "score").to_struct()
            ]
            for opp, opp_score in all_scores:
                if opp_score is not None and player != opp:
                    column_counters["W"][player] += score > opp_score
                    column_counters["T"][player] += score == opp_score
                    column_counters["L"][player] += score < opp_score

    data = {"team": players}
    for col, values in column_counters.items():
        data[col] = pl.Series([values[player] for player in players])

    summary = pl.DataFrame(data)
    team_grouped = df.group_by("team")
    week_grouped = df.filter(pl.col("score").is_not_nan()).group_by("week")

    all_wins = pl.col("W") + 0.5 * pl.col("T")
    total = pl.col("W") + pl.col("T") + pl.col("L")
    exp_pct = all_wins / total

    actual_wins = (
        pl.col("score") > pl.col("opp_score") + 0.5 * (pl.col("score") == pl.col("opp_score"))
    ).sum()

    # has_ties = (df["score"] == df["opp_score"]).any()
    # if not has_ties:
    #     summary["Actual"] = summary["Actual"].astype(int)

    season = df.get_column("season").unique().item()
    num_weeks = 14 if season > 2020 else 13
    weeks_played = cast(int, team_grouped.count().get_column("count").max())
    weeks_left = max(num_weeks - weeks_played, 0)

    exp_wins = exp_pct * weeks_played
    luck = pl.col("actual_wins") - pl.col("exp_wins")

    proj_wins = pl.col("actual_wins") + (pl.col("exp_pct") * weeks_left)

    # TODO: remaining SOS (and then incorporate that into projected)

    week_stats = week_grouped.agg(
        max=pl.col("score").max(),
        top3=pl.col("score").head(3).last(),
        bot3=pl.col("score").tail(3).first(),
        min=pl.col("score").min(),
    )

    team_stats = team_grouped.agg(
        actual_wins=actual_wins,
        points_for=pl.col("score").sum(),
        points_against=pl.col("opp_score").sum(),
        max_points=pl.col("score").max(),
        min_points=pl.col("score").min(),
        top1=(pl.col("score") >= week_stats.get_column("max")).sum(),
        top3=(pl.col("score") >= week_stats.get_column("top3")).sum(),
        bot3=(pl.col("score") <= week_stats.get_column("bot3")).sum(),
        bot1=(pl.col("score") <= week_stats.get_column("min")).sum(),
    )

    return (
        summary.join(team_stats, on="team")
        .with_columns(exp_wins=exp_wins, exp_pct=exp_pct)
        .with_columns(luck=luck, proj_wins=proj_wins)
        .sort("exp_pct", descending=True)
        .rename(
            {
                "actual_wins": "ActualWins",
                "points_for": "PF",
                "points_against": "PA",
                "max_points": "Max",
                "min_points": "Min",
                "top1": "Top1",
                "top3": "Top3",
                "bot1": "Bot1",
                "bot3": "Bot3",
                "exp_wins": "ExpWins",
                "exp_pct": "ExpWinPct",
                "luck": "Luck",
                "proj_wins": "ProjWins",
            }
        )
        .to_pandas()
        .set_index("team")
        .round(3)
    )

    # summary["Carpe"] = summary["Actual"] / ((summary["W"] + 0.5 * summary["T"]) / games_played)

    summary = summary.sort_values("Pct", ascending=False).round(3)
    return summary


def plot_season_graphs(df: pl.DataFrame, start_week: int, end_week: int, out_dir: Path):
    summaries = [get_summary_table(df, start_week, end) for end in range(start_week, end_week + 1)]
    plot_configs = [
        (
            "Expected Wins",
            pl.concat(
                [summ["Exp"].rename(f"{i+1}") for i, summ in enumerate(summaries)],
                axis=1,
            ).T,
        ),
        (
            "Wins",
            pl.concat(
                [summ["Actual"].rename(f"{i+1}") for i, summ in enumerate(summaries)],
                axis=1,
            ).T,
        ),
        (
            "Expected Win%",
            pl.concat(
                [summ["Pct"].rename(f"{i+1}") for i, summ in enumerate(summaries)],
                axis=1,
            ).T,
        ),
        (
            "Points Per Game",
            pl.concat(
                [(summ["PF"] / (i + 1)).rename(f"{i+1}") for i, summ in enumerate(summaries)],
                axis=1,
            ).T,
        ),
        (
            "PF",
            pl.concat(
                [summ["PF"].rename(f"{i+1}") for i, summ in enumerate(summaries)],
                axis=1,
            ).T,
        ),
    ]

    plt.style.use("fivethirtyeight")
    for name, series in plot_configs:
        ordered_labels = series.tail(1).squeeze().sort_values(ascending=False).index.values.tolist()
        series = series.loc[:, ordered_labels]
        fig, ax = plt.subplots(sharex=True, figsize=(16 * 2, 9 * 2))
        fig.set_tight_layout(True)
        sns.lineplot(series, ax=ax)
        plt.legend(
            handles=ax.legend_.legendHandles,
            labels=ordered_labels,
        )
        ax.set_xlabel("Week")
        ax.set_ylabel(name)
        season = df.season.unique().item()
        ax.set_title(f"{name} Over {season} Season")
        fig.savefig(out_dir / f"plot_{name}.png", bbox_inches="tight")
        plt.close(fig)
