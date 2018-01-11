import csv
import json
import logging
import logging.handlers as handlers
# import pytz
import sys
# import requests
# import time

from datetime import datetime
from datetime import timedelta
# from influxdb.exceptions import InfluxDBClientError
from influxdb import InfluxDBClient


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

logHandler = handlers.TimedRotatingFileHandler('historicalDataGetter.log', when='D', interval=1, backupCount=3)
logHandler.setLevel(logging.INFO)
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)


def getConfig():
    with open(sys.path[0] + '/../config/config.json', 'r') as configfile:
        return json.loads(configfile.read())
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

    return result


def getHistoricalDataAirU(client, filename, sensorID, startDate, endDate):

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

        queryAirU = "SELECT * FROM pm25 " \
                    "WHERE ID = '" + sensorID + "' " \
                    "AND time >= '" + start + "' AND time <= '" + end + "' "

        logger.info(queryAirU)

        dataAirU = client.query(queryAirU, epoch=None)
        # dataAirU = dataAirU.raw
        result = list(dataAirU.get_points())

        for row in result:
            writeLoggingDataToFile(filename, [row['time'], row['ID'], row['PM2.5']])

        start = end

    logger.info('writing file is done')


# usage python historicalData.py ID 2016-12-15T00:00:00Z 2016-12-22T00:00:00Z
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
    startDate = sys.argv[2]
    endDate = sys.argv[3]

    filename = '/home/pgoffin/historicalData-{}-{}-{}.csv'.format(sensorID, startDate.split('T')[0], endDate.split('T')[0])

    logger.info('sensor ID is %s', sensorID)
    logger.info('start date is %s', startDate)
    logger.info('end date is %s', endDate)
    logger.info('file name is %s', filename)

    getHistoricalDataAirU(influxClient, filename, sensorID, startDate, endDate)
