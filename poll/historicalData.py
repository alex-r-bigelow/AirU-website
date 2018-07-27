import csv
import logging
import logging.handlers as handlers
import os
import pytz
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


# transform a current time string from MST or MDT to UTC, returns string
def currentToUTCasString(aTime):

    print(aTime)
    local_tz = pytz.timezone('MST7MDT')
    # localize current time to current timezone
    local_dt = local_tz.localize(datetime.strptime(aTime, '%Y-%m-%dT%H:%M:%SZ'), is_dst=None)
    print(local_dt)
    server_tz = pytz.timezone('UTC')
    # transform local timezone time to UTC
    localInUTC = local_dt.astimezone(server_tz)

    return localInUTC.strftime('%Y-%m-%dT%H:%M:%SZ')


# transform a UTC time string to the current timezone either MST or MDT
def UTCTimeToCurrentTZString(aTime):

    print(aTime)
    server_tz = pytz.timezone('UTC')
    # localize UTC time to UTC timezone
    server_dt = server_tz.localize(datetime.strptime(aTime, '%Y-%m-%dT%H:%M:%SZ'), is_dst=None)
    print(server_dt)
    local_tz = pytz.timezone('MST7MDT')
    # transform UTC to local timezone
    UTCInLocal = server_dt.astimezone(local_tz)

    return UTCInLocal.strftime('%Y-%m-%dT%H:%M:%SZ')


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
def getHistoricalDataAirU(dataType, filename, sensorID, theSensorSource, startDateStr, endDateStr):
    """ Queries the API and writes to the csv file """

    logger.info('querying historical data')

    startDate = datetime.strptime(startDateStr, '%Y-%m-%dT%H:%M:%SZ')
    endDate = datetime.strptime(endDateStr, '%Y-%m-%dT%H:%M:%SZ')

    # Asking influx for more than 1000 data points will always only result in 1000 data points therefore
    # break the queries up
    dayDates = generateDayDates(startDate, endDate, timedelta(days=1))
    logger.info(dayDates)
    # start = startDate.strftime('%Y-%m-%dT%H:%M:%SZ')
    start = startDateStr
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

        start = end

        try:
            historicalData = requests.get(theURL)
            historicalData.raise_for_status()
        except requests.exceptions.HTTPError as e:
            sys.stderr.write('%s\tProblem acquiring historical data (HTTPError);\t%s.\n' % (TIMESTAMP, e))
            continue
        except requests.exceptions.Timeout as e:
            sys.stderr.write('%s\tProblem acquiring historical data (Timeout);\t%s.\n' % (TIMESTAMP, e))
            continue
        except requests.exceptions.TooManyRedirects as e:
            sys.stderr.write('%s\tProblem acquiring historical data (TooManyRedirects);\t%s.\n' % (TIMESTAMP, e))
            continue
        except requests.exceptions.RequestException as e:
            sys.stderr.write('%s\tProblem acquiring historical data (RequestException);\t%s.\n' % (TIMESTAMP, e))
            continue

        jsonData = historicalData.json()['data']
        jsonTags = historicalData.json()['tags']

        for aDict in jsonData:
            if aDict['pm25'] is not None:

                print(aDict['time'])
                currentTimezone_dt = UTCTimeToCurrentTZString(aDict['time'])
                print('current timezone date')
                print(currentTimezone_dt)
                # local_tz = pytz.timezone('MST')
                # serverTimezone = pytz.timezone('UTC')
                # server_dt = serverTimezone.localize(datetime.strptime(aDict['time'], '%Y-%m-%dT%H:%M:%SZ'), is_dst=None)  # now local time on server is MST, add that information to the time
                # print(server_dt)
                # mst_dt = server_dt.astimezone(local_tz)
                # print(mst_dt)
                writeLoggingDataToFile(filename, [currentTimezone_dt, jsonTags[0]['ID'], aDict['pm25']])

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

    storeDataInDirectory = 'JimmyData'

    # from: https://stackoverflow.com/questions/273192/how-can-i-create-a-directory-if-it-does-not-exist
    try:
        os.makedirs(storeDataInDirectory)
    except OSError:
        if not os.path.isdir(storeDataInDirectory):
            raise

    filename = 'historicalData-{}-{}-{}-{}.csv'.format(dataType, sensorID, startDate.split('T')[0], endDate.split('T')[0])
    filePathToData = os.path.join(storeDataInDirectory, filename)

    # take input dates in current timezone (MST or MDT) ==> input dates are either in MST or MDT depending on the dates
    # transform these dates to server time whcih is in UTC
    startDate_utc = currentToUTCasString(startDate)
    print('startDate in UTC')
    print(startDate_utc)
    endDate_utc = currentToUTCasString(endDate)
    print('endDate in UTC')
    print(endDate_utc)

    # remove the file if it already exists
    try:
        os.remove(filePathToData)
        logger.info('File already existed, removed it.')
    except OSError:
        pass

    logger.info('sensor ID is %s', sensorID)
    logger.info('sensor source is %s', sensorSource)    # airu
    logger.info('start date is %s', startDate)
    logger.info('end date is %s', endDate)
    logger.info('file name is %s', filePathToData)

    getHistoricalDataAirU(dataType, filePathToData, sensorID, sensorSource, startDate_utc, endDate_utc)

    logger.info('data quering is done')
