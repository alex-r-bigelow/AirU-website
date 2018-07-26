import argparse
import calculateEstimates
import sys
from datetime import datetime, timedelta


def main(args):
    parser = argparse.ArgumentParser()
    parser.add_argument("startQuerytime", help="start query time (UTC) for estimation with format: \%Y-\%m-\%dT\%H:\%M:\%SZ")
    parser.add_argument("endQuerytime", help="end query time (UTC) for estimation with format: \%Y-\%m-\%dT\%H:\%M:\%SZ")
    parser.add_argument("interval", help="interval until next estimate calculation in seconds")

    args = parser.parse_args(args)

    startQuerytime = datetime.strptime(args.startQuerytime, '%Y-%m-%dT%H:%M:%SZ')
    endQuerytime = datetime.strptime(args.endQuerytime, '%Y-%m-%dT%H:%M:%SZ')
    interval = timedelta(seconds=args.interval)

    while startQuerytime < endQuerytime:
        calculateEstimates.main(['false', '--d', 'modellingConfig_debugging.json', '-q', '2018-07-26T16:00:00Z'])
        startQuerytime += interval


if __name__ == '__main__':
    main(sys.argv[1:])
