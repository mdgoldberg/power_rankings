import pandas as pd
from collections import Counter
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from power_rankings.parse_utils import most_recent_week
import pandas as pd
import numpy as np
from collections import Counter, defaultdict
from power_rankings.parse_utils import most_recent_week


def get_summary_table(all_df: pd.DataFrame, start_week: int, end_week: int):
    df = all_df.loc[(start_week <= all_df.week) & (all_df.week <= end_week)]
    players = df.team.unique()

    column_counters = defaultdict(lambda: Counter({p: 0 for p in players}))

    for _, group in df.groupby("week"):
        for player in players:
            team_row = group.loc[group.team == player, "score"]
            if team_row.empty:
                continue

            score: float = team_row.values[0].item()
            all_scores: list[tuple[str, float]] = group.loc[
                :, ["team", "score"]
            ].values.tolist()
            for opp, opp_score in all_scores:
                if player != opp:
                    column_counters["W"][player] += score > opp_score
                    column_counters["T"][player] += score == opp_score
                    column_counters["L"][player] += score < opp_score

    summary = pd.DataFrame(column_counters)
    team_grouped = df.groupby("team")
    week_grouped = df.groupby("week")

    summary["Pct"] = (summary["W"] + 0.5 * summary["T"]) / (
        summary["W"] + summary["T"] + summary["L"]
    )

    summary["Actual"] = team_grouped.apply(
        lambda tm: ((tm.score > tm.opp_score) + 0.5 * (tm.score == tm.opp_score)).sum()
    )

    has_ties = (df["score"] == df["opp_score"]).any()
    if not has_ties:
        summary["Actual"] = summary["Actual"].astype(int)

    games_played = team_grouped.week.nunique()
    summary["Exp"] = summary["Pct"] * games_played
    summary["Luck"] = summary["Actual"] - summary["Exp"]

    season = df["season"].unique().item()
    num_weeks = 14 if season > 2020 else 13
    weeks_left = np.maximum(num_weeks - games_played, 0)
    summary["Proj"] = summary["Actual"] + (summary["Pct"] * weeks_left)

    # TODO: remaining SOS (and then incorporate that into projected)

    summary["PF"] = team_grouped.score.sum()
    summary["PA"] = team_grouped.opp_score.sum()

    summary["Max"] = team_grouped.score.max()
    summary["Min"] = team_grouped.score.min()

    weekly_max = week_grouped.score.max()
    weekly_min = week_grouped.score.min()
    weekly_top3 = week_grouped.score.nth(2)
    weekly_bot3 = week_grouped.score.nth(-3)

    summary["Top1"] = team_grouped.apply(
        lambda tm: sum(
            score >= weekly_max[wk]
            for wk, score in tm.set_index("week").score.to_dict().items()
        )
    )
    summary["Bot1"] = team_grouped.apply(
        lambda tm: sum(
            score <= weekly_min[wk]
            for wk, score in tm.set_index("week").score.to_dict().items()
        )
    )
    summary["Top3"] = team_grouped.apply(
        lambda tm: sum(
            score >= weekly_top3[wk]
            for wk, score in tm.set_index("week").score.to_dict().items()
        )
    )
    summary["Bot3"] = team_grouped.apply(
        lambda tm: sum(
            score <= weekly_bot3[wk]
            for wk, score in tm.set_index("week").score.to_dict().items()
        )
    )

    summary = summary.sort_values("Pct", ascending=False).round(3)
    return summary


def plot_season_graphs(df: pd.DataFrame, out_dir: Path):
    most_recent = most_recent_week(df)
    summaries = [get_summary_table(df, 1, i) for i in range(1, most_recent)]
    plot_configs = [
        (
            "Expected Wins",
            pd.concat(
                [summ["Exp"].rename(f"{i+1}") for i, summ in enumerate(summaries)],
                axis=1,
            ).T,
        ),
        (
            "Wins",
            pd.concat(
                [summ["Actual"].rename(f"{i+1}") for i, summ in enumerate(summaries)],
                axis=1,
            ).T,
        ),
        (
            "Expected Win%",
            pd.concat(
                [summ["Pct"].rename(f"{i+1}") for i, summ in enumerate(summaries)],
                axis=1,
            ).T,
        ),
        (
            "Points Per Game",
            pd.concat(
                [
                    (summ["PF"] / (i + 1)).rename(f"{i+1}")
                    for i, summ in enumerate(summaries)
                ],
                axis=1,
            ).T,
        ),
        (
            "PF",
            pd.concat(
                [summ["PF"].rename(f"{i+1}") for i, summ in enumerate(summaries)],
                axis=1,
            ).T,
        ),
    ]

    plt.style.use("fivethirtyeight")
    fig, axs = plt.subplots(
        nrows=len(plot_configs), ncols=1, sharex=True, figsize=(9 * 3, 16 * 3)
    )
    fig.set_tight_layout(True)

    for ax, (name, series) in zip(axs, plot_configs):
        sns.lineplot(series, ax=ax)
        ax.set_xlabel("Week")
        ax.set_ylabel(name)
        season = df.season.unique().item()
        ax.set_title(f"{name} Over {season} Season")

    fig.savefig(out_dir / "plot.png", bbox_inches="tight")
