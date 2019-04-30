import json
import logging
import logging.handlers as handlers
import pytz
import requests
import sys

from datetime import datetime
from influxdb.exceptions import InfluxDBClientError, InfluxDBServerError
from influxdb import InfluxDBClient


TIMESTAMP = datetime.now().isoformat()

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - [%(funcName)s:%(lineno)d] - %(levelname)s - %(message)s')

logHandler = handlers.RotatingFileHandler('purpleAirPoller.log', maxBytes=5000000, backupCount=5)
logHandler.setLevel(logging.INFO)
logHandler.setFormatter(formatter)
LOGGER.addHandler(logHandler)


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
PURPLE_AIR_FIELDS_PRI_FEED = {
    'Humidity (%)': 'field7',
    'Temp (*C)': 'field6',   # this gets converted specifically in the function
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


# new values are generated every 8sec by purple air
def uploadPurpleAirData(client):

    try:
        purpleAirData = requests.get("https://map.purpleair.org/json")
        purpleAirData.raise_for_status()
    except requests.exceptions.HTTPError as e:
        LOGGER.error('Problem acquiring PurpleAir data (https://map.purpleair.org/json);\t%s.' % e, exc_info=True)
        return []
    except requests.exceptions.Timeout as e:
        LOGGER.error('Problem acquiring PurpleAir data (https://map.purpleair.org/json);\t%s.' % e)
        return []
    except requests.exceptions.TooManyRedirects as e:
        LOGGER.error('Problem acquiring PurpleAir data (https://map.purpleair.org/json);\t%s.' % e)
        return []
    except requests.exceptions.RequestException as e:
        LOGGER.error('Problem acquiring PurpleAir data (https://map.purpleair.org/json);\t%s.' % e)
        return []

    try:
        purpleAirData = purpleAirData.json()
    except Exception, e:
        LOGGER.error('JSON parsing error. \t%s' % e, exc_info=True)
        return []

    try:
        purpleAirData = purpleAirData['results']
    except ValueError as e:
        LOGGER.error('Not able to decode the json object;\t%s.' % e, exc_info=True)
        return []

    # go through all the stations
    for station in purpleAirData:

        if station.get('DEVICE_LOCATIONTYPE') == 'inside':
            LOGGER.info('Sensor is located inside, dont store it\'s data')
            continue

        # simplified bbox from:
        # https://gist.github.com/mishari/5ecfccd219925c04ac32
        utahBbox = {
            'left': 36.9979667663574,
            'right': 42.0013885498047,
            'bottom': -114.053932189941,
            'top': -109.041069030762
        }

        # check if all the thingspeak ids are available, if not go to the next station
        if 'THINGSPEAK_PRIMARY_ID' not in station or 'THINGSPEAK_PRIMARY_ID_READ_KEY' not in station or 'THINGSPEAK_SECONDARY_ID' not in station or 'THINGSPEAK_SECONDARY_ID_READ_KEY' not in station:
            LOGGER.info('Sensor is missing one of the Thingspeak ids or keys.')
            continue

        # lat = specifies north-south position
        # log = specifies east-west position
        if station['Lat'] is None or station['Lon'] is None:
            # logging.info('latitude or longitude is None')
            continue

        if not((float(station['Lon']) < float(utahBbox['top'])) and (float(station['Lon']) > float(utahBbox['bottom']))) or not((float(station['Lat']) > float(utahBbox['left'])) and(float(station['Lat']) < float(utahBbox['right']))):
            # logging.info('Not in Utah')
            continue

        point = {
            'measurement': 'airQuality',
            'fields': {},
            'tags': {
                'Sensor Source': 'Purple Air'
            }
        }

        # to get pm2.5, humidity and temperature Thingspeak primary feed
        primaryID = station['THINGSPEAK_PRIMARY_ID']
        primaryIDReadKey = station['THINGSPEAK_PRIMARY_ID_READ_KEY']

        if primaryID is None or primaryIDReadKey is None:
            # if one of the two is missing pm value cannot be gathered
            # logging.info('primaryID or primaryIDReadKey is None')
            continue

        theID = str(station.get('ID'))
        # print(theID)

        # temp and humidity not gotten from thingspeak
        station.get('temp_f')

        station.get('humidity')

        # because we poll every 5min, and purple Air has a new value roughly every 1min 10sec, to be safe take the last 10 results
        primaryPart1 = 'https://api.thingspeak.com/channels/'
        primaryPart2 = '/feed.json?results=10&api_key='
        queryPrimaryFeed = primaryPart1 + primaryID + primaryPart2 + primaryIDReadKey

        try:
            purpleAirDataPrimary = requests.get(queryPrimaryFeed)
            purpleAirDataPrimary.raise_for_status()
        except requests.exceptions.HTTPError as e:
            LOGGER.error('Problem acquiring PurpleAir data from the PRIMARY feed, sensor ID: %s.\t%s.' % (theID, e))
            # sys.stderr.write('%s\tProblem acquiring PurpleAir data from the PRIMARY feed, sensor ID: %s.\t%s.\n' % (TIMESTAMP, theID, e))
            continue
        except requests.exceptions.Timeout as e:
            LOGGER.error('Problem acquiring PurpleAir data from the PRIMARY feed, sensor ID: %s.\t%s.' % (theID, e))
            # sys.stderr.write('%s\tProblem acquiring PurpleAir data from the PRIMARY feed, sensor ID: %s.\t%s.\n' % (TIMESTAMP, theID, e))
            continue
        except requests.exceptions.TooManyRedirects as e:
            LOGGER.error('Problem acquiring PurpleAir data from the PRIMARY feed, sensor ID: %s.\t%s.' % (theID, e))
            # sys.stderr.write('%s\tProblem acquiring PurpleAir data from the PRIMARY feed, sensor ID: %s.\t%s.\n' % (TIMESTAMP, theID, e))
            continue
        except requests.exceptions.RequestException as e:
            LOGGER.error('Problem acquiring PurpleAir data from the PRIMARY feed, sensor ID: %s.\t%s.' % (theID, e))
            # sys.stderr.write('%s\tProblem acquiring PurpleAir data from the PRIMARY feed, sensor ID: %s.\t%s.\n' % (TIMESTAMP, theID, e))
            continue

        purpleAirDataPrimaryChannel = purpleAirDataPrimary.json()['channel']
        purpleAirDataPrimaryFeed = purpleAirDataPrimary.json()['feeds']

        try:
            start = datetime.strptime(purpleAirDataPrimaryChannel['created_at'], '%Y-%m-%dT%H:%M:%SZ')
        except ValueError as e:
            # ok if we do not have that date, not crucial
            logging.error('No start date. \t%s' % e, exc_info=True)
            pass

        point['tags']['Start'] = start

        # getting thingspeak secondary feed data: PM1 and PM10
        secondaryID = station['THINGSPEAK_SECONDARY_ID']
        secondaryIDReadKey = station['THINGSPEAK_SECONDARY_ID_READ_KEY']

        if secondaryID is None or secondaryIDReadKey is None:
            # logging.info('secondary information is None')
            pass

        secondaryPart1 = 'https://api.thingspeak.com/channels/'
        secondaryPart2 = '/feed.json?results=10&api_key='

        querySecondaryFeed = secondaryPart1 + secondaryID + secondaryPart2 + secondaryIDReadKey

        try:
            purpleAirDataSecondary = requests.get(querySecondaryFeed)
            purpleAirDataSecondary.raise_for_status()
        except requests.exceptions.HTTPError as e:
            LOGGER.error('Problem acquiring PurpleAir data from the SECONDARY feed, sensor ID: %s.\t%s.' % (theID, e))
            # sys.stderr.write('%s\tProblem acquiring PurpleAir data from the SECONDARY feed, sensor ID: %s.\t%s.\n' % (TIMESTAMP, theID, e))
            continue
        except requests.exceptions.Timeout as e:
            LOGGER.error('Problem acquiring PurpleAir data from the SECONDARY feed, sensor ID: %s.\t%s.' % (theID, e))
            # sys.stderr.write('%s\tProblem acquiring PurpleAir data from the SECONDARY feed, sensor ID: %s.\t%s.\n' % (TIMESTAMP, theID, e))
            continue
        except requests.exceptions.TooManyRedirects as e:
            LOGGER.error('Problem acquiring PurpleAir data from the SECONDARY feed, sensor ID: %s.\t%s.' % (theID, e))
            # sys.stderr.write('%s\tProblem acquiring PurpleAir data from the SECONDARY feed, sensor ID: %s.\t%s.\n' % (TIMESTAMP, theID, e))
            continue
        except requests.exceptions.RequestException as e:
            LOGGER.error('Problem acquiring PurpleAir data from the SECONDARY feed, sensor ID: %s.\t%s.' % (theID, e))
            # sys.stderr.write('%s\tProblem acquiring PurpleAir data from the SECONDARY feed, sensor ID: %s.\t%s.\n' % (TIMESTAMP, theID, e))
            continue

        purpleAirDataSecondaryFeed = purpleAirDataSecondary.json()['feeds']
        if not purpleAirDataSecondaryFeed:
            continue

        # go through the primary feed data
        for idx, aMeasurement in enumerate(purpleAirDataPrimaryFeed):
            point['fields'] = {}

            try:
                timePrimary = datetime.strptime(aMeasurement['created_at'], '%Y-%m-%dT%H:%M:%SZ')
            except ValueError:
                # don't include the point if we can't parse the timestamp
                # logging.info("Coudn't parse the timestamp")
                continue

            # use the primary feed's time as the measuremnts time
            point['time'] = timePrimary
            # print point['time']

            LOGGER.debug('idx then aMeasurement')
            LOGGER.debug(idx)
            LOGGER.debug(aMeasurement)

            # go through the primary feed's fields
            for standardKey, purpleKey in PURPLE_AIR_FIELDS_PRI_FEED.iteritems():

                # if parentID = null then we have channel A --> field6=temp and field7=Humidity
                # if parentID != null then we have channel B --> field6!=temp and field7!=Humidity --> do not take field6/7
                if purpleKey in aMeasurement.keys():
                    if station.get('ParentID') is None and purpleKey in ['field6', 'field7', 'field8']:
                        # Channel A
                        point['fields'][standardKey] = aMeasurement[purpleKey]
                    elif station.get('ParentID') is not None and purpleKey in ['field8']:
                        # Channel B
                        point['fields'][standardKey] = aMeasurement[purpleKey]

            LOGGER.debug('purpleAirDataSecondaryFeed')
            LOGGER.debug(purpleAirDataSecondaryFeed)
            LOGGER.debug(purpleAirDataSecondaryFeed[idx])

            # go through the second feed's fields
            for standardKey, purpleKey in PURPLE_AIR_FIELDS_SEC_FEED.iteritems():
                if purpleKey in purpleAirDataSecondaryFeed[idx].keys():
                    point['fields'][standardKey] = purpleAirDataSecondaryFeed[idx][purpleKey]

            # Attach the tags - values about the station that shouldn't
            # change across measurements
            for standardKey, purpleKey in PURPLE_AIR_TAGS.iteritems():
                tagValue = station.get(purpleKey)
                if tagValue is not None:
                    point['tags'][standardKey] = tagValue

            idTag = point['tags'].get('ID')
            if idTag is None:
                # print 'ID is none'
                continue    # don't include the point if it doesn't have an ID

            # prefix the ID with "Purple Air " so that there aren't
            # collisions with other data sources
            point['tags']['ID'] = idTag
            # print point['tags']['ID']

            # get the dual sensor 2nd sensor a Sensor Model instead of null
            if station.get('ParentID') is not None:
                point['tags']['Sensor Model'] = 'PMS5003'

            # Only include the point if we haven't stored this measurement before
            lastPoint = client.query("""SELECT last("pm2.5 (ug/m^3)") FROM airQuality WHERE "ID" = '%s' AND "Sensor Source" = 'Purple Air'""" % point['tags']['ID'])
            # print "new POINT"
            # print pytz.utc.localize(point['time'])
            if len(lastPoint) > 0:
                lastPoint = lastPoint.get_points().next()
                # print parser.parse(lastPoint['time'], tzinfo=pytz.utc)
                # print point['time']
                # print lastPoint['time']
                lastPointParsed = datetime.strptime(lastPoint['time'], '%Y-%m-%dT%H:%M:%SZ')
                lastPointLocalized = pytz.utc.localize(lastPointParsed, is_dst=None)
                # print lastPointLocalized
                # if point['time'] <= parser.parse(lastPoint['time'], None, tzinfo=pytz.utc):
                if pytz.utc.localize(point['time']) <= lastPointLocalized:
                    continue

            for key, value in point['fields'].iteritems():
                try:
                    point['fields'][key] = float(value)
                except (ValueError, TypeError):
                    pass    # just leave bad /

            # Convert the purple air deg F to deg C
            tempVal = point['fields'].get('Temp (*C)')
            if tempVal is not None:
                point['fields']['Temp (*C)'] = (tempVal - 32) * 5 / 9

            try:
                client.write_points([point])
                LOGGER.info('data point for %s and ID= %s stored' % (str(point['time']), str(point['tags']['ID'])))
            except InfluxDBClientError as e:
                LOGGER.error('InfluxDBClientError\tWriting Purple Air data to influxdb lead to a write error.')
                LOGGER.error('point[time]%s' % str(point['time']))
                LOGGER.error('point[tags]%s' % str(point['tags']))
                LOGGER.error('point[fields]%s' % str(point['fields']))
                LOGGER.error('%s.' % e)
                continue
                # sys.stderr.write('%s\tInfluxDBClientError\tWriting Purple Air data to influxdb lead to a write error.\n' % TIMESTAMP)
                # sys.stderr.write('%s\tpoint[time]%s\n' % (TIMESTAMP, str(point['time'])))
                # sys.stderr.write('%s\tpoint[tags]%s\n' % (TIMESTAMP, str(point['tags'])))
                # sys.stderr.write('%s\tpoint[fields]%s\n' % (TIMESTAMP, str(point['fields'])))
                # sys.stderr.write('%s\t%s.\n' % (TIMESTAMP, e))
            except InfluxDBServerError as se:
                LOGGER.error('InfluxDBServerError\tAn error when writing occured. There is an issue with the server.')
                LOGGER.error('point[time]%s' % str(point['time']))
                LOGGER.error('point[tags]%s' % str(point['tags']))
                LOGGER.error('point[fields]%s' % str(point['fields']))
                LOGGER.error('%s.' % se)
                continue
            else:
                LOGGER.info('PURPLE AIR Polling successful.')
                # sys.stdout.write('%s\tPURPLE AIR Polling successful.\n' % TIMESTAMP)


if __name__ == '__main__':
    config = getConfig()
    client = InfluxDBClient(
        'air.eng.utah.edu',
        8086,
        config['pollingUsername'],
        config['pollingPassword'],
        'defaultdb',
        ssl=True,
        verify_ssl=True
    )

    uploadPurpleAirData(client)

    LOGGER.info('Polling Purple Air done.')
    # sys.stdout.write('%s\tPolling successful.\n' % TIMESTAMP)
