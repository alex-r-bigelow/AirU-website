import json
import logging
import logging.handlers as handlers
import sys

# from datetime import datetime
from influxdb import InfluxDBClient
from pymongo import MongoClient


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

logHandler = handlers.TimedRotatingFileHandler('sensorMonitoring.log', when='D', interval=1, backupCount=3)
logHandler.setLevel(logging.INFO)
logHandler.setFormatter(formatter)
LOGGER.addHandler(logHandler)


def getConfig():
    with open(sys.path[0] + '/../config/config.json', 'r') as configfile:
        return json.loads(configfile.read())
    LOGGER.info('ConfigError\tProblem reading config file.')
    sys.exit(1)


def getEmail():
    mongodb_url = 'mongodb://{user}:{password}@{host}:{port}/{database}'.format(
        user=config['MONGO_USER'],
        password=config['MONGO_PASSWORD'],
        host=config['MONGO_HOST'],
        port=config['MONGO_PORT'],
        database=config['MONGO_DATABASE'])

    mongoClient = MongoClient(mongodb_url)
    db = mongoClient.airudb

    emails = {}

    for aHolder in db.airUSensorHolder.find():
        name = aHolder['name']
        email = aHolder['email']

        emails[name] = {'email': email}

    return emails


def getMACToCheck(partOfSchoolProject):
    mongodb_url = 'mongodb://{user}:{password}@{host}:{port}/{database}'.format(
        user=config['MONGO_USER'],
        password=config['MONGO_PASSWORD'],
        host=config['MONGO_HOST'],
        port=config['MONGO_PORT'],
        database=config['MONGO_DATABASE'])

    mongoClient = MongoClient(mongodb_url)
    db = mongoClient.airudb

    macs = {}

    for aSensor in db.macToCustomSensorID.find():
        theMAC = ''.join(aSensor['macAddress'].split(':'))
        sensorHolder = aSensor['sensorHolder']

        if partOfSchoolProject:
            if aSensor['schoolProject']:
                macs[theMAC] = {'sensorHolder': sensorHolder}
        else:
            if not aSensor['schoolProject']:
                macs[theMAC] = {'sensorHolder': sensorHolder}

        LOGGER.info(theMAC)
        LOGGER.info(sensorHolder)

    LOGGER.info('getMAC is done')

    return macs


def runMonitoring(config, timeFrame, isSchool, borderBox, pAirClient, airUClient):

    macs = getMACToCheck(isSchool)
    emails = getEmail()

    LOGGER.info("Time frame: last " + str(timeFrame) + " seconds")
    LOGGER.info("Geographic area [top left bottom right]: [" + str(borderBox['top']) + ", " + str(borderBox['left']) + ", " + str(borderBox['bottom']) + ", " + str(borderBox['right']) + "]")

    LOGGER.info('the macs')
    LOGGER.info(macs)

    tmpIDs = []
    for mac, sensorHolder in macs.items():
        if mac not in tmpIDs:
            tmpIDs += [mac]

    # Querying the coordinates and model of each sensor in the queried geographic area
    airUUniqueIDs = []
    airULatitudes = []
    airULongitudes = []
    airUSensorModels = []

    # Printing the status of the sensors in the required box
    theMessage = ''
    theMessage = theMessage + '            \t             \t          \t          \t             \t        Query Status         \t             \n'
    theMessage = theMessage + 'ID          \tSensor Holder\temail     \tLatitude   \tLongitude    \toffline/failure/online (total)\tLatest Status \n'
    theMessage = theMessage + '------------\t-------------\t-----------\t-----------\t------------\t------------------------------\t--------------\n'

    for anID in tmpIDs:
        # last = airUClient.query('SELECT LAST(Latitude),"SensorModel" FROM ' +
        #                         config['INFLUX_AIRU_LATITUDE_MEASUREMENT'] + ' WHERE ID=\'' + anID + '\' AND time >= now()-' + str(timeFrame) + 's;')
        last = airUClient.query('SELECT LAST(Latitude),"SensorModel" FROM ' +
                                config['INFLUX_AIRU_LATITUDE_MEASUREMENT'] + ' WHERE ID=\'' + anID + '\'')

        # get the email
        theEmail = 'unknown'
        if macs[anID]['sensorHolder'] in emails:
            theEmail = emails[macs[anID]['sensorHolder']]['email']

        if len(last) == 0:
            # LOGGER.info('never pushed data for ID: ' + anID + ' last Value: ' + last)

            theMessage = theMessage + '%-15s' % anID + '\t' \
                                    + '%-30s' % macs[anID]['sensorHolder'] + '\t' \
                                    + '%-40s' % theEmail + '\t' \
                                    + '%-13s' % 'unknown' + '\t' \
                                    + '%-13s' % 'unknown' + '\t'\
                                    + '%s' % 'unknown' + '\t' \
                                    + '%-10s' % 'OFFLINE' + '\t' \
                                    + '%-20s' % 'never been online' + '\n'
            continue

        last = list(last.get_points())[0]
        # LOGGER.info('ID: ' + anID + ' last Value: ' + last)

        senModel = last['SensorModel']
        lat = last['last']

        # last = airUClient.query('SELECT LAST(Longitude),"SensorModel" FROM ' +
        #                         config['INFLUX_AIRU_LONGITUDE_MEASUREMENT'] + ' WHERE ID=\'' + anID + '\' AND time >= now()-' + str(timeFrame) + 's;')
        last = airUClient.query('SELECT LAST(Longitude),"SensorModel" FROM ' +
                                config['INFLUX_AIRU_LONGITUDE_MEASUREMENT'] + ' WHERE ID=\'' + anID + '\'')
        last = list(last.get_points())[0]
        long = last['last']

#        if lat is None or long is None:
#            print ("Skipped sensor with ID:" + anID + " -> Latitude/Longitude information not available!")
#            continue
#        if lat==0 or long==0:
#            print ("Skipped sensor with ID:" + anID + " -> Latitude/Longitude has not been aquired!")
#            continue

        # if not((float(long) < borderBox['right']) and (float(long) > borderBox['left'])) or not((float(lat) > borderBox['bottom']) and (float(lat) < borderBox['top'])):
        #     continue

        airUUniqueIDs += [anID]
        if lat is None:
            airULatitudes += ['missing']
        elif lat == 0:
            airULatitudes += ['not aquired']
        else:
            airULatitudes += [lat]
        if long is None:
            airULongitudes += ['missing']
        elif long == 0:
            airULongitudes += ['not aquired']
        else:
            airULongitudes += [long]
        if senModel is None:
            airUSensorModels += ['missing']
        else:
            airUSensorModels += [senModel.split('+')[0]]

    for i, anID in enumerate(airUUniqueIDs):
        result = airUClient.query('SELECT "PM2.5" FROM ' +
                                  config['INFLUX_AIRU_PM25_MEASUREMENT'] + ' WHERE time >= now()-' +
                                  str(timeFrame) + 's AND ID = \'' + anID + '\';')
        # print(anID, list(result.get_points()))

        result = list(result.get_points())
        nFail = 0
        nOff = 0
        for t, res in enumerate(result):
            if res['PM2.5'] is None:
                nOff += 1
            elif res['PM2.5'] <= 0:
                nFail += 1
            elif t > 0 and res['PM2.5'] == result[t - 1]['PM2.5']:
                isFail = True
                revt = t - 2
                while (revt >= 0 and revt > t - 10):
                    if res['PM2.5'] != result[revt]['PM2.5']:
                        isFail = False
                        break
                    revt -= 1
                if isFail:
                    nFail += 1

        nTotal = len(result)
        nFine = nTotal - nFail - nOff
        status = ('OFFLINE' if (not result) else ('Failed' if res['PM2.5'] < 0 else 'Online'))

        theLastTimestamp = airUClient.query('SELECT LAST("PM2.5") FROM ' +
                                            config['INFLUX_AIRU_PM25_MEASUREMENT'] + ' WHERE ID=\'' + anID + '\'')

        timestamp = list(theLastTimestamp.get_points())
        # print(timestamp)

        theEmail = 'unknown'
        if macs[anID]['sensorHolder'] in emails:
            theEmail = emails[macs[anID]['sensorHolder']]['email']

        theMessage = theMessage + '%-15s' % anID + '\t' \
                                + '%-30s' % macs[anID]['sensorHolder'] + '\t' \
                                + '%-40s' % theEmail + '\t' \
                                + '%-13s' % airULatitudes[i] + '\t' \
                                + '%-13s' % airULongitudes[i] + '\t' \
                                + '{}/{}/{}({})'.format(str(nOff), str(nFail), str(nFine), str(nTotal)) + '\t' \
                                + '%-10s' % status + '\t' \
                                + '%-20s' % timestamp[0]['time'].split('.')[0] + '\n'

    # for i, anID in enumerate(pAirUniqueIDs):
    #     result = pAirClient.query('SELECT "pm2.5 (ug/m^3)" FROM airQuality WHERE "Sensor Source" = \'Purple Air\' AND time >= now()-' +
    #                               str(timeFrame) + 's AND ID = \'' + anID + '\';')
    #     result = list(result.get_points())
    #     nFail = 0
    #     nOff = 0
    #     for res in result:
    #         if res['pm2.5 (ug/m^3)'] is None:
    #             nOff += 1
    #         elif res['pm2.5 (ug/m^3)'] <= 0:
    #             nFail += 1
    #     nTotal = len(result)
    #     nFine = nTotal - nFail - nOff
    #     status = ('Offline' if (res['pm2.5 (ug/m^3)'] is None) else ('Failed' if res['pm2.5 (ug/m^3)'] <= 0 else 'Online'))
    #     theMessage = theMessage + '%-12s' % anID + '\t' + '%-12s' % pAirSensorModels[i] + '\t' + '%-11s' % pAirLatitudes[i] + '\t' \
    #                             + '%-13s' % pAirLongitudes[i] \
    #                             + '\t' + format(str(nOff) + '/' + str(nFail) + '/' + str(nFine) + ' (' + str(nTotal) + ')', '^30') + '\t' + status + '\n'

    # theMessage = theMessage + emailFooter
    # print(theMessage)

    return theMessage


if __name__ == "__main__":

    # Default arguments
    # startDate = '2018-01-01T00:00:00Z'
    # startDate = datetime.strptime(startDate, '%Y-%m-%dT%H:%M:%SZ')
    # now = datetime.now()
    #
    # diffInSec = round((now - startDate).total_seconds())

    # timeFrame = int(diffInSec)  # needs to be in seconds
    timeFrame = 3600  # needs to be in seconds
    LOGGER.info('timeFrame: %d', timeFrame)

    isSchool = False              # Query the status of all the sensors
    if sys.argv[1] == 'school':
        isSchool = True

    LOGGER.info('isSchool: ' + str(isSchool))

    borderBox = {'bottom': 36.9979667663574,
                 'top': 42.0013885498047,
                 'left': -114.053932189941,
                 'right': -109.041069030762}    # Utah border coordinates

    # Reading the config file
    config = getConfig()

    # Purple Air client
    pAirClient = InfluxDBClient(config['INFLUX_HOST'],
                                config['INFLUX_PORT'],
                                config['INFLUX_MONITORING_USERNAME'],
                                config['INFLUX_MONITORING_PASSWORD'],
                                config['PURPLE_AIR_DB'],
                                ssl=True,
                                verify_ssl=True)

    # airU client
    airUClient = InfluxDBClient(config['INFLUX_HOST'],
                                config['INFLUX_PORT'],
                                config['INFLUX_MONITORING_USERNAME'],
                                config['INFLUX_MONITORING_PASSWORD'],
                                config['AIRU_DB'],
                                ssl=True,
                                verify_ssl=True)

    theRun = runMonitoring(config, timeFrame, isSchool, borderBox, pAirClient, airUClient)
    print(theRun)
