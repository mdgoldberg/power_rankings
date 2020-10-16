#! /usr/bin/env python3

from collections import Counter

import click

from . import power_rankings
from . import rank_functions


@click.command()
@click.argument('base_filename')
@click.argument('start_year', type=int)
@click.argument('end_year', default=2018)
def main(base_filename, start_year, end_year):
    rfs = {'Expected Wins': rank_functions.expected_wins,
           'Luck Wins': rank_functions.luck_rankings,
           'Wins': rank_functions.get_wins,
           'Points For': rank_functions.points_for,
           }
    rfTitles = list(rfs.keys())
    counters = {title: Counter() for title in rfTitles}

    for yr in range(start_year, end_year + 1):
        df = power_rankings.get_inputs('{}{}.html'.format(base_filename, yr))
        start_week = 1
        end_week = rank_functions.most_recent_week(df)
        for title, rf in rfs.items():
            results = rf(df, start_week, end_week)
            for p in results:
                counters[title][p] += results[p]

    for title, counter in counters.items():
        print(('{} Rankings:'.format(title)))
        for i, (name, num) in enumerate(counter.most_common()):
            print(('{:2}. {:18} {:.3f}'.format(i+1, name, num)))
        print()

if __name__ == '__main__':
    main()
