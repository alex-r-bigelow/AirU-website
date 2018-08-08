import argparse
import calculateEstimates
import json
import logging
import logging.handlers as handlers
import os
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


# getting the config file
def getConfig(aPath, fileName):

    configPath = os.path.join(sys.path[0], aPath)
    fullPath = os.path.join(configPath, fileName)

    with open(fullPath, 'r') as configfile:
        return json.loads(configfile.read())
    sys.stderr.write('ConfigError\tProblem reading config file.\n')
    sys.exit(1)


def main(args):
    debuggingConfigFile = 'modellingConfig_debugging.json'

    parser = argparse.ArgumentParser()
    parser.add_argument("startQuerytime", help="start query time (UTC) for estimation with format: \%Y-\%m-\%dT\%H:\%M:\%SZ")
    parser.add_argument("endQuerytime", help="end query time (UTC) for estimation with format: \%Y-\%m-\%dT\%H:\%M:\%SZ")
    parser.add_argument("interval", help="interval until next estimate calculation in seconds")

    args = parser.parse_args(args)

    startQuerytime = datetime.strptime(args.startQuerytime, '%Y-%m-%dT%H:%M:%SZ')
    endQuerytime = datetime.strptime(args.endQuerytime, '%Y-%m-%dT%H:%M:%SZ')
    interval = timedelta(seconds=int(args.interval))

    modellingConfig = getConfig('../config/', debuggingConfigFile)
    characteristicTimeLength = modellingConfig['characteristicTimeLength']

    # shift the start and end time because startQuerytime is actually not the actual query timebut the end of the window
    start_upperEstimationBound = startQuerytime + timedelta(seconds=characteristicTimeLength)
    end_upperEstimationBound = endQuerytime + timedelta(seconds=characteristicTimeLength)

    LOGGER.info('START upperEstimationBound timstep: %s', start_upperEstimationBound.strftime('%Y-%m-%dT%H:%M:%SZ'))
    LOGGER.info('END upperEstimationBound timstep: %s', end_upperEstimationBound.strftime('%Y-%m-%dT%H:%M:%SZ'))

    while start_upperEstimationBound <= end_upperEstimationBound:
        LOGGER.info('START timstep: %s', startQuerytime.strftime('%Y-%m-%dT%H:%M:%SZ'))

        start = time.time()

        calculateEstimates.main(['false', '--d', debuggingConfigFile, '-q', start_upperEstimationBound.strftime('%Y-%m-%dT%H:%M:%SZ')])

        end = time.time()
        diff = end - start

        LOGGER.info('*********** Time to calculate estimate: {}', format(diff))
        LOGGER.info('Finished timestep: %s', startQuerytime.strftime('%Y-%m-%dT%H:%M:%SZ'))

        startQuerytime += interval
        start_upperEstimationBound = startQuerytime + timedelta(seconds=characteristicTimeLength)


if __name__ == '__main__':
    main(sys.argv[1:])
