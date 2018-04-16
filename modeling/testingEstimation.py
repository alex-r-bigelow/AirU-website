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
# from bson.binary import Binary
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
    localTimezone = pytz.timezone('MST7MDT')
    UTCTimezone = pytz.timezone('UTC')
    local_dt = localTimezone.localize(aTime_dt, is_dst=None)  # now local time on server is MST, add that information to the time
    # local_dt = localTimezone.localize(datetime.strptime(aTimeString, '%Y-%m-%dT%H:%M:%SZ'), is_dst=None)  # now local time on server is MST, add that information to the time
    utc_dt = local_dt.astimezone(UTCTimezone)
    # utc_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    return utc_dt


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


def getEstimate(purpleAirClient, airuClient, theDBs, nowMinusCHLT, numberOfLat, numberOfLong, start, end, queryTimeRel):
    # numberOfGridCells1D = 20

    numberGridCells_LAT = numberOfLat
    numberGridCells_LONG = numberOfLong

    startDate = start
    endDate = end

    # startDate = currentUTCtime - timedelta(days=1)
    # endDate = currentUTCtime

    # startDate = getUTCTime(start)
    # endDate = getUTCTime(end)

    # topleftCorner = {'lat': 40.810476, 'lng': -112.001349}
    # bottomRightCorner = {'lat': 40.598850, 'lng': -111.713403}

    bottomLeftCorner = {'lat': 40.598850, 'lng': -112.001349}
    topRightCorner = {'lat': 40.810476, 'lng': -111.713403}
# TODO is the binnfrequency the way to get the 3 to 6 points?
    data_tr = AQDataQuery(purpleAirClient, airuClient, theDBs, startDate, endDate, 3600 * 6, topRightCorner['lat'], bottomLeftCorner['lng'], bottomLeftCorner['lat'], topRightCorner['lng'])

    # print(data_tr)

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

    print('***** lat_tr *****')
    print(lat_tr)

    print('***** long_tr *****')
    print(long_tr)

    # meshInfo = generateQueryMeshGrid(numberOfGridCells1D, topleftCorner, bottomRightCorner)
    meshInfo = generateQueryMeshVariableGrid(numberGridCells_LAT, numberGridCells_LONG, bottomLeftCorner, topRightCorner, queryTimeRel)

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

    return [yPred, yVar, x_Q[:, 0], x_Q[:, 1], numberGridCells_LAT, numberGridCells_LONG]


def calculateContours(X, Y, Z, endDate, levels, colorBands):

    # from: http://hplgit.github.io/web4sciapps/doc/pub/._part0013_web4sa_plain.html
    stringFile = StringIO()

    outputdirectory = '/home/airu/AirU-website/svgs_testing'
    anSVGfile = os.path.join(outputdirectory, endDate + '.svg')

    plt.figure()
    plt.axis('off')  # Removes axes
    plt.gca().set_position([0, 0, 1, 1])
    # plt.axes().set_frame_on(False)
    plt.axes().patch.set_visible(False)
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

    plt.savefig(stringFile, format="svg")
    theSVG = stringFile.getvalue()
    print('***** theSVG *******')
    print(theSVG)

    print('***** theContours.collections *******')
    print(theContours.collections)

    # to save as svg file in directory svgs
    plt.savefig(anSVGfile, format="svg")

    # plt.colorbar(theContours)  # This will give you a legend

    new_contours = []

    for i, collection in enumerate(theContours.collections):
        # print(collection)
        for path in collection.get_paths():
            print('***** path *******')
            print(path)
            coords = path.vertices
            # print(coords)
            # print(path.codes)
            new_contour = {}
            new_contour['path'] = []
            new_contour['level'] = i
            new_contour['k'] = i

            # prev_coords = None
            for (coords, code_type) in zip(path.vertices, path.codes):

                # '''
                # if prev_coords is not None and np.allclose(coords, prev_coords):
                #     continue
                # '''

                # prev_coords = coords

                # print >>sys.stderr, "coords, code_type:", coords, code_type, i

                if code_type == 1:
                    new_contour['path'] += [['M', float('{:.3f}'.format(coords[0])), float('{:.3f}'.format(coords[1]))]]
                elif code_type == 2:
                    new_contour['path'] += [['L', float('{:.3f}'.format(coords[0])), float('{:.3f}'.format(coords[1]))]]

            new_contours += [new_contour]

    return new_contours

    # saving the svg part
    # plt.axis('off')  # Removes axes
    # plt.savefig(stringFile, format="svg")
    # theSVG = stringFile.getvalue()
    # # theSVG = '<svg' + theSVG.split('<svg')[1]
    #
    # print(type(theSVG))
    # encodedString = theSVG.decode('utf8')
    # print(type(encodedString))
    #
    # encodedString = encodedString.encode('utf8')
    # print(type(encodedString))
    #
    # binaryFile = Binary(encodedString)
    # binaryFile = bson.BSON.encode({'svg': binaryFile})
    #
    # stringFile.close()
    #
    # return binaryFile


def storeInMongo(client, anEstimate, queryTime, levels, colorBands, theNowMinusCHLT):

    # db = client.airudb

    anEstimate[0] = [0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0,0,0,0, 0,0,5,5,5,5,0,0,0,0, 0,0,5,5,5,5,0,0,0,0,0, 0,0,5,5,5,5,0,0,0,0,0, 0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0,0,0,0]

    print('***** anEstimate[0] *******')
    print(anEstimate[0])
    print('***** anEstimate[3] - longs *******')
    print(anEstimate[3])

    # flatten the matrices to list
    estimates_list = np.squeeze(np.asarray(anEstimate[0])).tolist()
    variability = np.squeeze(np.asarray(anEstimate[1])).tolist()
    lat_list = np.squeeze(np.asarray(anEstimate[2])).tolist()
    lng_list = np.squeeze(np.asarray(anEstimate[3])).tolist()

    # make numpy arrays for the contours
    pmEstimates = np.asarray(anEstimate[0]).reshape(anEstimate[4], anEstimate[5])
    latQuery = np.asarray(anEstimate[2]).reshape(anEstimate[4], anEstimate[5])
    longQuery = np.asarray(anEstimate[3]).reshape(anEstimate[4], anEstimate[5])

    print('***** latQuery *****')
    print(latQuery)
    print('***** longQuery *****')
    print(longQuery)

    zippedEstimateData = zip(lat_list, lng_list, estimates_list, variability)

    # theEstimates = []
    theEstimates = {}
    location = {}
    for i, aZippedEstimate in enumerate(zippedEstimateData):
        header = ('lat', 'long', 'pm25', 'variability')
        theEstimate = dict(zip(header, aZippedEstimate))

        location[str(i)] = {'lat': theEstimate['lat'], 'long': theEstimate['long']}

        # theEstimates.append(theEstimate)
        theEstimates[str(i)] = {'pm25': theEstimate['pm25'], 'variability': theEstimate['variability']}

    # take the estimates and get the contours
    # binaryFile = calculateContours(latQuery, longQuery, pmEstimates)
    contours = calculateContours(latQuery, longQuery, pmEstimates, queryTime, levels, colorBands)

    print('***** contours ******')
    print(contours)

    # save the contour svg serialized in the db.

    # if theNowMinusCHLT:
    #     anEstimateSlice = {"estimationFor": currentUTCtime,
    #                        "modelVersion": '1.0.0',
    #                        "numberOfGridCells_LAT": anEstimate[4],
    #                        "numberOfGridCells_LONG": anEstimate[5],
    #                        "estimate": theEstimates,
    #                        "location": location,
    #                        # "svgBinary": binaryFile}
    #                        "contours": contours}
    #
    #     db.timeSlicedEstimates.insert_one(anEstimateSlice)
    #     logger.info('inserted data slice for %s', currentUTCtime_str)
    # else:
    #     # TODO: have two tables, table1 push the estimates for point now()-characteristic length time
    #     # before pushing remove oldest element from
    #     # table2 push estimates for point now(), before
    #     print('nothing there yet')


if __name__ == '__main__':

    dateStart = datetime(2018, 3, 7, 00, 00, 00)
    dateEnd = datetime(2018, 3, 10, 00, 00, 00)

    startDate_UTC = getUTCTime(dateStart)
    endDate_UTC = getUTCTime(dateEnd)

    aDate = startDate_UTC
    dates = [startDate_UTC]
    while aDate < endDate_UTC:
        aNewDate = aDate + timedelta(hours=1)
        dates.append(aNewDate)

        aDate = aNewDate

    for someDate in dates:
        startDate = someDate - timedelta(hours=characteristicTimeLength)
        endDate = someDate + timedelta(hours=characteristicTimeLength)
        queryTime = someDate
        queryTimeRelative = datetime2Reltime([queryTime], startDate)

        print(startDate, endDate, queryTime, queryTimeRelative)

        numberGridCells_LAT = 10
        numberGridCells_LONG = 16

        levels = [0.0, 12.0, 35.4, 55.4, 150.4, 250.4]
        colorBands = ('#a6d96a', '#ffffbf', '#fdae61', '#d7191c', '#bd0026', '#a63603')

        print(numberGridCells_LAT)
        # print(startDate)
        # print(endDate)

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

        theEstimate = getEstimate(pAirClient, airUClient, dbs, False, int(numberGridCells_LAT), int(numberGridCells_LONG), startDate, endDate, queryTimeRelative)

        mongodb_url = 'mongodb://{user}:{password}@{host}:{port}/{database}'.format(
            user=config['MONGO_USER'],
            password=config['MONGO_PASSWORD'],
            host=config['MONGO_HOST'],
            port=config['MONGO_PORT'],
            database=config['MONGO_DATABASE'])

        mongoClient = MongoClient(mongodb_url)
        queryTimeString = queryTime.strftime('%Y-%m-%dT%H:%M:%SZ')
        storeInMongo(mongoClient, theEstimate, queryTimeString, levels, colorBands, False)

        logger.info('new sensor check successful for ' + queryTimeString)
