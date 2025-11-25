from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import polars as pl
import seaborn as sns


def get_summary_table(all_df: pl.DataFrame, start_week: int, end_week: int):
    df = all_df.filter(pl.col("week").is_between(start_week, end_week, closed="both"))
    players = df.get_column("team").unique().to_list()

    column_counters = defaultdict(lambda: Counter({p: 0 for p in players}))

    for _, group in df.group_by("week"):
        for player in players:
            team_row = group.filter(pl.col("team") == player).get_column("score")
            if team_row.is_empty():
                continue

            score = team_row.item()
            if score is None:
                continue

            all_scores: list[tuple[str, float | None]] = [
                (row["team"], row["score"]) for row in group.select("team", "score").to_dicts()
            ]
            for opp, opp_score in all_scores:
                if opp_score is None or player == opp:
                    continue
                column_counters["W"][player] += score > opp_score
                column_counters["T"][player] += score == opp_score
                column_counters["L"][player] += score < opp_score

    summary = pl.DataFrame(
        {
            "team": players,
            "W": [column_counters["W"][p] for p in players],
            "T": [column_counters["T"][p] for p in players],
            "L": [column_counters["L"][p] for p in players],
        }
    )

    actual_expr = (
        (pl.col("score") > pl.col("opp_score")).fill_null(False).cast(pl.Float64)
        + 0.5 * (pl.col("score") == pl.col("opp_score")).fill_null(False).cast(pl.Float64)
    ).sum()

    team_grouped = df.group_by("team")
    team_stats = team_grouped.agg(
        games_played=pl.col("week").n_unique(),
        actual=actual_expr,
        pf=pl.col("score").sum(),
        pa=pl.col("opp_score").sum(),
        max_score=pl.col("score").max(),
        min_score=pl.col("score").min(),
    )

    has_ties = df.select((pl.col("score") == pl.col("opp_score")).any()).item()
    if not has_ties:
        team_stats = team_stats.with_columns(actual=pl.col("actual").cast(pl.Int64))

    week_stats = (
        df.group_by("week")
        .agg(
            weekly_max=pl.col("score").drop_nans().drop_nulls().max(),
            weekly_min=pl.col("score").drop_nans().drop_nulls().min(),
            weekly_top3=pl.col("score")
            .drop_nans()
            .drop_nulls()
            .sort(descending=True)
            .slice(2, 1)
            .first(),
            weekly_bot3=pl.col("score").drop_nans().drop_nulls().sort().slice(2, 1).first(),
        )
        .rename(
            {
                "weekly_max": "week_max",
                "weekly_min": "week_min",
                "weekly_top3": "week_top3",
                "weekly_bot3": "week_bot3",
            }
        )
    )

    with_week_stats = (
        df.join(week_stats, on="week", how="left")
        .with_columns(
            top1=pl.when(pl.col("score").is_not_null() & pl.col("week_max").is_not_null())
            .then(pl.col("score") >= pl.col("week_max"))
            .otherwise(False),
            bot1=pl.when(pl.col("score").is_not_null() & pl.col("week_min").is_not_null())
            .then(pl.col("score") <= pl.col("week_min"))
            .otherwise(False),
            top3=pl.when(pl.col("score").is_not_null() & pl.col("week_top3").is_not_null())
            .then(pl.col("score") >= pl.col("week_top3"))
            .otherwise(False),
            bot3=pl.when(pl.col("score").is_not_null() & pl.col("week_bot3").is_not_null())
            .then(pl.col("score") <= pl.col("week_bot3"))
            .otherwise(False),
        )
        .group_by("team")
        .agg(
            top1=pl.col("top1").sum(),
            bot1=pl.col("bot1").sum(),
            top3=pl.col("top3").sum(),
            bot3=pl.col("bot3").sum(),
        )
    )

    season = df.get_column("season").unique().item()
    num_weeks = 14 if season > 2020 else 13

    weeks_left = pl.lit(num_weeks) - pl.col("games_played")

    win_expr = (pl.col("W") + 0.5 * pl.col("T")) / (pl.col("W") + pl.col("T") + pl.col("L"))
    exp_wins = win_expr * pl.col("games_played")

    summary = summary.join(team_stats, on="team").join(with_week_stats, on="team", how="left")
    summary = summary.with_columns(
        Pct=win_expr,
        Exp=exp_wins,
        Luck=pl.col("actual") - exp_wins,
        Proj=pl.col("actual") + win_expr * pl.when(weeks_left < 0).then(0).otherwise(weeks_left),
    ).rename(
        {
            "actual": "Actual",
            "pf": "PF",
            "pa": "PA",
            "max_score": "Max",
            "min_score": "Min",
            "top1": "Top1",
            "bot1": "Bot1",
            "top3": "Top3",
            "bot3": "Bot3",
        }
    )

    return summary.sort("Pct", descending=True).with_columns(pl.col(pl.Float64).round(3))


def plot_season_graphs(df: pl.DataFrame, start_week: int, end_week: int, out_dir: Path | None):
    if out_dir is None:
        return
    out_dir.mkdir(parents=True, exist_ok=True)

    summaries = [get_summary_table(df, start_week, end) for end in range(start_week, end_week + 1)]
    weeks = list(range(start_week, end_week + 1))

    def build_metric_series(field: str, transform=None) -> dict[str, list[float | None]]:
        last_summary = summaries[-1].select(["team", field]).to_dict(as_series=False)
        teams = last_summary["team"]
        series: dict[str, list[float | None]] = {team: [] for team in teams}
        for idx, summ in enumerate(summaries, start=1):
            data = summ.select(["team", field]).to_dict(as_series=False)
            values = dict(zip(data["team"], data[field]))
            for team in teams:
                val = values.get(team)
                if transform is not None:
                    val = transform(val, idx)
                series[team].append(val)
        return series

    plot_configs = [
        ("Expected Wins", "Exp", None),
        ("Wins", "Actual", None),
        ("Expected Win%", "Pct", None),
        ("Points Per Game", "PF", lambda val, idx: val / idx if val is not None else None),
        ("PF", "PF", None),
    ]

    plt.style.use("fivethirtyeight")
    for name, field, transform in plot_configs:
        metric_series = build_metric_series(field, transform)
        ordered_labels = sorted(
            metric_series.keys(),
            key=lambda t: (
                metric_series[t][-1] is None,
                metric_series[t][-1] if metric_series[t][-1] is not None else float("-inf"),
            ),
            reverse=True,
        )
        fig, ax = plt.subplots(sharex=True, figsize=(16 * 2, 9 * 2))
        fig.set_tight_layout(True)
        for team in ordered_labels:
            sns.lineplot(x=weeks, y=metric_series[team], ax=ax, label=team)
        ax.set_xlabel("Week")
        ax.set_ylabel(name)
        season = df.get_column("season").unique().item()
        ax.set_title(f"{name} Over {season} Season")
        fig.savefig(out_dir / f"plot_{name}.png", bbox_inches="tight")
        plt.close(fig)
