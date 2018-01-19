import csv
import logging
import logging.handlers as handlers
import os
import requests
import sys

from datetime import datetime
from datetime import timedelta


TIMESTAMP = datetime.now().isoformat()

# setting up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

logHandler = handlers.TimedRotatingFileHandler('historicalDataGetter.log', when='D', interval=1, backupCount=3)
logHandler.setLevel(logging.INFO)
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)


def writeLoggingDataToFile(fileName, data):
    """ Writes data, usually a row worth of data, to the csv file fileName """

    with open(fileName, 'ab') as csvFile:
        writer = csv.writer(csvFile, delimiter=',', quoting=csv.QUOTE_ALL)
        writer.writerow(data)


def generateDayDates(start, end, delta):
    """ Returns the days between start and end, excluding start but including end as a list """

    result = []
    start += delta
    while start < end:
        result.append(start.strftime('%Y-%m-%dT%H:%M:%SZ'))
        start += delta

    result.append(end.strftime('%Y-%m-%dT%H:%M:%SZ'))
    return result


# time on the db is UTC (MST + 7h)
def getHistoricalDataAirU(dataType, filename, sensorID, theSensorSource, startDate, endDate):
    """ Queries the API and writes to the csv file """

    logger.info('querying historical data')

    startDate = datetime.strptime(startDate, '%Y-%m-%dT%H:%M:%SZ')
    endDate = datetime.strptime(endDate, '%Y-%m-%dT%H:%M:%SZ')

    # Asking influx for more than 1000 data points will always only result in 1000 data points therefore
    # break the queries up
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

        theURL = ''
        sensorSource = '&sensorSource='
        theStart = '&start='
        theEnd = '&end='
        if dataType == 'raw':
            baseURL = 'http://air.eng.utah.edu/dbapi/api/rawDataFrom?id='

            what = '&show=pm25'
            theURL = '{}{}{}{}{}{}{}{}{}'.format(baseURL, sensorID, sensorSource, theSensorSource, theStart, start, theEnd, end, what)

        else:
            baseURL = 'http://air.eng.utah.edu/dbapi/api/processedDataFrom?id='

            theFunction = '&function=mean'
            theFunctionArg = '&functionArg=pm25'
            theTimeInterval = '&timeInterval=60m'
            theURL = '{}{}{}{}{}{}{}{}{}{}{}'.format(baseURL, sensorID, sensorSource, theSensorSource, theStart, start, theEnd, end, theFunction, theFunctionArg, theTimeInterval)

        logger.info(theURL)

        try:
            historicalData = requests.get(theURL)
            historicalData.raise_for_status()
        except requests.exceptions.HTTPError as e:
            sys.stderr.write('%s\tProblem acquiring historical data;\t%s.\n' % (TIMESTAMP, e))
            return []
        except requests.exceptions.Timeout as e:
            sys.stderr.write('%s\tProblem acquiring historical data;\t%s.\n' % (TIMESTAMP, e))
            return []
        except requests.exceptions.TooManyRedirects as e:
            sys.stderr.write('%s\tProblem acquiring historical data;\t%s.\n' % (TIMESTAMP, e))
            return []
        except requests.exceptions.RequestException as e:
            sys.stderr.write('%s\tProblem acquiring historical;\t%s.\n' % (TIMESTAMP, e))
            return []

        jsonData = historicalData.json()['data']
        jsonTags = historicalData.json()['tags']

        for aDict in jsonData:
            if aDict['pm25'] is not None:
                writeLoggingDataToFile(filename, [aDict['time'], jsonTags[0]['ID'], aDict['pm25']])

        start = end

    logger.info('writing file is done')


# usage: python historicalData.py ID rawORprocessed sensorSource start end
# example: python historicalData.py 99 raw Purple\ Air 2017-12-15T00:00:00Z 2017-12-17T00:00:00Z
# example: python historicalData.py 99 processed airu 2017-12-15T00:00:00Z 2017-12-17T00:00:00Z
if __name__ == '__main__':

    sensorID = sys.argv[1]
    dataType = sys.argv[2]
    sensorSource = sys.argv[3]
    startDate = sys.argv[4]
    endDate = sys.argv[5]

    filename = 'historicalData-{}-{}-{}-{}.csv'.format(dataType, sensorID, startDate.split('T')[0], endDate.split('T')[0])

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

    getHistoricalDataAirU(dataType, filename, sensorID, sensorSource, startDate, endDate)

    logger.info('data quering is done')
