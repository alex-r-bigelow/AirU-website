import json
import logging
import logging.handlers as handlers
import sys

from datetime import datetime, timedelta
from influxdb import InfluxDBClient
from pymongo import MongoClient


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - [%(funcName)s:%(lineno)d] - %(levelname)s - %(message)s')

# logHandler = handlers.TimedRotatingFileHandler('cronChecker.log', when='D', interval=1, backupCount=3)
logHandler = handlers.RotatingFileHandler('cronChecker.log', maxBytes=5000000, backupCount=5)
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
    # min10Ago = nowUTC - timedelta(minutes=10)
    # min10AgoStr = min10Ago.strftime('%Y-%m-%dT%H:%M:%SZ')

    # new using -24h to keep seeing sensors that have stopped pushing data somewhere in the last 24h
    min24hAgo = nowUTC - timedelta(hours=24)
    min24hAgoStr = min24hAgo.strftime('%Y-%m-%dT%H:%M:%SZ')

    # LOGGER.info(min10AgoStr)
    LOGGER.info(min24hAgoStr)

    queryInflux = "SELECT ID, LAST(\"PM2.5\") AS pm25 " \
                  "FROM pm25 WHERE time >= '" + min24hAgoStr + "' " \
                  "GROUP BY ID" \

    LOGGER.info(queryInflux)
    dataLatestPMPerID = influxClient.query(queryInflux, epoch='ms')
    data = dataLatestPMPerID.raw
    # LOGGER.info(data)

    dataSeries = list(map(lambda x: dict(zip(x['columns'], x['values'][0])), data['series']))
    LOGGER.info(dataSeries)
    # dataSeries = [{u'ID': u'209148E036DE', u'pm25': 22.649, u'time': 1534196832174}, {u'ID': u'209148E036E8', u'pm25': 26.161, u'time': 1534196843826},

    # take out only the ID, and transform each ID to the ":" format
    dataSeries_IDs = [str(":".join([sensor['ID'][i:i + 2] for i in range(0, len(sensor['ID']), 2)])) for sensor in dataSeries]

    db = mongoClient.airudb

    # get the schools --> sensor that should be hidden
    allSchools = [school['macAddress'] for school in db.schools.find()]
    LOGGER.info(allSchools)

    # get all sensors in the liveSensor collection
    allSensorsInLiveSensors = [aLiveSensor['macAddress'] for aLiveSensor in db.liveSensors.find()]

    # get elements to delete from collection
    setOfElementsToDelete = set(allSensorsInLiveSensors) - set(dataSeries_IDs)
    LOGGER.info(setOfElementsToDelete)

    # get elements to insert into collection
    setOfElementsToInsert = set(dataSeries_IDs) - set(allSensorsInLiveSensors)
    LOGGER.info(setOfElementsToInsert)

    for toDelete in setOfElementsToDelete:
        LOGGER.info(toDelete)

        aSensor = {"macAddress": toDelete}

        db.liveSensors.delete_one(aSensor)
        LOGGER.info('sensor %s deleted', toDelete)

    for toInsert in setOfElementsToInsert:
        LOGGER.info(toInsert)

        if toInsert not in allSchools:
            LOGGER.info('ID %s is not a school', toInsert)
            aSensor = {"macAddress": toInsert,
                       "createdAt": nowUTC}

            db.liveSensors.insert_one(aSensor)
            LOGGER.info('sensor %s added', toDelete)

    # for anID in dataSeries:
    #     LOGGER.info(anID)
    #
    #     theID = anID['ID']
    #     idWithColon = ":".join([theID[i:i + 2] for i in range(0, len(theID), 2)])
    #     LOGGER.info(idWithColon)
    #
    #     if idWithColon not in allSchools:
    #         LOGGER.info('ID %s is not a school', idWithColon)
    #         aSensor = {"macAddress": idWithColon,
    #                    "createdAt": nowUTC}
    #
    #         foundID = db.liveSensors.find_one({'macAddress': idWithColon})
    #         LOGGER.info(foundID)
    #         if foundID is None:
    #             db.liveSensors.insert_one(aSensor)
    #             LOGGER.info('sensor %s added', idWithColon)
    #     else:
    #         LOGGER.info('ID %s is a school', idWithColon)


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
