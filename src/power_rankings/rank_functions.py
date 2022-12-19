from collections import Counter, defaultdict

import numpy as np
import pandas as pd


def week_finishes(df, start_week, end_week):
    players = df.team.unique()
    finishes = defaultdict(list)
    df = df.query("@start_week <= week <= @end_week")
    for wk, group in df.groupby("week"):
        group_w_rank = group.assign(rank=group.score.rank(ascending=False))
        for p in players:
            finishes[p].append(int(group_w_rank.loc[group.team == p, "rank"].iloc[0]))

    return finishes


def week_opp_finishes(df, start_week, end_week):
    players = df.team.unique()
    finishes = defaultdict(list)
    df = df.query("@start_week <= week <= @end_week")
    for _, group in df.groupby("week"):
        group_w_rank = group.assign(rank=group.score.rank(ascending=False))
        for p in players:
            finishes[p].append(
                int(group_w_rank.loc[group.opponent == p, "rank"].iloc[0])
            )

    return finishes


def week_win_loss(df, start_week, end_week):
    players = df.team.unique()
    results = defaultdict(list)
    df = df.query("@start_week <= week <= @end_week")
    for wk, group in df.groupby("week"):
        group_w_rank = group.assign(rank=group.score.rank(ascending=False))
        for p in players:
            wl_val = group_w_rank.loc[group.team == p, "wins"].iloc[0]
            wl_str = {0.0: "L", 0.5: "T", 1.0: "W"}[wl_val]
            results[p].append(wl_str)

    return results


def zipped(df, start_week, end_week):
    pts = week_finishes(df, start_week, end_week)
    wl = week_win_loss(df, start_week, end_week)
    return {player: list(zip(pts[player], wl[player])) for player in pts}


def zipped_opp(df, start_week, end_week):
    pts = week_opp_finishes(df, start_week, end_week)
    wl = week_win_loss(df, start_week, end_week)
    return {player: list(zip(pts[player], wl[player])) for player in pts}


def expected_win_pct(df, start_week, end_week):
    expWins = expected_wins(df, start_week, end_week)
    for p in expWins:
        expWins[p] /= float(end_week - start_week + 1)
    return expWins


def get_wins(df, start_week, end_week):
    df = df.query("@start_week <= week <= @end_week")
    return dict(df.groupby("team").wins.sum().items())


def projected_wins(df, start_week, end_week):
    teams = df.team.unique()
    if start_week != 1:
        return {tm: np.nan for tm in teams}
    exp_win_pct = pd.Series(expected_win_pct(df, start_week, end_week))
    current_wins = pd.Series(get_wins(df, start_week, end_week))
    num_past_games = end_week
    num_future_games = df.week.max() - end_week
    future_wins = num_future_games * exp_win_pct
    total_wins = current_wins + future_wins
    return total_wins.to_dict()
    total_losses = num_past_games + num_future_games - total_wins
    return {
        tm: "{}-{}".format(round(wins, 2), round(loss, 2))
        for (tm, wins), loss in zip(total_wins.items(), total_losses)
    }


def remaining_schedule(df, start_week, end_week):
    expWins = expected_win_pct(df, start_week, end_week)
    df = df.query("week > @end_week")
    weeksLeft = len(df.week.unique())
    sos = Counter()
    for team, group in df.groupby("team"):
        sos[team] = np.sum(expWins[opp] for opp in group.opponent)
    for p in sos:
        sos[p] /= float(weeksLeft)
    return sos


def luck_rankings(df, start_week, end_week):
    wins = get_wins(df, start_week, end_week)
    expWins = expected_wins(df, start_week, end_week)
    players = df.team.unique()
    luck = Counter()
    for p in players:
        luck[p] = wins[p] - expWins[p]
    return luck


def points_for(df, start_week, end_week):
    points = Counter()
    df = df.query("@start_week <= week <= @end_week")
    for k, v in df.groupby("team").score.sum().items():
        points[k] = v
    return points


def points_against(df, start_week, end_week):
    points = Counter()
    df = df.query("@start_week <= week <= @end_week")
    for k, v in df.groupby("opponent").score.sum().items():
        points[k] = v
    return points
