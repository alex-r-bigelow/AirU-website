import csv
import json
import logging
import logging.handlers as handlers
import os
# import pytz
import requests
import sys
# import requests
# import time

from datetime import datetime
from datetime import timedelta
# from influxdb.exceptions import InfluxDBClientError
from influxdb import InfluxDBClient

TIMESTAMP = datetime.now().isoformat()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

logHandler = handlers.TimedRotatingFileHandler('historicalDataGetter.log', when='D', interval=1, backupCount=3)
logHandler.setLevel(logging.INFO)
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)


def getConfig():
    # print(os.path.dirname(os.path.realpath(__file__)))
    # os.path.join(os.path.dirname(filename),
    #                              os.path.basename(filename))
    with open(sys.path[0] + '/../config/config.json', 'r') as jsonConfigfile:
        return json.load(jsonConfigfile)
    logger.info('ConfigError\tProblem reading config file.')
    sys.exit(1)


def writeLoggingDataToFile(fileName, data):

    with open(fileName, 'ab') as csvFile:
        writer = csv.writer(csvFile, delimiter=',', quoting=csv.QUOTE_ALL)
        writer.writerow(data)


def generateDayDates(start, end, delta):

    result = []
    start += delta
    while start < end:
        result.append(start.strftime('%Y-%m-%dT%H:%M:%SZ'))
        start += delta

    result.append(end.strftime('%Y-%m-%dT%H:%M:%SZ'))
    return result


def getHistoricalDataAirU(client, filename, sensorID, theSensorSource, startDate, endDate):

    logger.info('querying historical data')

    startDate = datetime.strptime(startDate, '%Y-%m-%dT%H:%M:%SZ')
    endDate = datetime.strptime(endDate, '%Y-%m-%dT%H:%M:%SZ')

    dayDates = generateDayDates(startDate, endDate, timedelta(days=1))
    logger.info(dayDates)
    start = startDate.strftime('%Y-%m-%dT%H:%M:%SZ')
    logger.info(start)

    # writing header
    writeLoggingDataToFile(filename, [
        'time',
        'ID',
        'PM2.5'
    ])

    for end in dayDates:
        logger.info(end)


        # baseURL = 'http://air.eng.utah.edu/dbapi/api/rawDataFrom?id='
        # sensorSource = '&sensorSource='
        # theStart = '&start='
        # theEnd = '&end='
        # what = '&show=pm25'
        # theURL = '{}{}{}{}{}{}{}{}{}'.format(baseURL, sensorID, sensorSource, theSensorSource, theStart, start, theEnd, end, what)

        # processedDataFrom?id=1010&start=2017-10-01T00:00:00Z&end=2017-10-02T00:00:00Z&function=mean&functionArg=pm25&timeInterval=30m
        baseURL = 'http://air.eng.utah.edu/dbapi/api/processedDataFrom?id='
        sensorSource = '&sensorSource='
        theStart = '&start='
        theEnd = '&end='
        theFunction = '&function=mean'
        theFunctionArg = '&functionArg=pm25'
        theTimeInterval = '&timeInterval=60m'
        theURL = '{}{}{}{}{}{}{}{}{}{}{}'.format(baseURL, sensorID, sensorSource, theSensorSource, theStart, start, theEnd, end, theFunction, theFunctionArg, theTimeInterval)

        logger.info(theURL)

        # /api/rawDataFrom?id=1010&start=2017-10-01T00:00:00Z&end=2017-10-02T00:00:00Z&show=pm25,pm1

        try:
            historicalData = requests.get(theURL)
            historicalData.raise_for_status()
        except requests.exceptions.HTTPError as e:
            sys.stderr.write('%s\tProblem acquiring historic data data;\t%s.\n' % (TIMESTAMP, e))
            return []
        except requests.exceptions.Timeout as e:
            sys.stderr.write('%s\tProblem acquiring historic data;\t%s.\n' % (TIMESTAMP, e))
            return []
        except requests.exceptions.TooManyRedirects as e:
            sys.stderr.write('%s\tProblem acquiring historic data;\t%s.\n' % (TIMESTAMP, e))
            return []
        except requests.exceptions.RequestException as e:
            sys.stderr.write('%s\tProblem acquiring ;\t%s.\n' % (TIMESTAMP, e))
            return []

        # queryAirU = "SELECT * FROM pm25 " \
        #             "WHERE ID = '" + sensorID + "' " \
        #             "AND time >= '" + start + "' AND time <= '" + end + "' "
        #
        # logger.info(queryAirU)
        #
        # dataAirU = client.query(queryAirU, epoch=None)
        # # dataAirU = dataAirU.raw
        # result = list(dataAirU.get_points())

        jsonData = historicalData.json()['data']
        jsonTags = historicalData.json()['tags']

        for aDict in jsonData:
            if aDict['pm25'] is not None:
                writeLoggingDataToFile(filename, [aDict['time'], jsonTags[0]['ID'], aDict['pm25']])

        start = end

    logger.info('writing file is done')


# usage python historicalData.py ID sensorSource 2016-12-15T00:00:00Z 2016-12-22T00:00:00Z
# python historicalData.py 99 Purple\ Air 2017-12-15T00:00:00Z 2017-12-17T00:00:00Z
if __name__ == '__main__':
    config = getConfig()

    influxClient = InfluxDBClient(
        host='air.eng.utah.edu',
        port=8086,
        username=config['airUUsername'],
        password=config['airUPassword'],
        database=config['airuDB'],
        ssl=True,
        verify_ssl=True
    )

    sensorID = sys.argv[1]
    sensorSource = sys.argv[2]
    startDate = sys.argv[3]
    endDate = sys.argv[4]

    filename = 'historicalData-{}-{}-{}.csv'.format(sensorID, startDate.split('T')[0], endDate.split('T')[0])

    # remove the file if it already exists
    try:
        os.remove(filename)
        logger.info('File already existed, removed it.')
    except OSError:
        pass

    logger.info('sensor ID is %s', sensorID)
    logger.info('sensor source is %s', sensorSource)    # airu
    logger.info('start date is %s', startDate)
    logger.info('end date is %s', endDate)
    logger.info('file name is %s', filename)

    getHistoricalDataAirU(influxClient, filename, sensorID, sensorSource, startDate, endDate)
