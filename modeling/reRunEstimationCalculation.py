import argparse
import calculateEstimates
import logging
import logging.handlers as handlers
import sys
import time
from datetime import datetime, timedelta

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - [%(funcName)s:%(lineno)d] - %(levelname)s - %(message)s')

# logHandler = handlers.TimedRotatingFileHandler('cronPMEstimation.log', when='D', interval=1, backupCount=3)
logHandler = handlers.RotatingFileHandler('reRunEstimation.log', maxBytes=5000000, backupCount=5)
logHandler.setLevel(logging.INFO)
logHandler.setFormatter(formatter)
LOGGER.addHandler(logHandler)


def main(args):
    parser = argparse.ArgumentParser()
    parser.add_argument("startQuerytime", help="start query time (UTC) for estimation with format: \%Y-\%m-\%dT\%H:\%M:\%SZ")
    parser.add_argument("endQuerytime", help="end query time (UTC) for estimation with format: \%Y-\%m-\%dT\%H:\%M:\%SZ")
    parser.add_argument("interval", help="interval until next estimate calculation in seconds")

    args = parser.parse_args(args)

    startQuerytime = datetime.strptime(args.startQuerytime, '%Y-%m-%dT%H:%M:%SZ')
    endQuerytime = datetime.strptime(args.endQuerytime, '%Y-%m-%dT%H:%M:%SZ')
    interval = timedelta(seconds=int(args.interval))

    while startQuerytime < endQuerytime:
        LOGGER.info('START timstep: %s', startQuerytime.strftime('%Y-%m-%dT%H:%M:%SZ'))

        start = time.time()

        calculateEstimates.main(['false', '--d', 'modellingConfig_debugging.json', '-q', startQuerytime.strftime('%Y-%m-%dT%H:%M:%SZ')])
        startQuerytime += interval

        end = time.time()

        LOGGER.info('*********** Time to calculate estimate: {}', format(end - start))
        LOGGER.info('Finished timestep: %s', startQuerytime.strftime('%Y-%m-%dT%H:%M:%SZ'))


if __name__ == '__main__':
    main(sys.argv[1:])
