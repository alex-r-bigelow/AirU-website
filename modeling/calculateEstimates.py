import argparse
import json
import logging
import logging.handlers as handlers
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import os
import sys
import time
# import pytz

from AQ_API import AQGPR
from AQ_DataQuery_API import AQDataQuery
from datetime import datetime, timedelta
from distutils.util import strtobool
from influxdb import InfluxDBClient
from pymongo import MongoClient
# from StringIO import StringIO
from utility_tools import calibrate, datetime2Reltime, findMissings, removeMissings


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - [%(funcName)s:%(lineno)d] - %(levelname)s - %(message)s')

# logHandler = handlers.TimedRotatingFileHandler('cronPMEstimation.log', when='D', interval=1, backupCount=3)
logHandler = handlers.RotatingFileHandler('cronPMEstimation.log', maxBytes=5000000, backupCount=5)
logHandler.setLevel(logging.INFO)
logHandler.setFormatter(formatter)
LOGGER.addHandler(logHandler)

currentUTCtime = datetime.utcnow()
# currentUTCtime_str = currentUTCtime.isoformat()


# getting the config file
def getConfig(aPath, fileName):

    configPath = os.path.join(sys.path[0], aPath)
    fullPath = os.path.join(configPath, fileName)

    with open(fullPath, 'r') as configfile:
        return json.loads(configfile.read())
    sys.stderr.write('%s\tConfigError\tProblem reading config file.\n' % currentUTCtime.isoformat())
    sys.exit(1)


def generateQueryMeshGrid(numberGridCells1D, bottomLeftCorner, topRightCorner, theQueryTimeRel):
    gridCellSize_lat = abs(bottomLeftCorner['lat'] - topRightCorner['lat']) / numberGridCells1D
    gridCellSize_lng = abs(bottomLeftCorner['lng'] - topRightCorner['lng']) / numberGridCells1D

    lats = []
    lngs = []
    times = []
    for lng in range(numberGridCells1D + 1):
        longitude = bottomLeftCorner['lng'] + (lng * gridCellSize_lng)

        for lat in range(numberGridCells1D + 1):
            latitude = topRightCorner['lat'] + (lat * gridCellSize_lat)
            lats.append([float(latitude)])
            lngs.append([float(longitude)])
            # times.append([int(0)])
            times.append([theQueryTimeRel])

    return {'lats': lats, 'lngs': lngs, 'times': times}


def generateQueryMeshVariableGrid(numberGridCellsLAT, numberGridCellsLONG, bottomLeftCorner, topRightCorner, theQueryTimeRel):
    gridCellSize_lat = abs(bottomLeftCorner['lat'] - topRightCorner['lat']) / numberGridCellsLAT
    gridCellSize_lng = abs(bottomLeftCorner['lng'] - topRightCorner['lng']) / numberGridCellsLONG

    lats = []
    lngs = []
    times = []
    for aRelativeTime in theQueryTimeRel:
        for lng in range(numberGridCellsLONG + 1):
            longitude = bottomLeftCorner['lng'] + (lng * gridCellSize_lng)

            for lat in range(numberGridCellsLAT + 1):
                latitude = bottomLeftCorner['lat'] + (lat * gridCellSize_lat)
                lats.append([float(latitude)])
                lngs.append([float(longitude)])
                # times.append([int(0)])
                times.append([aRelativeTime])

    return {'lats': lats, 'lngs': lngs, 'times': times}


def getEstimate(purpleAirClient, airuClient, theDBs, characteristicLength_space, characteristicLength_time, mesh, start, end, theBottomLeftCorner, theTopRightCorner, binFrequency):

    startDate = start
    endDate = end

    # for 4h characteristicLength => 3600 * 2
    # for 1/6h characteristicLength => 120
    data_tr = AQDataQuery(purpleAirClient, airuClient, theDBs, startDate, endDate, binFrequency, theTopRightCorner['lat'], theBottomLeftCorner['lng'], theBottomLeftCorner['lat'], theTopRightCorner['lng'])

    pm2p5_tr = data_tr[0]
    long_tr = data_tr[1]
    lat_tr = data_tr[2]
    nLats = len(lat_tr)
    time_tr = data_tr[3]
    nts = len(time_tr)
    sensorModels = data_tr[4]

    # print(time_tr)

    pm2p5_tr = findMissings(pm2p5_tr)
    pm2p5_tr = np.matrix(pm2p5_tr, dtype=float)
    pm2p5_tr = calibrate(pm2p5_tr, sensorModels)
    pm2p5_tr = pm2p5_tr.flatten().T
    lat_tr = np.tile(np.matrix(lat_tr).T, [nts, 1])
    long_tr = np.tile(np.matrix(long_tr).T, [nts, 1])
    time_tr = datetime2Reltime(time_tr, min(time_tr))
    time_tr = np.repeat(np.matrix(time_tr).T, nLats, axis=0)

    # meshInfo = generateQueryMeshGrid(numberOfGridCells1D, topleftCorner, bottomRightCorner)
    # meshInfo = generateQueryMeshVariableGrid(numberGridCells_LAT, numberGridCells_LONG, bottomLeftCorner, topRightCorner, queryTimeRel)
    meshInfo = mesh

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
    # sigmaF0 = 8.3779
    #
    # # characteristic length for space (x and y), characteristic length for time
    # L0 = [4.7273, 7.5732]
    #
    # # This is the noise variance and is being calculated from the sensor calibration data. This is hard coded in the AQGPR as well
    # sigmaN = 5.81
    #
    # # This is the degree of the mean function used in the regression, we would like to have it equal to 1 for now
    # basisFnDeg = 1

    # Indicating wether we want to do training to find model parameters or not
    # isTrain = False
    #
    # # Indicating wether we want to do the regression and find some estimates or not
    # isRegression = True

    # the rest uses the default values given by Amir
    # [yPred, yVar] = AQGPR(x_Q, x_tr, pm2p5_tr)  # , sigmaF0, L0, sigmaN, basisFnDeg, isTrain, isRegression)
    [yPred, yVar] = AQGPR(x_Q, x_tr, pm2p5_tr, sigmaF0=10, L0=[characteristicLength_space, characteristicLength_time/3600.0], sigmaN=4.2, basisFnDeg=1, isTrain=False, isRegression=True)

    return [yPred, yVar, x_Q[:, 0], x_Q[:, 1]]


def calculateContours(X, Y, Z, endDate, levels, colorBands):

    # from: http://hplgit.github.io/web4sciapps/doc/pub/._part0013_web4sa_plain.html
    # stringFile = StringIO()

    # # creating the fileName of contour file
    # outputdirectory = '/home/airu/AirU-website/svgs'
    # anSVGfile = os.path.join(outputdirectory, endDate.strftime('%Y-%m-%dT%H:%M:%SZ') + '.png')

    plt.figure()
    plt.axis('off')  # Removes axes
    plt.gca().set_position([0, 0, 1, 1])
    # plt.axes().set_frame_on(False)
    # plt.axes().patch.set_visible(False)
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

    # levels = [0.0, 12.0, 35.4, 55.4, 150.4, 250.4]
    # c = ('#a6d96a', '#ffffbf', '#fdae61', '#d7191c', '#bd0026', '#a63603')
    theContours = plt.contourf(X, Y, Z, levels, colors=colorBands)

    # plt.savefig(stringFile, format="svg")
    # theSVG = stringFile.getvalue()
    # print(theSVG)

    # plt.colorbar(theContours)  # This will give you a legend

    new_contours = []

    for i, collection in enumerate(theContours.collections):

        for path in collection.get_paths():

            new_contour = {}
            new_contour['path'] = []
            new_contour['level'] = i
            new_contour['k'] = i

            for (coords, code_type) in zip(path.vertices, path.codes):

                if code_type == 1:
                    new_contour['path'] += [['M', float('{:.5f}'.format(coords[0])), float('{:.5f}'.format(coords[1]))]]
                elif code_type == 2:
                    new_contour['path'] += [['L', float('{:.5f}'.format(coords[0])), float('{:.5f}'.format(coords[1]))]]
                elif code_type == 79:
                    new_contour['path'] += [['L', float('{:.5f}'.format(coords[0])), float('{:.5f}'.format(coords[1]))]]

            new_contours += [new_contour]

    # to save as svg file in directory svgs
    # plt.savefig(anSVGfile, format="png")  # stopped saving the contour file on server

    # stringFile.close()
    plt.close()

    return new_contours


def storeInMongo(configForModelling, client, theCollection, anEstimate, queryTime, endTime, levels, colorBands, theNowMinusCHLT, numberGridCells_LAT, numberGridCells_LONG):

    db = client.airudb

    # flatten the matrices to list
    estimates_list = np.squeeze(np.asarray(anEstimate[0])).tolist()
    variability = np.squeeze(np.asarray(anEstimate[1])).tolist()
    lat_list = np.squeeze(np.asarray(anEstimate[2])).tolist()
    lng_list = np.squeeze(np.asarray(anEstimate[3])).tolist()

    # make numpy arrays for the contours
    pmEstimates = np.asarray(anEstimate[0]).reshape(numberGridCells_LONG + 1, numberGridCells_LAT + 1)
    latQuery = np.asarray(anEstimate[2]).reshape(numberGridCells_LONG + 1, numberGridCells_LAT + 1)
    longQuery = np.asarray(anEstimate[3]).reshape(numberGridCells_LONG + 1, numberGridCells_LAT + 1)

    zippedEstimateData = zip(lat_list, lng_list, estimates_list, variability)

    theEstimates = {}
    for i, aZippedEstimate in enumerate(zippedEstimateData):
        header = ('lat', 'long', 'pm25', 'variability')
        theEstimate = dict(zip(header, aZippedEstimate))

        theEstimationMetadata = db.estimationMetadata.find_one({"gridID": int(configForModelling['currentGridVersion']), "metadataType": theCollection})

        if theEstimationMetadata is not None:

            for key, value in theEstimationMetadata['transformedGrid'].iteritems():
                if value['lat'][0] == theEstimate['lat'] and value['lngs'][0] == theEstimate['long']:
                    # LOGGER.info('found a match')

                    theEstimates[str(i)] = {'gridELementID': key, 'pm25': theEstimate['pm25'], 'variability': theEstimate['variability']}
                    break
        else:
            LOGGER.info('Did not find the appropriate estimation metadata.')

    # take the estimates and get the contours
    # binaryFile = calculateContours(latQuery, longQuery, pmEstimates)
    contours = calculateContours(latQuery, longQuery, pmEstimates, queryTime, levels, colorBands)

    # save the contour svg serialized in the db.

    anEstimateSlice = {"estimationFor": queryTime,
                       "modelVersion": '1.0.0',
                       # "numberOfGridCells_LAT": anEstimate[4],
                       # "numberOfGridCells_LONG": anEstimate[5],
                       "estimate": theEstimates,
                       # "location": location,
                       "contours": contours}

    if theNowMinusCHLT:
        # high variability estimation

        # if theCollection == 'timeSlicedEstimates_high':
        if theCollection == configForModelling['metadataType_highUncertainty']:
            db[theCollection].insert_one(anEstimateSlice)

        LOGGER.info('inserted data slice for %s into %s', queryTime.strftime('%Y-%m-%dT%H:%M:%SZ'), theCollection)
    else:
        # low variability estimation

        # remove estimates from the high uncertainty db that are too old
        # if theCollection == 'timeSlicedEstimates_low':
        if theCollection == configForModelling['metadataType_lowUncertainty']:
            db[theCollection].insert_one(anEstimateSlice)

            # oldestEstimation = db.timeSlicedEstimates_high.find().sort("estimationFor", 1).limit(5)
            oldestEstimation = db[(configForModelling['metadataType_highUncertainty'])].find().sort("estimationFor", 1).limit(5)

            for document in oldestEstimation:
                LOGGER.info('preparing to delete %s', document['estimationFor'])
                documentID = document.get('_id')
                # timeDifference = datetime.strptime(endTime, '%Y-%m-%dT%H:%M:%SZ') - datetime.strptime(document['estimationFor'], '%Y-%m-%dT%H:%M:%SZ')
                LOGGER.info(endTime)
                LOGGER.info(document['estimationFor'])
                timeDifference = endTime - document['estimationFor']
                LOGGER.info(timeDifference)
                # print('******* timeDifference *****')
                # print(timeDifference)
                # print(timeDifference.total_seconds() / (60 * 60))
                LOGGER.info('querytime is %s', endTime.strftime('%Y-%m-%dT%H:%M:%SZ'))
                LOGGER.info('time of time slice is %s', document['estimationFor'])
                LOGGER.info('time difference is %s', timeDifference)

                if (timeDifference.total_seconds()) >= configForModelling['characteristicTimeLength']:
                    db[configForModelling['metadataType_highUncertainty']].delete_one({"_id": documentID})
                    LOGGER.info('deleted %s', document['estimationFor'])

        LOGGER.info('inserted data slice for %s into %s', queryTime.strftime('%Y-%m-%dT%H:%M:%SZ'), theCollection)


def storeGridMetadata(client, gridID, metadataType, numberGridCells_LAT, numberGridCells_LONG, theMesh, theBottomLeftCorner, theTopRightCorner):

    # transform theMesh which looks like this {'lats': lats, 'lngs': lngs, 'times': times} to {0: {"lat": lats[0], "lngs": lngs[0], "times": times[0]}, ...}
    transformedMesh = {}
    numberofElementsInMesh = len(theMesh['lats'])
    for i in range(numberofElementsInMesh):
        transformedMesh[str(i)] = {"lat": theMesh['lats'][i], "lngs": theMesh['lngs'][i], "times": theMesh['times'][i]}

    aMetadataElement = {"gridID": int(gridID),
                        "metadataType": metadataType,
                        "numberOfElementsInMesh": numberofElementsInMesh,
                        "grid": theMesh,
                        "bottomLeftCorner": theBottomLeftCorner,
                        "topRightCorner": theTopRightCorner,
                        "transformedGrid": transformedMesh,
                        "numberOfGridCells": {'lat': numberGridCells_LAT, 'long': numberGridCells_LONG}}

    db = client.airudb
    db.estimationMetadata.insert_one(aMetadataElement)

    LOGGER.info('inserted estimation Metadata %s', gridID)


def main(args):

    start01 = time.time()

    parser = argparse.ArgumentParser()
    parser.add_argument("highUncertainty", help="true means only now() to now()-characteristicLength, false means now() to now()-characteristicLength and to now()-2*characteristicLength")
    # parser.add_argument("--debugging", help="true means debugging")
    parser.add_argument("-d", "--debugging", help="name of config file")
    parser.add_argument("-q", "--querytime", help="query time (UTC) for estimation with format: %Y-%m-%dT%H:%M:%SZ")

    args = parser.parse_args(args)

    # true means only now()-characteristicLength;
    # false means now() to now()-characteristicLength and to now()-2*characteristicLength
    nowMinusCHLT = bool(strtobool(args.highUncertainty))

    theQueryTime = currentUTCtime

    # take the modeling parameter from the config file
    modellingConfig = getConfig('../config/', 'modellingConfig.json')

    if args.debugging and args.querytime:
        # debugging = bool(strtobool(args.debugging))

        debuggingModelligConfigFileName = args.debugging
        theQueryTime = datetime.strptime(args.querytime, '%Y-%m-%dT%H:%M:%SZ')

        # debugging flag, if true, store data into dbs made for debugging, also allows to add another config file
        if debuggingModelligConfigFileName != '':
            LOGGER.info('modelling config file is %s', debuggingModelligConfigFileName)
            modellingConfig = getConfig('../config/', debuggingModelligConfigFileName)

    # nowMinusCHLT = bool(strtobool(sys.argv[1]))

    # # DEBUGGING CODE PIECE
    # debugging = bool(strtobool(sys.argv[2]))
    # if len(sys.argv) > 3:
    #

    # if debugging:
    #     if debuggingModelligConfigFileName != '':
    #         LOGGER.info('modelling config file is %s', debuggingModelligConfigFileName)
    #         modellingConfig = getConfig('../config/', debuggingModelligConfigFileName)

    # characteristicTimeLength is given in seconds
    characteristicTimeLength = modellingConfig['characteristicTimeLength']
    characteristicSpaceLength = modellingConfig['characteristicSpaceLength']
    binFrequency = modellingConfig['binFrequency']
    theGridID = modellingConfig['currentGridVersion']

    # depending on high or low uncertainty argument generate start time, end time and query time
    if nowMinusCHLT:
        startDate = theQueryTime - timedelta(seconds=characteristicTimeLength)
        endDate = theQueryTime
        queryTime = endDate
        collection = modellingConfig['metadataType_highUncertainty']
    else:
        startDate = theQueryTime - timedelta(seconds=(2 * characteristicTimeLength))
        endDate = theQueryTime
        queryTime = endDate - timedelta(seconds=characteristicTimeLength)
        collection = modellingConfig['metadataType_lowUncertainty']

    # the relative time is always with respect to the start time
    queryTimeRelative = datetime2Reltime([queryTime], startDate)
    # print(queryTimeRelative)

    config = getConfig('../config/', 'config.json')

    end01 = time.time()
    diff01 = end01 - start01
    LOGGER.info('initial phase took %s', diff01)

    start02 = time.time()

    mongodb_url = 'mongodb://{user}:{password}@{host}:{port}/{database}'.format(
        user=config['MONGO_USER'],
        password=config['MONGO_PASSWORD'],
        host=config['MONGO_HOST'],
        port=config['MONGO_PORT'],
        database=config['MONGO_DATABASE'])

    mongoClient = MongoClient(mongodb_url)
    db = mongoClient.airudb

    # query estimationMetadata table if already modeling parameters for the combination of metadataType and gridID exist
    # metadataType provides information about high or low uncertainty, bascially gives a description keyword
    # gridID describes the iteration number
    meshgridInfo = db.estimationMetadata.find_one({"metadataType": collection, "gridID": theGridID})

    # print(meshgridInfo)

    if meshgridInfo is None:

        # geographical area
        bottomLeftCorner = {'lat': modellingConfig['bottomLeftCorner_LAT'], 'lng': modellingConfig['bottomLeftCorner_LONG']}
        topRightCorner = {'lat': modellingConfig['topRightCorner_LAT'], 'lng': modellingConfig['topRightCorner_LONG']}

        numberGridCells_LAT = modellingConfig['numberGridCells_LAT']
        numberGridCells_LONG = modellingConfig['numberGridCells_LONG']

        mesh = generateQueryMeshVariableGrid(numberGridCells_LAT, numberGridCells_LONG, bottomLeftCorner, topRightCorner, queryTimeRelative)

        storeGridMetadata(mongoClient, theGridID, collection, int(numberGridCells_LAT), int(numberGridCells_LONG), mesh, bottomLeftCorner, topRightCorner)
    else:
        mesh = meshgridInfo['grid']
        numberGridCells_LAT = meshgridInfo['numberOfGridCells']['lat']
        numberGridCells_LONG = meshgridInfo['numberOfGridCells']['long']
        bottomLeftCorner = meshgridInfo['bottomLeftCorner']
        topRightCorner = meshgridInfo['topRightCorner']

    end02 = time.time()
    diff02 = end02 - start02
    LOGGER.info('grid generation phase took %s', diff02)

    # levels = [0.0, 12.0, 35.4, 55.4, 150.4, 250.4]
    levels = [0.0, 4.0, 8.0, 12.0, 19.8, 27.6, 35.4, 42.1, 48.7, 55.4, 150.4, 250.4]
    # colorBands = ('#a6d96a', '#ffffbf', '#fdae61', '#d7191c', '#bd0026', '#a63603')
    colorBands = ('#31a354', '#a1d99b', '#e5f5e0', '#ffffcc', '#ffeda0', '#fed976', '#feb24c', '#fd8d3c', '#fc4e2a', '#e31a1c', '#bd0026', '#800026')

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

    start03 = time.time()

    theEstimate = getEstimate(pAirClient, airUClient, dbs, characteristicSpaceLength, characteristicTimeLength, mesh, startDate, endDate, bottomLeftCorner, topRightCorner, binFrequency)

    end03 = time.time()
    diff03 = end03 - start03
    LOGGER.info('estimation phase took %s', diff03)

    start04 = time.time()

    storeInMongo(modellingConfig, mongoClient, collection, theEstimate, queryTime, endDate, levels, colorBands, nowMinusCHLT, numberGridCells_LAT, numberGridCells_LONG)

    end04 = time.time()
    diff04 = end04 - start04
    LOGGER.info('generating contour and storing data phase took %s', diff04)

    LOGGER.info('successful estimation of %s for %s', collection, queryTime.strftime('%Y-%m-%dT%H:%M:%SZ'))


if __name__ == '__main__':

    main(sys.argv[1:])
