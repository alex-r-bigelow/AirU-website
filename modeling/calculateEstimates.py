# import csv
import json
import logging
import logging.handlers as handlers
import numpy as np
import sys

from AQ_API import AQGPR
from AQ_DataQuery_API import AQDataQuery
from datetime import datetime
from pymongo import MongoClient
from influxdb import InfluxDBClient


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

logHandler = handlers.TimedRotatingFileHandler('cronPMEstimation.log', when='D', interval=1, backupCount=3)
logHandler.setLevel(logging.INFO)
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)

TIMESTAMP = datetime.now().isoformat()


def getConfig():
    with open(sys.path[0] + '/../config/config.json', 'r') as configfile:
        return json.loads(configfile.read())
    sys.stderr.write('%s\tConfigError\tProblem reading config file.\n' % TIMESTAMP)
    sys.exit(1)


def generateQueryMeshGrid(numberGridCells1D, topLeftCorner, bottomRightCorner):
    gridCellSize_lat = abs(topLeftCorner['lat'] - bottomRightCorner['lat']) / numberGridCells1D
    gridCellSize_lng = abs(topLeftCorner['lng'] - bottomRightCorner['lng']) / numberGridCells1D

    lats = []
    lngs = []
    times = []
    for lng in range(numberGridCells1D):
        longitude = topLeftCorner['lng'] + (lng * gridCellSize_lng)

        for lat in range(numberGridCells1D):
            latitude = topLeftCorner['lat'] - (lat * gridCellSize_lat)
            lats.append(latitude)
            lngs.append(longitude)
            times.append(0)

    return {'lats': lats, 'lngs': lngs, 'times': times}


def getEstimate(purpleAirClient, airuClient, theDBs):
    startDate = datetime(2018, 1, 7)
    endDate = datetime(2018, 1, 11)
    topleftCorner = {'lat': 40.810476, 'lng': -112.001349}
    bottomRightCorner = {'lat': 40.598850, 'lng': -111.713403}

    data = AQDataQuery(purpleAirClient, airuClient, theDBs, startDate, endDate, 3600 * 6, topleftCorner['lat'], topleftCorner['lng'], bottomRightCorner['lat'], bottomRightCorner['lng'])

    pm25 = data[0]
    longitudes = data[1]
    latitudes = data[2]
    nLats = len(latitudes)
    times = data[3]
    nts = len(times)
    # sensorModels = data[4]

    pm25 = np.matrix(pm25).flatten().T
    latitudes = np.tile(np.matrix(latitudes).T, [nts, 1])
    longitudes = np.tile(np.matrix(longitudes).T, [nts, 1])
    times = np.repeat(np.matrix(times).T, nLats, axis=0)

    meshInfo = generateQueryMeshGrid(20, topleftCorner, bottomRightCorner)

    # long_tr = readCSVFile('data/example_data/LONG_tr.csv')
    # lat_tr = readCSVFile('data/example_data/LAT_tr.csv')
    # time_tr = readCSVFile('data/example_data/TIME_tr.csv')
    # pm2p5_tr = readCSVFile('data/example_data/PM2p5_tr.csv')
    # long_Q = readCSVFile('data/example_data/LONG_Q.csv')
    # lat_Q = readCSVFile('data/example_data/LAT_Q.csv')
    # time_Q = readCSVFile('data/example_data/TIME_Q.csv')

    # long_tr = np.matrix(long_tr)
    long_tr = longitudes
    # lat_tr = np.matrix(lat_tr)
    lat_tr = latitudes
    # time_tr = np.matrix(time_tr)
    time_tr = times
    long_Q = np.matrix(meshInfo['lngs'])
    lat_Q = np.matrix(meshInfo['lats'])
    time_Q = np.matrix(meshInfo['times'])

    # This would be y_tr of the AQGPR function
    # pm2p5_tr = np.matrix(pm25)
    pm2p5_tr = pm25

    # This would be the x_tr of the AQGPR function
    x_tr = np.concatenate((lat_tr, long_tr, time_tr), axis=1)
    # This would be the xQuery of the AQGPR function
    x_Q = np.concatenate((lat_Q, long_Q, time_Q), axis=1)

    # set parameters
    # we usually initialize sigmaF0 for training as the standard deviation of the sensor measurements
    # sigmaF0=np.std(pm2p5_tr, ddof=1)
    # If we know  sigmaF from previous training we use the found parameter
    sigmaF0 = 8.3779

    # characteristic length for space (x and y), characteristic length for time
    L0 = [4.7273, 7.5732]

    # This is the noise variance and is being calculated from the sensor calibration data. This is hard coded in the AQGPR as well
    sigmaN = 5.81

    # This is the degree of the mean function used in the regression, we would like to have it equal to 1 for now
    basisFnDeg = 1

    # Indicating wether we want to do training to find model parameters or not
    isTrain = False

    # Indicating wether we want to do the regression and find some estimates or not
    isRegression = True

    [yPred, yVar] = AQGPR(x_Q, x_tr, pm2p5_tr, sigmaF0, L0, sigmaN, basisFnDeg, isTrain, isRegression)

    return [yPred, yVar]


def storeInMongo(client, anEstimate):

    db = client.airudb

    anEstimateSlice = {"estimationFor": TIMESTAMP,
                       "estimate": anEstimate[0],
                       "variability": anEstimate[1]}

    db.timeSlicedEstimates.insert_one(anEstimateSlice)
    logger.info('inserted data slice for %s', TIMESTAMP)


if __name__ == '__main__':
    config = getConfig()

    # PurpleAir client
    pAirClient = InfluxDBClient(
        config['INFLUX_HOST'],
        config['INFLUX_PORT'],
        config['INFLUX_MODELLING_USERNAME'],
        config['INFLUX_MODELLING_PASSWORD'],
        config['PURPLE_AIR_DB'],
        ssl=True,
        verify_ssl=True
    )

    # airU client
    airUClient = InfluxDBClient(
        config['INFLUX_HOST'],
        config['INFLUX_PORT'],
        config['INFLUX_MODELLING_USERNAME'],
        config['INFLUX_MODELLING_PASSWORD'],
        config['AIRU_DB'],
        ssl=True,
        verify_ssl=True
    )

    dbs = {'airu_pm25_measurement': config['INFLUX_AIRU_PM25_MEASUREMENT'],
           'airu_lat_measurement': config['INFLUX_AIRU_LATITUDE_MEASUREMENT'],
           'airu_long_measurement': config['INFLUX_AIRU_LONGITUDE_MEASUREMENT']}

    theEstimate = getEstimate(pAirClient, airUClient, dbs)

    mongodb_url = 'mongodb://{user}:{password}@{host}:{port}/{database}'.format(
        user=config['MONGO_USER'],
        password=config['MONGO_PASSWORD'],
        host=config['MONGO_HOST'],
        port=config['MONGO_PORT'],
        database=config['MONGO_DATABASE'])

    mongoClient = MongoClient(mongodb_url)
    storeInMongo(mongoClient, theEstimate)

    logger.info('new sensor check successful.')
