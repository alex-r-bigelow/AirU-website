import json
# import logging
import sys
import urllib2

from datetime import datetime
from datetime import timedelta

from influxdb.exceptions import InfluxDBClientError
from influxdb import InfluxDBClient
from itertools import tee

TIMESTAMP = datetime.now().isoformat()

PURPLE_AIR_FIELDS_PRI_FEED = {
    # 'Humidity (%)': 'field7',
    # 'Temp (*C)': 'field6',   # this gets converted specifically in the function
    'pm2.5 (ug/m^3)': 'field8',     # 'PM2.5 (CF=1)',
}

PURPLE_AIR_TAGS = {
    'ID': 'ID',
    # 'Sensor Model': 'Type',
    # 'Sensor Version': 'Version',
    'Latitude': 'Lat',
    'Longitude': 'Lon',
    # 'Altitude (m)': 'elevation'
    # 'Start': 'created_at'
}


def getConfig():
    with open(sys.path[0] + '/../config/config.json', 'r') as configfile:
        return json.loads(configfile.read())
    sys.stderr.write('%s\tProblem reading config file.\n' % TIMESTAMP)
    sys.exit(1)


def getHistoricalPurpleAirData(client, startDate, endDate):
    print startDate
    print endDate

    try:
        purpleAirData = urllib2.urlopen("https://map.purpleair.org/json").read()
    except urllib2.URLError:
        sys.stderr.write('%s\tProblem acquiring PurpleAir data; their server appears to be down.\n' % TIMESTAMP)
        return []

    problematicStations = 0

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
            problematicStations += 1
            continue

        # because we poll every 5min, and purple Air has a new value roughly every 1min 10sec, to be safe take the last 10 results
        primaryPart1 = 'https://api.thingspeak.com/channels/'
        primaryPart2 = '/feed.json?api_key='
        primaryPart3 = '&offset=0&start='
        primaryPart4 = '&end='
        queryPrimaryFeed = primaryPart1 + primaryID + primaryPart2 + primaryIDReadKey + primaryPart3 + startDate + primaryPart4 + endDate

        print queryPrimaryFeed

        try:
            purpleAirDataPrimary = urllib2.urlopen(queryPrimaryFeed).read()
        except urllib2.URLError:
            sys.stderr.write('%s\tProblem acquiring PurpleAir data from thingspeak; their server appears to be down.\n' % TIMESTAMP)
            problematicStations += 1
            continue

        purpleAirDataPrimary = unicode(purpleAirDataPrimary, 'ISO-8859-1')
        # purpleAirDataPrimaryChannel = json.loads(purpleAirDataPrimary)['channel']
        purpleAirDataPrimaryFeed = json.loads(purpleAirDataPrimary)['feeds']
        # print 'purpleAirDataPrimaryFeed'
        # print purpleAirDataPrimaryFeed

        # try:
        #     start = datetime.strptime(purpleAirDataPrimaryChannel['created_at'], '%Y-%m-%dT%H:%M:%SZ')
        # except ValueError:
        #     # ok if we do not have that date, not crucial
        #     # logging.info('No start date')
        #     pass

        # point['tags']['Start'] = start

        # # getting thingspeak secondary feed data: PM1 and PM10
        # secondaryID = station['THINGSPEAK_SECONDARY_ID']
        # secondaryIDReadKey = station['THINGSPEAK_SECONDARY_ID_READ_KEY']
        #
        # if secondaryID is None or secondaryIDReadKey is None:
        #     # logging.info('secondary information is None')
        #     pass
        #
        # secondaryPart1 = 'https://api.thingspeak.com/channels/'
        # secondaryPart2 = '/feed.json?results=10&api_key='
        #
        # querySecondaryFeed = secondaryPart1 + secondaryID + secondaryPart2 + secondaryIDReadKey
        #
        # try:
        #     purpleAirDataSecondary = urllib2.urlopen(querySecondaryFeed).read()
        # except urllib2.URLError:
        #     sys.stderr.write('%s\tProblem acquiring PurpleAir data from thingspeak; their server appears to be down.\n' % TIMESTAMP)
        #     return []
        #
        # purpleAirDataSecondary = unicode(purpleAirDataSecondary, 'ISO-8859-1')
        # # purpleAirDataSecondaryChannel = json.loads(purpleAirDataSecondary)['channel']
        # purpleAirDataSecondaryFeed = json.loads(purpleAirDataSecondary)['feeds']
        # # print 'purpleAirDataSecondaryFeed'
        # # print purpleAirDataSecondaryFeed

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

            # go through the primary feed's fields
            for standardKey, purpleKey in PURPLE_AIR_FIELDS_PRI_FEED.iteritems():
                if purpleKey in aMeasurement.keys():
                    point['fields'][standardKey] = aMeasurement[purpleKey]

            pmValue = point['fields'].get('pm2.5 (ug/m^3)')
            if pmValue is None:
                # print 'pm2.5 value is none'
                continue

            # the measurements between primary feed and secondary feed are of by aroud 5 sec
            # try:
            #     timeSecondary = datetime.strptime(purpleAirDataSecondaryFeed[idx]['created_at'], '%Y-%m-%dT%H:%M:%SZ')
            # except ValueError:
            #     # don't include the point if we can't parse the timestamp
            #     continue

            # # go through the second feed's fields
            # for standardKey, purpleKey in PURPLE_AIR_FIELDS_SEC_FEED.iteritems():
            #     if purpleKey in purpleAirDataSecondaryFeed[idx].keys():
            #         point['fields'][standardKey] = purpleAirDataSecondaryFeed[idx][purpleKey]

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

            # # Only include the point if we haven't stored this measurement before
            # lastPoint = client.query("""SELECT last("ID") FROM airQuality WHERE "ID" = '%s' AND "Sensor Source" = 'Purple Air'""" % point['tags']['ID'])
            # # print 'LAST POINT'
            # # print lastPoint
            # if len(lastPoint) > 0:
            #     lastPoint = lastPoint.get_points().next()
            #     # print parser.parse(lastPoint['time'], tzinfo=pytz.utc)
            #     # print point['time']
            #     if point['time'] <= parser.parse(lastPoint['time']):
            #         continue

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

            # # Convert the purple air deg F to deg C
            # tempVal = point['fields'].get('Temp (*C)')
            # if tempVal is not None:
            #     point['fields']['Temp (*C)'] = (tempVal - 32) * 5 / 9

            # print point['time']
            # print point['tags']
            # print point['fields']
            #
            # print 'THEPOINT'
            # print point

            # print point['tags']['ID']

            try:
                client.write_points([point])
            except InfluxDBClientError:
                print point['time']
                print point['tags']
                print point['fields']
                sys.stderr.write('%s\tWriting Purple Air data to influxdb lead to a write error.\n' % TIMESTAMP)

    print problematicStations


def generateDates(start, end, delta):
    start = datetime.strptime(start, '%Y-%m-%d')
    end = datetime.strptime(end, '%Y-%m-%d')

    curr = start
    while curr < end:
        yield curr
        curr += delta


def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)


if __name__ == '__main__':
    config = getConfig()
    client = InfluxDBClient(
        'air.eng.utah.edu',
        8086,
        config['influxdbUsername'],
        config['influxdbPassword'],
        'historicalPAData'
    )

    # start = '2017-01-06 00:00:00'
    # end = '2017-01-20 00:00:00'
    start = '2017-01-06'
    end = '2017-01-20'
    for startDate, endDate in pairwise(generateDates(start, end, timedelta(days=1))):
        startDate = datetime.strftime(startDate, '%Y-%m-%d')
        startDate = startDate + '%2000:00:00'
        endDate = datetime.strftime(endDate, '%Y-%m-%d')
        endDate = endDate + '%2000:00:00'
        getHistoricalPurpleAirData(client, startDate, endDate)

    sys.stdout.write('%s\tPolling successful.\n' % TIMESTAMP)
