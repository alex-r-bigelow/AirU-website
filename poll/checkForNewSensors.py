import json
import logging
import logging.handlers as handlers
import sys

from datetime import datetime, timedelta
from influxdb import InfluxDBClient
from pymongo import MongoClient


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

logHandler = handlers.TimedRotatingFileHandler('cronChecker.log', when='D', interval=1, backupCount=3)
logHandler.setLevel(logging.INFO)
logHandler.setFormatter(formatter)
LOGGER.addHandler(logHandler)


def getConfig():
    with open(sys.path[0] + '/../config/config.json', 'r') as configfile:
        return json.loads(configfile.read())
    LOGGER.info('ConfigError\tProblem reading config file.')
    sys.exit(1)


def checkForNewSensors(influxClient, mongoClient):

    LOGGER.info('checking for new sensor.')

    # now = datetime.now()
    # min10Ago = now - timedelta(minutes=10)
    # min10AgoStr = min10Ago.strftime('%Y-%m-%dT%H:%M:%SZ')

    nowUTC = datetime.utcnow()
    min10Ago = nowUTC - timedelta(minutes=10)
    min10AgoStr = min10Ago.strftime('%Y-%m-%dT%H:%M:%SZ')

    LOGGER.info(min10AgoStr)

    queryInflux = "SELECT ID, LAST(\"PM2.5\") AS pm25 " \
                  "FROM pm25 WHERE time >= '" + min10AgoStr + "' " \
                  "GROUP BY ID" \

    LOGGER.info(queryInflux)
    dataLatestPMPerID = influxClient.query(queryInflux, epoch='ms')
    data = dataLatestPMPerID.raw

    dataSeries = list(map(lambda x: dict(zip(x['columns'], x['values'][0])), data['series']))
    LOGGER.info(dataSeries)

    db = mongoClient.airudb
    # allLiveSensors = db.liveSensors.find()
    # LOGGER.info(allLiveSensors)

    # get the schools
    allSchools = [school['macAddress'] for school in db.schools.find()]
    LOGGER.info(allSchools)

    for anID in dataSeries:
        LOGGER.info(anID)

        theID = anID['ID']
        idWithColon = ":".join([theID[i:i + 2] for i in range(0, len(theID), 2)])
        LOGGER.info(idWithColon)

        if idWithColon not in allSchools:
            LOGGER.info('ID %s is not a school', idWithColon)
            aSensor = {"macAddress": idWithColon,
                       "createdAt_utc": nowUTC}

            foundID = db.liveSensors.find_one({'macAddress': idWithColon})
            LOGGER.info(foundID)
            if foundID is None:
                db.liveSensors.insert_one(aSensor)
                LOGGER.info('sensor %s added', idWithColon)
        else:
            LOGGER.info('ID %s is a school', idWithColon)


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

    mongodb_url = 'mongodb://{user}:{password}@{host}:{port}/{database}'.format(
        user=config['MONGO_USER'],
        password=config['MONGO_PASSWORD'],
        host=config['MONGO_HOST'],
        port=config['MONGO_PORT'],
        database=config['MONGO_DATABASE'])

    mongoClient = MongoClient(mongodb_url)

    checkForNewSensors(influxClient, mongoClient)

    LOGGER.info('new sensor check successful.')
