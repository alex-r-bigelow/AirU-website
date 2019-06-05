import json
import logging
import logging.handlers as handlers
# import pytz
import requests
import sys
import time

from datetime import datetime
from influxdb.exceptions import InfluxDBClientError, InfluxDBServerError
from influxdb import InfluxDBClient

from requests.adapters import HTTPAdapter
from requests.exceptions import ConnectionError, HTTPError, Timeout, TooManyRedirects, RequestException
from requests.packages.urllib3.util.retry import Retry


TIMESTAMP = datetime.now().isoformat()

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - [%(funcName)s:%(lineno)d] - %(levelname)s - %(message)s')

logHandler = handlers.RotatingFileHandler('purpleAirPoller.log', maxBytes=5000000, backupCount=5)
logHandler.setLevel(logging.INFO)
logHandler.setFormatter(formatter)
LOGGER.addHandler(logHandler)

dateStringParserFormat = '%Y-%m-%dT%H:%M:%SZ'

numberOfDataPointsToDownload = 10


def getConfig():
    with open(sys.path[0] + '/../config/config.json', 'r') as configfile:
        return json.loads(configfile.read())
    sys.stderr.write('%s\tConfigError\tProblem reading config file.\n' % TIMESTAMP)
    sys.exit(1)

# info about PurpleAir Channel A and Channel B: https://docs.google.com/document/d/15ijz94dXJ-YAZLi9iZ_RaBwrZ4KtYeCy08goGBwnbCU/edit

# Channel A (ParentID==None) will be stored in influxdb with PM2.5, temperature and humidity
# Channel B (ParentID!=None) will be stored in influxdb with only PM2.5, but not temperature and not humidity


# the fields are always the same, therefore hardcoded them,
# according to Adrian Dybwad
PURPLE_AIR_FIELDS_PRI_FEED_CHANNEL_A = {
    'Humidity (%)': 'field7',
    'Temp (*C)': 'field6',   # this gets converted specifically in the function
    'pm2.5 (ug/m^3)': 'field8',     # 'PM2.5 (CF=1)',
}

PURPLE_AIR_FIELDS_PRI_FEED_CHANNEL_B = {
    'pm2.5 (ug/m^3)': 'field8',     # 'PM2.5 (CF=1)',
}

PURPLE_AIR_FIELDS_SEC_FEED = {
    'pm1.0 (ug/m^3)': 'field7',     # 'PM1.0 (CF=1)',
    'pm10.0 (ug/m^3)': 'field8',    # 'PM10.0 (CF=1)',
}

PURPLE_AIR_TAGS = {
    'ID': 'ID',
    'Sensor Model': 'Type',
    'Sensor Version': 'Version',
    'Latitude': 'Lat',
    'Longitude': 'Lon',
    # 'Altitude (m)': 'elevation'
    'Start': 'created_at'
}


def isSensorValid(aStation):

    # inside/outside check
    if aStation.get('DEVICE_LOCATIONTYPE') == 'inside':
        # LOGGER.info('Sensor is located inside, dont store it\'s data')
        return False

    # checks if sensor is in Utah
    # simplified bbox from: https://gist.github.com/mishari/5ecfccd219925c04ac32
    utahBbox = {
        'left': 36.9979667663574,
        'right': 42.0013885498047,
        'bottom': -114.053932189941,
        'top': -109.041069030762
    }

    # sensor needs an id
    if aStation.get('ID') is None:
        LOGGER.info('Sensor has no ID')
        return False

    # sensor needs primary ID and Key
    if aStation.get('THINGSPEAK_PRIMARY_ID') is None or aStation.get('THINGSPEAK_PRIMARY_ID_READ_KEY') is None:
        LOGGER.info('Sensor has None value(s) for primary Thingspeak id or key.')
        return False

    # sensor needs valid lat and long
    # lat = specifies north-south position
    # log = specifies east-west position
    if aStation.get('Lat') is None or aStation.get('Lon') is None:
        # LOGGER.info('latitude or longitude is None')
        return False

    if not((float(aStation['Lon']) < float(utahBbox['top'])) and (float(aStation['Lon']) > float(utahBbox['bottom']))) or not((float(aStation['Lat']) > float(utahBbox['left'])) and(float(aStation['Lat']) < float(utahBbox['right']))):
        # LOGGER.info('Not in Utah')
        return False

    return True


def requests_retry_session(retries=3, backoff_factor=0.3, status_forcelist=(500, 502, 503, 504), session=None):
    """ from here: https://www.peterbe.com/plog/best-practice-with-retries-with-requests """
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )

    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


def getTimeStamp(dateString):
    """ parse string to get a datetime object """

    result = None
    try:
        result = datetime.strptime(dateString, dateStringParserFormat)
    except ValueError as e:
        LOGGER.error('No start date. \t%s' % e, exc_info=True)
        return None

    return result


def isMeasurementNewerThanDBData(aMeasurement_unixTimestamp, aSensorID):

    if aMeasurement_unixTimestamp is None or aSensorID is None:
        return False

    try:
        lastPoint = client.query("""SELECT last("pm2.5 (ug/m^3)") FROM airQuality WHERE "ID" = '%s' AND "Sensor Source" = 'Purple Air'""" % aSensorID)
    except Exception as e:
        LOGGER.info('querying influxdb did not work: %s', e)
        return False

    if len(lastPoint) > 0:
        lastPoint = lastPoint.get_points().next()
        lastPointParsed = datetime.strptime(lastPoint['time'], '%Y-%m-%dT%H:%M:%SZ')
        lastPointUnixTimestamp = (lastPointParsed - datetime(1970, 1, 1)).total_seconds()

        if aMeasurement_unixTimestamp <= lastPointUnixTimestamp:
            return False

    return True

# def isMeasurementNewerThanDBData(aMeasurement):
#
#     try:
#         lastPoint = client.query("""SELECT last("pm2.5 (ug/m^3)") FROM airQuality WHERE "ID" = '%s' AND "Sensor Source" = 'Purple Air'""" % aMeasurement['tags']['ID'])
#     except Exception as e:
#         LOGGER.info('querying influxdb did not work: %s', e)
#         return False
#
#     if len(lastPoint) > 0:
#         lastPoint = lastPoint.get_points().next()
#
#         lastPointParsed = datetime.strptime(lastPoint['time'], dateStringParserFormat)
#         lastPointLocalized = pytz.utc.localize(lastPointParsed, is_dst=None)
#
#         if pytz.utc.localize(aMeasurement['time']) <= lastPointLocalized:
#             return False
#
#     return True


def getData(dataSource, aURL, theKeys, timeoutValue=5):

    try:
        theData = requests_retry_session().get(aURL, timeout=timeoutValue)
        theData.raise_for_status()
    except ConnectionError as e:
        LOGGER.error('ConnectionError: problem acquiring %s with %s;\t%s.' % dataSource, aURL, e, exc_info=True)
        return []
    except HTTPError as e:
        LOGGER.error('HTTPError: problem acquiring %s with %s;\t%s.' % dataSource, aURL, e, exc_info=True)
        return []
    except Timeout as e:
        LOGGER.error('Timeout: Problem acquiring %s with %s;\t%s.' % dataSource, aURL, e)
        return []
    except TooManyRedirects as e:
        LOGGER.error('TooManyRedirects: problem acquiring %s with %s;\t%s.' % dataSource, aURL, e)
        return []
    except RequestException as e:
        LOGGER.error('RequestException: problem acquiring %s with %s;\t%s.' % dataSource, aURL, e, exc_info=True)
        return []

    try:
        theData = theData.json()
    except Exception as e:
        LOGGER.error('JSON parsing error for %s with %s. \t%s' % dataSource, aURL, e, exc_info=True)
        return []

    result = {}
    for aKey in theKeys:
        try:
            result[aKey] = theData[aKey]
        except ValueError as e:
            LOGGER.error('Not able to decode the json object for %s with %s;\t%s.' % dataSource, aURL, e, exc_info=True)
            return []
        except KeyError as e:
            LOGGER.error('Key error for %s with %s;\t%s.' % dataSource, aURL, e, exc_info=True)
            return []

    return result


def getTagData(primaryDataChannel, aStation):

    tagData = {'Sensor Source': 'Purple Air'}

    # Attach the tags - values about the station that shouldn't
    start = getTimeStamp(primaryDataChannel['created_at'])
    if start is not None:
        tagData['Start'] = start

    # change across measurements
    for standardKey, purpleKey in PURPLE_AIR_TAGS.iteritems():
        tagValue = aStation.get(purpleKey)
        if tagValue is not None:
            tagData[standardKey] = tagValue

    # get the dual sensor 2nd sensor a Sensor Model instead of null
    if aStation.get('ParentID') is not None:
        tagData['Sensor Model'] = 'PMS5003'

    return tagData


def getSecondaryStreamData(secondaryID, secondaryKey):

    # purpleAirDataSecondaryFeed = []
    if secondaryID is not None and secondaryKey is not None:
        # secondary id and key are available

        secondaryPart1 = 'https://api.thingspeak.com/channels/'
        secondaryPart2 = '/feed.json?results=' + str(numberOfDataPointsToDownload) + '&api_key='

        querySecondaryFeed = secondaryPart1 + secondaryID + secondaryPart2 + secondaryKey

        purpleAirDataSecondary = getData('PurpleAir data from SECONDARY feed', querySecondaryFeed, ['feeds'])

        if purpleAirDataSecondary:
            return purpleAirDataSecondary['feeds']
        else:
            return []


def castToFloat(aPoint_fields):
    # influx field values cannot be None

    # if pm25 is None no need to store data point
    tmpPM25 = aPoint_fields.get('pm2.5 (ug/m^3)')
    if tmpPM25 is None:
        return None

    castedToFloat = {}

    for key, value in aPoint_fields.iteritems():
        try:
            castedToFloat[key] = float(value)
        except (ValueError, TypeError):
            pass    # skip that key/value pair

    # Convert the purple air deg F to deg C
    tempVal = castedToFloat.get('Temp (*C)')
    if tempVal is not None:
        castedToFloat['Temp (*C)'] = (tempVal - 32) * 5 / 9

    return castedToFloat


def storePoints(client, anID, pointsToStore):
    try:
        LOGGER.info('worked')
        client.write_points(pointsToStore)
        LOGGER.info('%s data points for ID= %s stored' % (str(len(pointsToStore)), str(anID)))
    except InfluxDBClientError as e:
        LOGGER.error('InfluxDBClientError\tWriting Purple Air data to influxdb lead to a write error.')
        LOGGER.error('%s.' % e)
        return False
    except InfluxDBServerError as e:
        LOGGER.error('InfluxDBServerError\tAn error when writing occured. There is an issue with the server.')
        LOGGER.error('%s.' % e)
        return False

    return True


# new values are generated every 8sec by purple air
def uploadPurpleAirData(client):

    startScript = time.time()

    purpleAirData = getData('Purple Air data', 'https://map.purpleair.org/json', ['results'])
    if not purpleAirData:
        # if no data break out of function
        return
    else:
        purpleAirData = purpleAirData['results']

    # go through all the stations
    for station in purpleAirData:

        if not isSensorValid(station):
            continue

        sensorLastSeen = station.get('LastSeen')
        sensorID = station.get('ID')
        if not isMeasurementNewerThanDBData(sensorLastSeen, sensorID):
            # sensor was last seen before or same as latest DB measurement
            LOGGER.info('station skipped: no new measurement for %s' % sensorID)
            continue

        # to get pm2.5, humidity and temperature Thingspeak primary feed
        # we know primary ID and Key exist, therefore not using .get()
        primaryID = station['THINGSPEAK_PRIMARY_ID']
        primaryIDReadKey = station['THINGSPEAK_PRIMARY_ID_READ_KEY']

        # because we poll every 5min, and purple Air has a new value roughly every 1min 10sec, to be safe take the last 10 results
        primaryPart1 = 'https://api.thingspeak.com/channels/'
        primaryPart2 = '/feed.json?results=' + str(numberOfDataPointsToDownload) + '&api_key='
        queryPrimaryFeed = primaryPart1 + primaryID + primaryPart2 + primaryIDReadKey

        purpleAirDataPrimary = getData('PurpleAir data from the PRIMARY feed', queryPrimaryFeed, ['channel', 'feeds'])

        if not purpleAirDataPrimary:
            purpleAirDataPrimaryChannel = purpleAirDataPrimary['channel']
            purpleAirDataPrimaryFeed = purpleAirDataPrimary['feeds']
        else:
            continue

        # Attach the tags - values about the station that shouldn't change
        tagDataForPoint = getTagData(purpleAirDataPrimaryChannel, station)

        # getting thingspeak secondary feed data: PM1 and PM10
        secondaryID = station.get('THINGSPEAK_SECONDARY_ID')
        secondaryIDReadKey = station.get('THINGSPEAK_SECONDARY_ID_READ_KEY')

        purpleAirDataSecondaryFeed = getSecondaryStreamData(secondaryID, secondaryIDReadKey)

        pointsToStore = []

        # go through the primary feed data
        for idx, aMeasurement in enumerate(purpleAirDataPrimaryFeed):

            point = {
                'measurement': 'airQuality',
                'fields': {},
                'tags': tagDataForPoint
            }

            timePrimary = getTimeStamp(aMeasurement['created_at'])
            if timePrimary is None:
                # don't include the point if we can't parse the timestamp
                continue

            # use the primary feed's time as the measuremnts time
            point['time'] = timePrimary

            # deal first with secondary feed
            if purpleAirDataSecondaryFeed:
                # if not empty take the data
                # go through the second feed's fields
                for standardKey, purpleKey in PURPLE_AIR_FIELDS_SEC_FEED.iteritems():
                    aSecondaryFeedMeasurement = purpleAirDataSecondaryFeed[idx]
                    if purpleKey in aSecondaryFeedMeasurement.keys():
                        point['fields'][standardKey] = aSecondaryFeedMeasurement[purpleKey]

            # go through the primary feed's fields
            for standardKey, purpleKey in PURPLE_AIR_FIELDS_PRI_FEED_CHANNEL_A.iteritems():

                # if parentID == null then we have channel A --> field6=temp and field7=Humidity
                # if parentID != null then we have channel B --> field6!=temp and field7!=Humidity --> do not take field6/7
                if purpleKey in aMeasurement.keys():
                    if station.get('ParentID') is None and purpleKey in PURPLE_AIR_FIELDS_PRI_FEED_CHANNEL_A.values():
                        # Channel A
                        point['fields'][standardKey] = aMeasurement[purpleKey]
                    elif station.get('ParentID') is not None and purpleKey in PURPLE_AIR_FIELDS_PRI_FEED_CHANNEL_B.values():
                        # Channel B
                        point['fields'][standardKey] = aMeasurement[purpleKey]

            # Only include the point if we haven't stored this measurement before
            time_unixtimestamp = (point['time'] - datetime(1970, 1, 1)).total_seconds()
            if not isMeasurementNewerThanDBData(time_unixtimestamp, point['tags']['ID']):
                LOGGER.info('measurement skipped: measurement is older %s' % point['tags']['ID'])
                continue

            castedFields = castToFloat(point['fields'])
            if castedFields is not None:
                point['fields'] = castedFields
            else:
                LOGGER.info('a None field value for PM25, for sensor %s' % point['tags']['ID'])
                continue

            pointsToStore.append(point)

        if storePoints(client, point['tags']['ID'], pointsToStore):
            LOGGER.info('PURPLE AIR Polling successful.')
        else:
            continue

    endScript = time.time()
    LOGGER.info("*********** total time for script: %s" % (endScript - startScript))


if __name__ == '__main__':
    config = getConfig()
    client = InfluxDBClient(
        'air.eng.utah.edu',
        8086,
        config['pollingUsername'],
        config['pollingPassword'],
        # 'defaultdb',
        'purpleAirScriptTester',
        ssl=True,
        verify_ssl=True
    )

    uploadPurpleAirData(client)

    LOGGER.info('Polling Purple Air done.')
    # sys.stdout.write('%s\tPolling successful.\n' % TIMESTAMP)
