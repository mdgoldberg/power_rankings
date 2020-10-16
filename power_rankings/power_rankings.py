import re
from collections import Counter

import click
import numpy as np
import pandas as pd
from pyquery import PyQuery as pq

from power_rankings import rank_functions

NUM_WEEKS = 13
NUM_TEAMS = 12


def get_inputs(fn):
    with open(fn) as f:
        html = f.read()

    doc = pq(html)
    table = doc("div.matchup--table table.Table")
    trs = table("tbody tr")
    trs = [tr for tr in list(trs.items()) if len(tr("td")) == 6]
    trs = trs[: int(NUM_TEAMS * NUM_WEEKS / 2)]
    weeks = np.split(np.array(trs, dtype=object), NUM_WEEKS)
    raw_info = [
        [
            {
                "away": td[1].item().text_content(),
                "away_score_str": td[2].item().text_content(),
                "home_score_str": td[3].item().text_content(),
                "home": td[4].item().text_content(),
            }
            for tr in week
            for td in tr
        ]
        for week in weeks
    ]
    matchups = [
        [(matchup["away"], matchup["home"]) for matchup in week] for week in raw_info
    ]
    scores = [
        {
            team: float(score_str) if score_str else 0.
            for matchup in week
            for (team, score_str) in [
                (matchup["away"], matchup["away_score_str"]),
                (matchup["home"], matchup["home_score_str"]),
            ]
        }
        for week in raw_info
    ]
    dicts = []
    for i, (mu, score) in enumerate(zip(matchups, scores)):
        for p1, p2 in mu:
            d1 = {
                "week": i + 1,
                "team": p1,
                "opponent": p2,
                "score": score[p1],
                "oppScore": score[p2],
            }
            d2 = {
                "week": i + 1,
                "team": p2,
                "opponent": p1,
                "score": score[p2],
                "oppScore": score[p1],
            }
            dicts.extend([d1, d2])
    df = pd.DataFrame(dicts)

    def wins_func(t, o):
        """Two arguments are team and opponent scores. Returns 1 if team won,
        0.5 if tied, 0 if team lost."""
        return 1.0 * (t > o) + 0.5 * (t == o) if t + o > 0.0 else 0.0

    df["wins"] = [wins_func(score, opp) for score, opp in zip(df.score, df.oppScore)]
    yrMatch = re.search(r"(20\d{2})", fn)
    year = int(yrMatch.group(1)) if yrMatch else np.nan
    df["year"] = year
    return df


def ranking_strings(df, rfs, start_week, end_week):
    year = df.year.unique().item()
    retStr = "{} Power Rankings: Weeks {}-{}\n".format(year, start_week, end_week)
    retStr += "=" * len(retStr) + "\n"
    for title, rf in rfs:
        ranks = Counter(rf(df, start_week, end_week))
        ordered = ranks.most_common()
        retStr += "{} Rankings:\n".format(title)
        for (i, (name, val)) in enumerate(ordered):
            if isinstance(val, int) or isinstance(val, float):
                retStr += "{}. {}, {:.3f}\n".format(i + 1, name, val)
            else:
                retStr += "{}. {}, {}\n".format(i + 1, name, val)
        retStr += "\n"
    return retStr


@click.command()
@click.argument("html-filename")
@click.option(
    "-o",
    "--out-filename",
    help=(
        "The power rankings will be dumped into this file. "
        "If not provided, power rankings will be echoed to "
        "stdout."
    ),
)
@click.option(
    "--start-week", default=1, help="The first week to consider in generating rankings."
)
@click.option(
    "--end-week", type=int, help="The last week to consider in generating rankings."
)
def main(html_filename, out_filename, start_week, end_week):
    """Generates rankings for a given season, given the HTML of the schedule
    and results."""
    rfs = (
        ("Expected Wins", rank_functions.expected_wins),
        ("Expected WPct", rank_functions.expected_win_pct),
        ("Projected Wins", rank_functions.projected_wins),
        ("Standings", rank_functions.get_wins),
        ("Points For", rank_functions.points_for),
        ("Remaining SOS", rank_functions.remaining_schedule),
        ("Luck Wins", rank_functions.luck_rankings),
    )
    df = get_inputs(html_filename)
    if end_week is None:
        end_week = rank_functions.most_recent_week(df)
    else:
        end_week = min(end_week, rank_functions.most_recent_week(df))
    output_str = ranking_strings(df, rfs, start_week, end_week)
    if out_filename:
        with open(out_filename, "w") as f:
            f.write(output_str)
    else:
        click.echo(output_str)


if __name__ == "__main__":
    main()
