from collections import Counter

import numpy as np
import pandas as pd


def most_recent_week(df):
    earliestFuture = df.week.max() + 1
    for wk, group in df.groupby('week'):
        if wk < earliestFuture and not group.score.any():
            earliestFuture = wk
    return earliestFuture - 1


def expected_wins(df, start_week, end_week):
    players = df.team.unique()
    n = len(players)
    noLuckWins = Counter({p: 0. for p in players})
    df = df.query('@start_week <= week <= @end_week')
    for wk, group in df.groupby('week'):
        for p in players:
            pScore = group.loc[group.team == p, 'score'].values[0]
            allScores = group.loc[:, ['team', 'score']].values
            expWins = np.sum(1*(pScore > score) + 0.5*(pScore == score)
                             for opp, score in allScores if opp != p)
            noLuckWins[p] += expWins

    # convert to week-per-game wins
    for p in noLuckWins:
        noLuckWins[p] /= float(n-1)

    return noLuckWins


def expected_win_pct(df, start_week, end_week):
    expWins = expected_wins(df, start_week, end_week)
    for p in expWins:
        expWins[p] /= float(end_week - start_week + 1)
    return expWins


def get_wins(df, start_week, end_week):
    df = df.query('@start_week <= week <= @end_week')
    return dict(df.groupby('team').wins.sum().items())


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
        tm: '{}-{}'.format(round(wins, 2), round(loss, 2))
        for (tm, wins), loss in zip(total_wins.items(), total_losses)
    }


def remaining_schedule(df, start_week, end_week):
    expWins = expected_win_pct(df, start_week, end_week)
    df = df.query('week > @end_week')
    weeksLeft = len(df.week.unique())
    sos = Counter()
    for team, group in df.groupby('team'):
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
    df = df.query('@start_week <= week <= @end_week')
    for k, v in df.groupby('team').score.sum().items():
        points[k] = v
    return points
