import json
import logging
import logging.handlers as handlers
import sys

from datetime import datetime, timedelta
from influxdb import InfluxDBClient
from pymongo import MongoClient

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

logHandler = handlers.TimedRotatingFileHandler('cronChecker.log', when='D', interval=1, backupCount=3)
logHandler.setLevel(logging.INFO)
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)


def getConfig():
    with open(sys.path[0] + '/../instance/config.py', 'r') as configfile:
        return json.loads(configfile.read())
    logger.info('ConfigError\tProblem reading config file.')
    sys.exit(1)


def checkForNewSensors(influxClient, mongoClient):

    logger.info('checking for new sensor.')

    now = datetime.now()
    min10Ago = now - timedelta(minute=10)
    min10AgoStr = min10Ago.strftime('%Y-%m-%dT%H:%M:%SZ')

    queryInflux = "SELECT ID, LAST(\"pm2.5 (ug/m^3)\") AS pm25 " \
                  "FROM pm25 WHERE time >= '" + min10AgoStr + "' " \
                  "GROUP BY ID" \

    dataLatestPMPerID = influxClient.query(queryInflux, epoch='ms')
    dataLatestPMPerID = dataLatestPMPerID.raw

    print(dataLatestPMPerID['series'][0])

    db = mongoClient.runningAirUSensor
    allLiveSensors = db.sensors.find()
    print(allLiveSensors)

    for anID in dataLatestPMPerID:

        aSensor = {"macAddress": anID,
                   "createdAt": now}

        foundID = db.liveSensors.find_one({'ID': anID})

        if foundID is None:
            db.liveSensors.insert_one(aSensor)


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

    logger.info('new sensor check successful.')
