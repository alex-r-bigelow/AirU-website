import csv
import logging
import logging.handlers as handlers
import sys
import json

from datetime import datetime
# from influxdb.exceptions import InfluxDBClientError
from influxdb import InfluxDBClient

TIMESTAMP = datetime.now().isoformat()

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - [%(funcName)s:%(lineno)d] - %(levelname)s - %(message)s')

logHandler = handlers.RotatingFileHandler('jimmyPaperDataTesting.log', maxBytes=5000000, backupCount=5)
logHandler.setLevel(logging.INFO)
logHandler.setFormatter(formatter)
LOGGER.addHandler(logHandler)


def getConfig():
    with open(sys.path[0] + '/../config/config.json', 'r') as configfile:
        return json.loads(configfile.read())
    sys.stderr.write('%s\tConfigError\tProblem reading config file.\n' % TIMESTAMP)
    sys.exit(1)


def readCSVFile(fileName):
    """ read csv file and ouput it as a list"""

    data = []
    with open(fileName, 'rb') as csvFile:
        csvReader = csv.reader(csvFile, delimiter=',')
        next(csvReader)
        for row in csvReader:
            aTime = row['time']
            anID = row['entity_id']
            aValue = row['value']

            LOGGER.info(aTime)
            LOGGER.info(anID)
            LOGGER.info(aValue)

            data.append([aTime, anID, aValue])

    return data


def pushDataToInfluxDB(client, aData):

    for aRow in aData:

        point = {
            'measurement': 'indoorAirQuality_Paper',
            'fields': {},
            'tags': {
            }
        }

        point['time'] = aRow[0]
        point['tags']['entity_id'] = aRow[1]
        point['fields']['pm25'] = aRow[3]

        LOGGER.info(point)

        client.write_points([point])


if __name__ == '__main__':

    config = getConfig()
    client = InfluxDBClient(
        'air.eng.utah.edu',
        8086,
        config['pollingUsername'],
        config['pollingPassword'],
        'JimmIndoorPaper',
        ssl=True,
        verify_ssl=True
    )

    fileName = 'deployment_008_all_pmSmall.csv'

    theData = readCSVFile(fileName)

    pushDataToInfluxDB(client, theData)
