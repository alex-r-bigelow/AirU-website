# import csv
import json
import logging
import logging.handlers as handlers
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import sys

from AQ_API import AQGPR
from AQ_DataQuery_API import AQDataQuery
from bson.binary import Binary
from datetime import datetime, timedelta
from influxdb import InfluxDBClient
from io import BytesIO
from pymongo import MongoClient
from StringIO import StringIO
from utility_tools import calibrate, datetime2Reltime, findMissings, removeMissings


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
            lats.append([float(latitude)])
            lngs.append([float(longitude)])
            times.append([int(0)])

    return {'lats': lats, 'lngs': lngs, 'times': times}


def getEstimate(purpleAirClient, airuClient, theDBs):
    numberOfGridCells1D = 20
    currentUTCtime = datetime.utcnow()

    startDate = currentUTCtime - timedelta(days=1)
    endDate = currentUTCtime
    topleftCorner = {'lat': 40.810476, 'lng': -112.001349}
    bottomRightCorner = {'lat': 40.598850, 'lng': -111.713403}

    data_tr = AQDataQuery(purpleAirClient, airuClient, theDBs, startDate, endDate, 3600 * 6, topleftCorner['lat'], topleftCorner['lng'], bottomRightCorner['lat'], bottomRightCorner['lng'])

    pm2p5_tr = data_tr[0]
    long_tr = data_tr[1]
    lat_tr = data_tr[2]
    nLats = len(lat_tr)
    time_tr = data_tr[3]
    nts = len(time_tr)
    sensorModels = data_tr[4]

    pm2p5_tr = findMissings(pm2p5_tr)
    pm2p5_tr = np.matrix(pm2p5_tr, dtype=float)
    pm2p5_tr = calibrate(pm2p5_tr, sensorModels)
    pm2p5_tr = pm2p5_tr.flatten().T
    lat_tr = np.tile(np.matrix(lat_tr).T, [nts, 1])
    long_tr = np.tile(np.matrix(long_tr).T, [nts, 1])
    time_tr = datetime2Reltime(time_tr, min(time_tr))
    time_tr = np.repeat(np.matrix(time_tr).T, nLats, axis=0)

    meshInfo = generateQueryMeshGrid(numberOfGridCells1D, topleftCorner, bottomRightCorner)

    # long_tr = readCSVFile('data/example_data/LONG_tr.csv')
    # lat_tr = readCSVFile('data/example_data/LAT_tr.csv')
    # time_tr = readCSVFile('data/example_data/TIME_tr.csv')
    # pm2p5_tr = readCSVFile('data/example_data/PM2p5_tr.csv')
    # long_Q = readCSVFile('data/example_data/LONG_Q.csv')
    # lat_Q = readCSVFile('data/example_data/LAT_Q.csv')
    # time_Q = readCSVFile('data/example_data/TIME_Q.csv')

    # long_tr = np.matrix(long_tr)
    # long_tr = longitudes
    # lat_tr = np.matrix(lat_tr)
    # lat_tr = latitudes
    # time_tr = np.matrix(time_tr)
    # time_tr = times
    long_Q = np.matrix(meshInfo['lngs'])
    lat_Q = np.matrix(meshInfo['lats'])
    time_Q = np.matrix(meshInfo['times'])

    # This would be y_tr of the AQGPR function
    # pm2p5_tr = np.matrix(pm25)
    # pm2p5_tr = pm25

    # This would be the x_tr of the AQGPR function
    x_tr = np.concatenate((lat_tr, long_tr, time_tr), axis=1)
    x_tr, pm2p5_tr = removeMissings(x_tr, pm2p5_tr)
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

    return [yPred, yVar, x_Q[:, 0], x_Q[:, 1], numberOfGridCells1D]


def calculateContours(X, Y, Z):

    # from: http://hplgit.github.io/web4sciapps/doc/pub/._part0013_web4sa_plain.html
    stringFile = StringIO()

    plt.figure()
    # to set contourf levels, simply add N like so:
    #    # N = 4
    #    # CS = plt.contourf(Z, N)
    # there will be filled colored regions between the values set

    # Y ou can also do this to manually change the cutoff levels for the contours:
    #    # levels = [0.0, 0.2, 0.5, 0.9, 1.5, 2.5, 3.5]
    #    # contour = plt.contour(Z, levels)

    # To set colors:
    # c = ('#ff0000', '#ffff00', '#0000FF', '0.6', 'c', 'm')
    # CS = plt.contourf(Z, 5, colors=c)
    CS = plt.contourf(X, Y, Z)

    plt.colorbar(CS)  # This will give you a legend
    plt.axis('off')  # Removes axes
    plt.savefig(stringFile, format="svg")
    theSVG = stringFile.getvalue()
    theSVG = '<svg' + theSVG.split('<svg')[1]
    stringFile.close()
    print(theSVG)
    print(type(stringFile))
    binaryFile = Binary(str.encode(stringFile))
    return binaryFile


def storeInMongo(client, anEstimate):

    db = client.airudb

    # flatten the matrices to list
    estimates_list = np.squeeze(np.asarray(anEstimate[0])).tolist()
    variability = np.squeeze(np.asarray(anEstimate[1])).tolist()
    lat_list = np.squeeze(np.asarray(anEstimate[2])).tolist()
    lng_list = np.squeeze(np.asarray(anEstimate[3])).tolist()

    # make numpy arrays for the contours
    pmEstimates = np.asarray(anEstimate[0]).reshape(anEstimate[4], anEstimate[4])
    latQuery = np.asarray(anEstimate[2]).reshape(anEstimate[4], anEstimate[4])
    longQuery = np.asarray(anEstimate[3]).reshape(anEstimate[4], anEstimate[4])

    zippedEstimateData = zip(lat_list, lng_list, estimates_list, variability)

    theEstimates = []
    for aZippedEstimate in zippedEstimateData:
        header = ('lat', 'long', 'pm25', 'variability')
        theEstimate = dict(zip(header, aZippedEstimate))
        theEstimates.append(theEstimate)

    # take the estimates and get the contours
    binaryFile = calculateContours(latQuery, longQuery, pmEstimates)

    # save the contour svg serialized in the db.

    anEstimateSlice = {"estimationFor": TIMESTAMP,
                       "modelVersion": '1.0.0',
                       "numberOfGridCells1D": anEstimate[4],
                       "estimate": theEstimates,
                       "svgBinary": binaryFile}

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
