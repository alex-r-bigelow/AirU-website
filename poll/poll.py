import httplib
import json
# import logging
import pytz
import sys
import urllib2

from bs4 import BeautifulSoup
from datetime import datetime
from dateutil import parser
from influxdb.exceptions import InfluxDBClientError
from influxdb import InfluxDBClient


TIMESTAMP = datetime.now().isoformat()

# logging.basicConfig(filename='poller.log', level=logging.DEBUG, format='%(asctime)s %(message)s')

# Rose Park: http://air.utah.gov/xmlFeed.php?id=rp
# (1354 West Goodwin Avenue, SLC; Lat: 40.7955; Long: -111.9309;
# Elevation (m): 1295 )
# Hawthorne http://air.utah.gov/xmlFeed.php?id=slc
# (1675 South 600 East, SLC; Lat: 40.7343; Long: -111.8721;
# Elevation (m): 1306)
# Herriman http://air.utah.gov/xmlFeed.php?id=h3
# (14058 Mirabella Drive, Herriman; Lat:40.496408; Long: -112.036305;
# Elevation (m): 1534)
# Bountiful http://air.utah.gov/xmlFeed.php?id=bv
# (1380 North 200 West, Bountiful; Lat: 40.903; Long: -111.8845)
# Magna (Met only) http://air.utah.gov/xmlFeed.php?id=mg
# (2935 South 8560 West, Magna, UT; Lat: 40.7068; Long: -112.0947)
DAQ_SITES = [{
    'ID': 'Rose Park',
    'dataFeed': 'http://air.utah.gov/xmlFeed.php?id=rp',
    'lat': 40.7955,
    'lon': -111.9309,
    'elevation': 1295,
    }, {
    'ID': 'Hawthorne',
    'dataFeed': 'http://air.utah.gov/xmlFeed.php?id=slc',
    'lat': 40.7343,
    'lon': -111.8721,
    'elevation': 1306
    }, {
    'ID': 'Herriman',
    'dataFeed': 'http://air.utah.gov/xmlFeed.php?id=h3',
    'lat': 40.496408,
    'lon': -112.036305,
    'elevation': 1534
    }, {
    'ID': 'Bountiful',
    'dataFeed': 'http://air.utah.gov/xmlFeed.php?id=bv',
    'lat': 40.903,
    'lon': -111.8845,
    'elevation': None
    }, {
    'ID': 'Magna (Met only)',
    'dataFeed': 'http://air.utah.gov/xmlFeed.php?id=mg',
    'lat': 40.7068,
    'lon': -112.0947,
    'elevation': None
}]

# TODO: pull historical data; the url format is:
# https://thingspeak.com/channels/194967/feed.json?offset=0&start=2010-01-01%2000:00:00&end=2017-03-01%2000:00:00


def getConfig():
    with open(sys.path[0] + '/../config/config.json', 'r') as configfile:
        return json.loads(configfile.read())
    sys.stderr.write('%s\tConfigError\tProblem reading config file.\n' % TIMESTAMP)
    sys.exit(1)


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


DAQ_FIELDS = {
    # 'Pressure (Pa)': 'pressure',
    'Humidity (%)': 'relative_humidity',
    'Temp (*C)': 'temperature',  # gets converted specifically in the function
    'pm2.5 (ug/m^3)': 'pm25',
    # 'pm1.0 (ug/m^3)': 'pm1',
    'pm10.0 (ug/m^3)': 'pm10',
    'Wind direction (compass degree)': 'wind_direction',
    'Wind speed (m/s)': 'wind_speed'
}

DAQ_TAGS = {
    'ID': 'ID',
    # 'Sensor Model': 'Type',
    # 'Sensor Version': 'Version',
    'Latitude': 'lat',
    'Longitude': 'lon',
    'Altitude (m)': 'elevation'
    # 'Start': 'created_at'
}


MESOWEST_FIELDS = {
    'Pressure (Pa)': 'pressure_set_1',
    'Humidity (%)': 'relative_humidity_set_1',
    'Temp (*C)': 'air_temp_set_1',  # already in *C
    'pm2.5 (ug/m^3)': 'PM_25_concentration_set_1',
    # pm1.0 (ug/m^3),
    # pm10.0 (ug/m^3),
    'Wind direction (compass degree)': 'wind_direction_set_1',
    'Wind speed (m/s)': 'wind_speed_set_1',
    'Ozon concentration (ppb)': 'ozone_concentration_set_1',
    'Sensor error code': 'sensor_error_code_set_1',
    'Solar radiation (W/m**2)': 'solar_radiation_set_1',
    'Wind gust (m/s)': 'wind_gust_set_1'
}

MESOWEST_TAGS = {
    'ID': 'STID',
    # 'Sensor Model': 'Type',
    # 'Sensor Version': 'Version',
    'Latitude': 'LATITUDE',
    'Longitude': 'LONGITUDE',
    'Altitude (m)': 'ELEVATION',
    'Start': 'PERIOD_OF_RECORD'  # plus .start
}


def uploadPurpleAirData(client):
    try:
        purpleAirData = urllib2.urlopen("https://map.purpleair.org/json").read()
    except urllib2.URLError:
        sys.stderr.write('%s\tURLError\tProblem acquiring PurpleAir data; their server appears to be down. Problem here: https://map.purpleair.org/json\n' % TIMESTAMP)
        return []

    purpleAirData = unicode(purpleAirData, 'ISO-8859-1')
    purpleAirData = json.loads(purpleAirData)['results']
    for station in purpleAirData:
        # print station

        # simplified bbox from:
        # https://gist.github.com/mishari/5ecfccd219925c04ac32
        utahBbox = {
            'left': 36.9979667663574,
            'right': 42.0013885498047,
            'bottom': -114.053932189941,
            'top': -109.041069030762
        }
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

        # because we poll every 5min, and purple Air has a new value roughly every 1min 10sec, to be safe take the last 10 results
        primaryPart1 = 'https://api.thingspeak.com/channels/'
        primaryPart2 = '/feed.json?results=10&api_key='
        queryPrimaryFeed = primaryPart1 + primaryID + primaryPart2 + primaryIDReadKey

        try:
            purpleAirDataPrimary = urllib2.urlopen(queryPrimaryFeed).read()
        except urllib2.URLError:
            sys.stderr.write('%s\tURLError\tProblem acquiring PurpleAir data from the primary feed. The problematic ID is %s and the key is %s.\n' % (TIMESTAMP, primaryID, primaryIDReadKey))
            # return []
            continue
        except httplib.BadStatusLine:
            sys.stderr.write('%s\tBadStatusLine\t%s' % (TIMESTAMP, queryPrimaryFeed))
            continue

        purpleAirDataPrimary = unicode(purpleAirDataPrimary, 'ISO-8859-1')
        purpleAirDataPrimaryChannel = json.loads(purpleAirDataPrimary)['channel']
        purpleAirDataPrimaryFeed = json.loads(purpleAirDataPrimary)['feeds']
        # print 'purpleAirDataPrimaryFeed'
        # print purpleAirDataPrimaryFeed

        try:
            start = datetime.strptime(purpleAirDataPrimaryChannel['created_at'], '%Y-%m-%dT%H:%M:%SZ')
        except ValueError:
            # ok if we do not have that date, not crucial
            # logging.info('No start date')
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
            purpleAirDataSecondary = urllib2.urlopen(querySecondaryFeed).read()
        except urllib2.URLError:
            sys.stderr.write('%s\tURLError\tProblem acquiring PurpleAir data from the secondary feed; their server appears to be down. The problematic ID is %s and the key is %s.\n' % (TIMESTAMP, secondaryID, secondaryIDReadKey))
            # return []
            continue
        except httplib.BadStatusLine:
            sys.stderr.write('%s\tBadStatusLine\t%s\n' % (TIMESTAMP, queryPrimaryFeed))
            continue

        purpleAirDataSecondary = unicode(purpleAirDataSecondary, 'ISO-8859-1')
        # purpleAirDataSecondaryChannel = json.loads(purpleAirDataSecondary)['channel']
        purpleAirDataSecondaryFeed = json.loads(purpleAirDataSecondary)['feeds']
        # print 'purpleAirDataSecondaryFeed'
        # print purpleAirDataSecondaryFeed

        # go through the primary feed data
        for idx, aMeasurement in enumerate(purpleAirDataPrimaryFeed):
            # print 'aMeasurement'
            # print aMeasurement

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

            # go through the second feed's fields
            for standardKey, purpleKey in PURPLE_AIR_FIELDS_PRI_FEED.iteritems():
                if purpleKey in aMeasurement.keys():
                    point['fields'][standardKey] = aMeasurement[purpleKey]

            # the measurements between primary feed and secondary feed are of by aroud 5 sec
            # try:
            #     timeSecondary = datetime.strptime(purpleAirDataSecondaryFeed[idx]['created_at'], '%Y-%m-%dT%H:%M:%SZ')
            # except ValueError:
            #     # don't include the point if we can't parse the timestamp
            #     continue

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

            # Convert all the fields to floats
            # for standardKey, purpleKey in PURPLE_AIR_FIELDS.iteritems():
            #     purpleFieldValue = point['fields'].get(standardKey)
            #     if purpleFieldValue is not None:
            #         try:
            #             point['fields'][standardKey] = float(purpleFieldValue)
            #             print 'some points'
            #             print point['fields'][standardKey]
            #         except (ValueError, TypeError):
            #             pass    # just leave bad / missing values blank
            for key, value in point['fields'].iteritems():
                try:
                    point['fields'][key] = float(value)
                    # print 'some points'
                    # print point['fields'][key]
                except (ValueError, TypeError):
                    pass    # just leave bad /

            # Convert the purple air deg F to deg C
            tempVal = point['fields'].get('Temp (*C)')
            if tempVal is not None:
                point['fields']['Temp (*C)'] = (tempVal - 32) * 5 / 9

            # print point['time']
            # print point['tags']
            # print point['fields']

            try:
                client.write_points([point])
            except InfluxDBClientError:
                print point['time']
                print point['tags']
                print point['fields']
                sys.stderr.write('%s\tInfluxDBClientError\tWriting Purple Air data to influxdb lead to a write error.\n' % TIMESTAMP)


def uploadDAQAirData(client):

    local = pytz.timezone('MST')

    for daqSites in DAQ_SITES:
        try:
            daqData = urllib2.urlopen(daqSites['dataFeed']).read()
        except urllib2.URLError:
            sys.stderr.write('%s\tURLError\tProblem acquiring DAQ data; their server appears to be down.\n' % TIMESTAMP)
            continue

        daqData = unicode(daqData, 'ISO-8859-1')

        soup = BeautifulSoup(daqData, "html5lib")

        for measurement in soup.findAll('data'):

            point = {
                'measurement': 'airQuality',
                'fields': {},
                'tags': {
                    'Sensor Source': 'DAQ'
                }
            }

            # Figure out the time stamp
            try:
                time = datetime.strptime(measurement.find('date').get_text(), '%m/%d/%Y %H:%M:%S')
            except ValueError:
                # don't include the point if we can't parse the timestamp
                continue

            local_dt = local.localize(time, is_dst=None)
            utc_dt = local_dt.astimezone(pytz.utc)
            point['time'] = utc_dt

            # print point['time']

            # Attach the tags - values about the station that shouldn't change
            for standardKey, daqKey in DAQ_TAGS.iteritems():
                daqTag = daqSites.get(daqKey)
                if daqTag is not None:
                    point['tags'][standardKey] = daqTag

            # print point['tags']

            # Convert all the fields to floats
            # print 'MEASUREMENT'
            # print measurement

            # check if there is a pm value
            if measurement.find('pm25'):
                pmTag = measurement.find('pm25')
                if pmTag is not None:
                    theValue = pmTag.get_text()

                # only check for empty string
                if theValue:
                    standardPM25Key = list(DAQ_FIELDS.keys())[list(DAQ_FIELDS.values()).index('pm25')]
                    point['fields'][standardPM25Key] = theValue
                else:
                    # if there is no pm value do not store
                    # print 'no pm value'
                    break

            for standardKey, daqKey in DAQ_FIELDS.iteritems():
                daqValue = measurement.find(daqKey)
                if daqKey != 'pm25' and daqValue is not None:
                    theFieldValue = daqValue.get_text()

                    # check for empty string
                    if theFieldValue:
                        point['fields'][standardKey] = daqValue.get_text()

            # Only include the point if we haven't stored this measurement before
            lastPoint = client.query("""SELECT last("pm2.5 (ug/m^3)") FROM airQuality WHERE "ID" = '%s' AND "Sensor Source" = 'DAQ'""" % point['tags']['ID'])
            # print 'LAST POINT'
            # print lastPoint
            if len(lastPoint) > 0:
                lastPoint = lastPoint.get_points().next()
                # print parser.parse(lastPoint['time'], tzinfo=pytz.utc)
                # print point['time']
                lastPointParsed = datetime.strptime(lastPoint['time'], '%Y-%m-%dT%H:%M:%SZ')
                lastPointLocalized = pytz.utc.localize(lastPointParsed, is_dst=None)
                # print lastPointLocalized
                # if point['time'] <= parser.parse(lastPoint['time'], None, tzinfo=pytz.utc):
                if point['time'] <= lastPointLocalized:
                    # if point['time'] <= parser.parse(lastPoint['time']):
                    # print 'POINT NOT INCLUDED'
                    continue

            # Convert all the fields to floats
            for standardKey, daqKey in DAQ_FIELDS.iteritems():
                daqFieldValue = point['fields'].get(standardKey)
                if daqFieldValue is not None:
                    try:
                        point['fields'][standardKey] = float(daqFieldValue)
                    except (ValueError, TypeError):
                        pass    # just leave bad / missing values blank

            # Convert miles per hour to meter per seconds for the wind speed
            windSpeedField = point['fields'].get('Wind speed (m/s)')
            if windSpeedField is not None:
                point['fields']['Wind speed (m/s)'] = windSpeedField * (1609.344 / 3600)

            # Convert the daq deg F to deg C
            # print point['fields']
            tmpField = point['fields'].get('Temp (*C)')
            if tmpField is not None:
                point['fields']['Temp (*C)'] = (tmpField - 32) * 5 / 9

            # print point['time']
            # print point['tags']
            # print point['fields']

            try:
                client.write_points([point])
            except InfluxDBClientError:
                print point['time']
                print point['tags']
                print point['fields']
                sys.stderr.write('%s\tInfluxDBClientError\tWriting DAQ data to influxdb lead to a write error.\n' % TIMESTAMP)


def uploadMesowestData(client):

    # the recent argument is in minutes
    mesowestURL = 'http://api.mesowest.net/v2/stations/timeseries?recent=15&token=demotoken&stid=mtmet,wbb,NAA,MSI01,UFD10,UFD11&vars=wind_speed,air_temp,solar_radiation,wind_gust,relative_humidity,wind_direction,pressure,ozone_concentration,altimeter,PM_25_concentration,sensor_error_code,clear_sky_solar_radiation,internal_relative_humidity,air_flow_temperature'

    try:
        mesowestData = urllib2.urlopen(mesowestURL).read()
    except urllib2.URLError:
        sys.stderr.write('%s\tURLError\tProblem acquiring Mesowest data; their server appears to be down.\n' % TIMESTAMP)

    mesowestData = unicode(mesowestData, 'ISO-8859-1')
    mesowestData = json.loads(mesowestData)['STATION']

    # go through the stations
    for aMesowestStation in mesowestData:

        point = {
            'measurement': 'airQuality',
            'fields': {},
            'tags': {
                'Sensor Source': 'Mesowest'
            }
        }

        # timezone will not be stored in db
        # aTimezone = aMesowestStation['TIMEZONE']
        # local = pytz.timezone(aTimezone)
        # print local

        # however we might only be interested in the day
        # get the 'Start' information
        mesowestStartTag = MESOWEST_TAGS['Start']
        # print 'CHECK CHECK'
        # print mesowestStartTag
        try:
            # print 'WHAT WHAT'
            # print aMesowestStation[mesowestStartTag]['start']
            point['tags']['Start'] = datetime.strptime(aMesowestStation[mesowestStartTag]['start'], '%Y-%m-%dT%H:%M:%SZ')
        except ValueError:
            # print aMesowestStation[mesowestStartTag]['start']
            pass

        # print point['tags']['Start']

        # get the remaining information for the tag fields
        for standardKey, mesowestKey in MESOWEST_TAGS.iteritems():
            mesowestTag = aMesowestStation.get(mesowestKey)
            if mesowestTag is not None and standardKey != 'Start':
                point['tags'][standardKey] = mesowestTag

        # print point['tags']

        # first get the date_time array, has the time of the measurements
        measurements = aMesowestStation['OBSERVATIONS']
        # print measurements

        for idx, aMeasurement in enumerate(measurements['date_time']):
            # get time of measurment
            try:
                # time is provided in UTC by default
                point['time'] = datetime.strptime(aMeasurement, '%Y-%m-%dT%H:%M:%SZ')
                # print 'non UTC timezone'
                # print point['time']
            except ValueError:
                # print aMeasurement
                # don't include the point if we can't parse the timestamp
                continue

            # local_dt = local.localize(point['time'], is_dst=None)
            # utc_dt = local_dt.astimezone(pytz.utc)
            # point['time'] = utc_dt
            # print 'UTC timezone'
            # print point['time']

            # get the information for the fields
            point['fields'] = {}
            for standardKey, mesowestKey in MESOWEST_FIELDS.iteritems():
                mesowestField = measurements.get(mesowestKey)

                if mesowestKey == 'PM_25_concentration_set_1' and mesowestField is None:
                    # if pm concentration is None skip that data point
                    break

                if mesowestField is not None:
                    point['fields'][standardKey] = mesowestField[idx]

            # Only include the point if we haven't stored this measurement before
            lastPoint = client.query("""SELECT last("pm2.5 (ug/m^3)") FROM airQuality WHERE "ID" = '%s' AND "Sensor Source" = 'Mesowest'""" % point['tags']['ID'])
            # print 'LAST POINT'
            # print lastPoint
            if len(lastPoint) > 0:
                lastPoint = lastPoint.get_points().next()
                # print parser.parse(lastPoint['time'], tzinfo=pytz.utc)
                # print point['time']
                lastPointParsed = datetime.strptime(lastPoint['time'], '%Y-%m-%dT%H:%M:%SZ')
                lastPointLocalized = pytz.utc.localize(lastPointParsed, is_dst=None)
                # print lastPointLocalized
                # if point['time'] <= parser.parse(lastPoint['time'], None, tzinfo=pytz.utc):
                if pytz.utc.localize(point['time']) <= lastPointLocalized:
                    # if point['time'] <= parser.parse(lastPoint['time']):
                    # print 'POINT NOT INCLUDED'
                    continue

            for standardKey, purpleKey in MESOWEST_FIELDS.iteritems():
                mesowestFieldValue = point['fields'].get(standardKey)
                if mesowestFieldValue is not None:
                    try:
                        point['fields'][standardKey] = float(mesowestFieldValue)
                    except (ValueError, TypeError):
                        pass    # just leave bad / missing values blank

            # go through the fields and check if there is at least one field
            # that is not none
            notNoneValue = False
            for key, value in point['fields'].iteritems():
                if value is not None:
                    notNoneValue = True
                    break

            if notNoneValue:
                try:
                    client.write_points([point])
                except InfluxDBClientError:
                    print point['time']
                    print point['tags']
                    print point['fields']
                    sys.stderr.write('%s\tInfluxDBClientError\tWriting mesowest data to influxdb lead to a write error.\n' % TIMESTAMP)


if __name__ == '__main__':
    config = getConfig()
    client = InfluxDBClient(
        'air.eng.utah.edu',
        8086,
        config['influxdbUsername'],
        config['influxdbPassword'],
        'defaultdb',
        #ssl=True,
        #verify_ssl=True
    )

    uploadPurpleAirData(client)
    uploadDAQAirData(client)
    uploadMesowestData(client)

    sys.stdout.write('%s\tPolling successful.\n' % TIMESTAMP)
