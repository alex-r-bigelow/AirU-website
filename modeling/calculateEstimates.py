import json
import logging
import logging.handlers as handlers
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import os
import sys
import pytz

from AQ_API import AQGPR
from AQ_DataQuery_API import AQDataQuery
from datetime import datetime, timedelta
from distutils.util import strtobool
from influxdb import InfluxDBClient
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

# TIMESTAMP = datetime.now().isoformat()
currentUTCtime = datetime.utcnow()
currentUTCtime_str = currentUTCtime.isoformat()

characteristicTimeLength = 7.5732


def getConfig():
    with open(sys.path[0] + '/../config/config.json', 'r') as configfile:
        return json.loads(configfile.read())
    sys.stderr.write('%s\tConfigError\tProblem reading config file.\n' % currentUTCtime_str)
    sys.exit(1)


def getUTCTime(aTime_dt):
    localTimezone = pytz.timezone('MST')
    UTCTimezone = pytz.timezone('UTC')
    local_dt = localTimezone.localize(aTime_dt, is_dst=None)  # now local time on server is MST, add that information to the time
    # local_dt = localTimezone.localize(datetime.strptime(aTimeString, '%Y-%m-%dT%H:%M:%SZ'), is_dst=None)  # now local time on server is MST, add that information to the time
    utc_dt = local_dt.astimezone(UTCTimezone)
    return utc_dt


def generateQueryMeshGrid(numberGridCells1D, bottomLeftCorner, topRightCorner, theQueryTimeRel):
    gridCellSize_lat = abs(bottomLeftCorner['lat'] - topRightCorner['lat']) / numberGridCells1D
    gridCellSize_lng = abs(bottomLeftCorner['lng'] - topRightCorner['lng']) / numberGridCells1D

    lats = []
    lngs = []
    times = []
    for lng in range(numberGridCells1D):
        longitude = bottomLeftCorner['lng'] + (lng * gridCellSize_lng)

        for lat in range(numberGridCells1D):
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
        for lng in range(numberGridCellsLONG):
            longitude = bottomLeftCorner['lng'] + (lng * gridCellSize_lng)

            for lat in range(numberGridCellsLAT):
                latitude = bottomLeftCorner['lat'] + (lat * gridCellSize_lat)
                lats.append([float(latitude)])
                lngs.append([float(longitude)])
                # times.append([int(0)])
                times.append([aRelativeTime])

    return {'lats': lats, 'lngs': lngs, 'times': times}


def getEstimate(purpleAirClient, airuClient, theDBs, nowMinusCHLT, mesh, start, end):

    startDate = start
    endDate = end

# TODO is the binnfrequency the way to get the 3 to 6 points?
    data_tr = AQDataQuery(purpleAirClient, airuClient, theDBs, startDate, endDate, 3600 * 6, topRightCorner['lat'], bottomLeftCorner['lng'], bottomLeftCorner['lat'], topRightCorner['lng'])

    pm2p5_tr = data_tr[0]
    long_tr = data_tr[1]
    lat_tr = data_tr[2]
    nLats = len(lat_tr)
    time_tr = data_tr[3]
    nts = len(time_tr)
    sensorModels = data_tr[4]

    print(time_tr)

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
    [yPred, yVar] = AQGPR(x_Q, x_tr, pm2p5_tr)  # , sigmaF0, L0, sigmaN, basisFnDeg, isTrain, isRegression)

    return [yPred, yVar, x_Q[:, 0], x_Q[:, 1]]


def calculateContours(X, Y, Z, endDate, levels, colorBands):

    # from: http://hplgit.github.io/web4sciapps/doc/pub/._part0013_web4sa_plain.html
    stringFile = StringIO()

    outputdirectory = '/home/airu/AirU-website/svgs'
    anSVGfile = os.path.join(outputdirectory, endDate + '.svg')

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

    # levels = [0.0, 12.0, 35.4, 55.4, 150.4, 250.4]
    # c = ('#a6d96a', '#ffffbf', '#fdae61', '#d7191c', '#bd0026', '#a63603')
    theContours = plt.contourf(X, Y, Z, levels, colors=colorBands)

    plt.axis('off')  # Removes axes
    plt.savefig(stringFile, format="svg")
    # theSVG = stringFile.getvalue()
    # print(theSVG)

    # to save as svg file in directory svgs
    plt.savefig(anSVGfile, format="svg")

    # plt.colorbar(theContours)  # This will give you a legend

    new_contours = []

    for i, collection in enumerate(theContours.collections):
        # print('********** i + collection **********')
        # print(i)
        # print(collection)

        for path in collection.get_paths():
            # coords = path.vertices

            new_contour = {}
            new_contour['path'] = []
            new_contour['level'] = i
            new_contour['k'] = i

            # print('********** path **********')
            # print(path)

            # prev_coords = None
            for (coords, code_type) in zip(path.vertices, path.codes):

                # print('********** coords + code type **********')
                # print(coords)
                # print(code_type)

                if code_type == 1:
                    new_contour['path'] += [['M', float('{:.3f}'.format(coords[0])), float('{:.3f}'.format(coords[1]))]]
                elif code_type == 2:
                    new_contour['path'] += [['L', float('{:.3f}'.format(coords[0])), float('{:.3f}'.format(coords[1]))]]

            new_contours += [new_contour]

    stringFile.close()

    return new_contours

    # saving the svg part
    # plt.axis('off')  # Removes axes
    # plt.savefig(stringFile, format="svg")
    # theSVG = stringFile.getvalue()
    # # theSVG = '<svg' + theSVG.split('<svg')[1]
    #
    # encodedString = theSVG.decode('utf8')
    #
    # encodedString = encodedString.encode('utf8')
    #
    # binaryFile = Binary(encodedString)
    # binaryFile = bson.BSON.encode({'svg': binaryFile})


def storeInMongo(client, theCollection, anEstimate, queryTime, levels, colorBands, theNowMinusCHLT, numberGridCells_LAT, numberGridCells_LONG, gridID):

    db = client.airudb

    # flatten the matrices to list
    estimates_list = np.squeeze(np.asarray(anEstimate[0])).tolist()
    variability = np.squeeze(np.asarray(anEstimate[1])).tolist()
    lat_list = np.squeeze(np.asarray(anEstimate[2])).tolist()
    lng_list = np.squeeze(np.asarray(anEstimate[3])).tolist()

    # make numpy arrays for the contours

    pmEstimates = np.asarray(anEstimate[0]).reshape(numberGridCells_LONG, numberGridCells_LAT)
    latQuery = np.asarray(anEstimate[2]).reshape(numberGridCells_LONG, numberGridCells_LAT)
    longQuery = np.asarray(anEstimate[3]).reshape(numberGridCells_LONG, numberGridCells_LAT)

    zippedEstimateData = zip(lat_list, lng_list, estimates_list, variability)

    # theEstimates = []
    theEstimates = {}
    # location = {}
    for i, aZippedEstimate in enumerate(zippedEstimateData):
        header = ('lat', 'long', 'pm25', 'variability')
        theEstimate = dict(zip(header, aZippedEstimate))

        print('**** gridID ****')
        print(gridID)
        print('**** theCollection ****')
        print(theCollection)

        theEstimationMetadata = db.estimationMetadata.find_one({"gridID": int(gridID), "metadataType": theCollection})
        print(theEstimationMetadata)

        if theEstimationMetadata is not None:

            for key, value in theEstimationMetadata['transformedGrid'].iteritems():
                print("****** value['lat'] and theEstimate['lat'] ******")
                print(value['lat'])
                print(theEstimate['lat'])

                print("****** value['lngs'] and theEstimate['long'] ******")
                print(value['lngs'])
                print(theEstimate['long'])
                
                if value['lat'] == theEstimate['lat'] and value['lngs'] == theEstimate['long']:
                    print('found a match')

                    # location[str(i)] = {'lat': theEstimate['lat'], 'long': theEstimate['long']}
                    theEstimates[str(i)] = {'gridELementID': key, 'pm25': theEstimate['pm25'], 'variability': theEstimate['variability']}
        else:
            print('Did not find the appropriate estimation metadata.')

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

        if theCollection == 'timeSlicedEstimates_high':
            db.timeSlicedEstimates_high.insert_one(anEstimateSlice)

        logger.info('inserted data slice for %s', currentUTCtime_str)
    else:
        # low variability estimation

        if theCollection == 'timeSlicedEstimates_low':
            db.timeSlicedEstimates_low.insert_one(anEstimateSlice)

            oldestEstimation = db.timeSlicedEstimates_high.find().sort("estimationFor", 1).limit(1)
            print('******* oldestEstimation *****')
            print(oldestEstimation)
            for document in oldestEstimation:
                documentID = document.get('_id')
                timeDifference = datetime.strptime(queryTime, '%Y-%m-%dT%H:%M:%SZ') - datetime.strptime(document['estimationFor'], '%Y-%m-%dT%H:%M:%SZ')
                print('******* timeDifference *****')
                print(timeDifference)
                print(timeDifference.total_seconds() / (60 * 60))

                if (timeDifference.total_seconds() / (60 * 60)) >= characteristicTimeLength:
                    db.timeSlicedEstimates_high.delete_one({"_id": documentID})
                    print('********* removed *******')
                    print(document['estimationFor'])

        logger.info('inserted data slice for %s', currentUTCtime)


def storeGridMetadata(client, gridID, metadataType, numberGridCells_LAT, numberGridCells_LONG, theMesh):

    # transform theMesh which looks like this {'lats': lats, 'lngs': lngs, 'times': times} to {0: {"lat": lats[0], "lngs": lngs[0], "times": times[0]}, ...}
    transformedMesh = {}
    numberofElementsInMesh = len(theMesh['lats'])
    for i in range(numberofElementsInMesh):
        transformedMesh[str(i)] = {"lat": theMesh['lats'][i], "lngs": theMesh['lngs'][i], "times": theMesh['times'][i]}

    aMetadataElement = {"gridID": int(gridID),
                        "metadataType": metadataType,
                        "numberOfElementsInMesh": numberofElementsInMesh,
                        "grid": theMesh,
                        "transformedGrid": transformedMesh,
                        "numberOfGridCells": {'lat': numberGridCells_LAT, 'long': numberGridCells_LONG}}

    db = client.airudb
    db.estimationMetadata.insert_one(aMetadataElement)

    logger.info('inserted estimation Metadata %s', gridID)


if __name__ == '__main__':

    # true means only now()-characteristicLength; false means now() to now()-characteristicLength and to now()-2*characteristicLength
    nowMinusCHLT = bool(strtobool(sys.argv[1]))
    theGridID = 0

    numberGridCells_LAT = None
    numberGridCells_LONG = None

    if nowMinusCHLT:
        startDate = currentUTCtime - timedelta(hours=characteristicTimeLength)
        endDate = currentUTCtime
        queryTime = endDate
        collection = 'timeSlicedEstimates_high'
    else:
        startDate = currentUTCtime - timedelta(hours=(2 * characteristicTimeLength))
        endDate = currentUTCtime
        queryTime = endDate - timedelta(hours=characteristicTimeLength)
        collection = 'timeSlicedEstimates_low'

    # the relative time is always with respect to the start time
    queryTimeRelative = datetime2Reltime([queryTime], startDate)
    # print(queryTimeRelative)

    # python modeling/calculateEstimates.py gridCellsLat gridCellsLong startDate endDate
    # python modeling/calculateEstimates.py 10 16 %Y-%m-%dT%H:%M:%SZ %Y-%m-%dT%H:%M:%SZ
    if len(sys.argv) > 2:
        numberGridCells_LAT = sys.argv[2]
        numberGridCells_LONG = sys.argv[3]
        startDate = datetime.strptime(sys.argv[4], '%Y-%m-%dT%H:%M:%SZ')
        endDate = datetime.strptime(sys.argv[5], '%Y-%m-%dT%H:%M:%SZ')
    # else:
    #     numberGridCells_LAT = 10
    #     numberGridCells_LONG = 16
        # startDate = datetime(2018, 1, 7, 0, 0, 0)
        # endDate = datetime(2018, 1, 11, 0, 0, 0)

    # geographical area
    bottomLeftCorner = {'lat': 40.598850, 'lng': -112.001349}
    topRightCorner = {'lat': 40.810476, 'lng': -111.713403}

    config = getConfig()

    mongodb_url = 'mongodb://{user}:{password}@{host}:{port}/{database}'.format(
        user=config['MONGO_USER'],
        password=config['MONGO_PASSWORD'],
        host=config['MONGO_HOST'],
        port=config['MONGO_PORT'],
        database=config['MONGO_DATABASE'])

    mongoClient = MongoClient(mongodb_url)
    db = mongoClient.airudb
    meshgridInfo = db.estimationMetadata.find_one({"metadataType": collection})

    print(meshgridInfo)

    if meshgridInfo is None:

        if numberGridCells_LAT is None and numberGridCells_LONG is None:
            numberGridCells_LAT = 10
            numberGridCells_LONG = 16
        else:
            logger.info('problem with numberGridCells_LAT andnumberGridCells_LONG, one of them is not None')

        mesh = generateQueryMeshVariableGrid(numberGridCells_LAT, numberGridCells_LONG, bottomLeftCorner, topRightCorner, queryTimeRelative)

        # theGridID = 0
        storeGridMetadata(mongoClient, 0, collection, int(numberGridCells_LAT), int(numberGridCells_LONG), mesh)
    else:
        mesh = meshgridInfo['grid']
        numberGridCells_LAT = meshgridInfo['numberOfGridCells']['lat']
        numberGridCells_LONG = meshgridInfo['numberOfGridCells']['long']

    levels = [0.0, 12.0, 35.4, 55.4, 150.4, 250.4]
    colorBands = ('#a6d96a', '#ffffbf', '#fdae61', '#d7191c', '#bd0026', '#a63603')

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

    theEstimate = getEstimate(pAirClient, airUClient, dbs, nowMinusCHLT, mesh, startDate, endDate)

    queryTimeString = queryTime.strftime('%Y-%m-%dT%H:%M:%SZ')
    storeInMongo(mongoClient, collection, theEstimate, queryTimeString, levels, colorBands, nowMinusCHLT, numberGridCells_LAT, numberGridCells_LONG, theGridID)

    logger.info('new sensor check successful for ' + queryTimeString)
