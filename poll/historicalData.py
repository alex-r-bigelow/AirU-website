import csv
import json
import logging
import logging.handlers as handlers
# import pytz
import sys
# import requests
# import time

# from datetime import datetime
# from datetime import timedelta
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


def getHistoricalDataAirU(client, filename, sensorID, startDate, endDate):

    logger.info('querying historical data')

    queryAirU = "SELECT * FROM pm25 " \
                "WHERE ID = '" + sensorID + "' " \
                "AND time >= '" + startDate + "' AND time <= '" + endDate + "' "

    logger.info(queryAirU)

    dataAirU = client.query(queryAirU, epoch=None)
    # dataAirU = dataAirU.raw
    result = list(dataAirU.get_points())

    # writing header
    writeLoggingDataToFile(filename, [
        'time',
        'ID',
        'PM2.5'
    ])

    for row in result:

        writeLoggingDataToFile(filename, [row['time'], row['ID'], row['PM2.5']])


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

    filename = '/home/pgoffin/historicalData.csv'

    sensorID = sys.argv[1]
    startDate = sys.argv[2]
    endDate = sys.argv[3]
    getHistoricalDataAirU(influxClient, filename, sensorID, startDate, endDate)
