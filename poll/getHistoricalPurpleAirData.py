import csv
import httplib
import json
# import logging
import pytz
import sys
import urllib2

from datetime import datetime
from datetime import timedelta
from influxdb.exceptions import InfluxDBClientError
from influxdb import InfluxDBClient

TIMESTAMP = datetime.now().isoformat()

PURPLE_AIR_FIELDS_PRI_FEED = {
    # 'Humidity (%)': 'field7',
    # 'Temp (*C)': 'field6',   # this gets converted specifically in the function
    'pm2.5 (ug/m^3)': 'field8',     # 'PM2.5 (CF=1)',
}

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


def getConfig():
    # for use on the server '/../config/config.json' for use on Vagrant './../config/config.json'
    with open(sys.path[0] + '/../config/config.json', 'r') as configfile:
        return json.loads(configfile.read())
    sys.stderr.write('%s\tProblem reading config file.\n' % TIMESTAMP)
    sys.exit(1)


def generateHourlyDates(start, end, delta):

    result = []
    start += delta
    while start < end:
        result.append(start.strftime('%Y-%m-%dT%H:%M:%SZ'))
        start += delta

    return result


def writeLoggingDataToFile(fileName, data):

    with open(fileName, 'ab') as csvFile:
        writer = csv.writer(csvFile, delimiter=',', quoting=csv.QUOTE_ALL)
        writer.writerow(data)


def getDualStationsWithPartner():
    try:
        purpleAirData = urllib2.urlopen("https://map.purpleair.org/json").read()
    except urllib2.URLError:
        sys.stderr.write('%s\tProblem acquiring PurpleAir data; their server appears to be down.\n' % TIMESTAMP)

    purpleAirData = unicode(purpleAirData, 'ISO-8859-1')
    purpleAirData = json.loads(purpleAirData)['results']

    noParentStations = []

    # the ones that have a parent --> download parent and child
    stationsToDownload = []
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

        if station['THINGSPEAK_PRIMARY_ID_READ_KEY'] is None:
            # print station['ID']
            continue

        if station['Lat'] is None or station['Lon'] is None:
            # logging.info('latitude or longitude is None')
            continue

        if not((float(station['Lon']) < float(utahBbox['top'])) and (float(station['Lon']) > float(utahBbox['bottom']))) or not((float(station['Lat']) > float(utahBbox['left'])) and(float(station['Lat']) < float(utahBbox['right']))):
            # logging.info('Not in Utah')
            continue

        # print 'ID: ' + str(station['ID']) + ' ' + 'parentID: ' + str(station['ParentID']) + ' ' + station['THINGSPEAK_PRIMARY_ID'] + ' ' + station['Lat'] + ' ' + station['Lon']

        aStation = {'ID': station['ID'], 'parentID': station['ParentID'], 'THINGSPEAK_PRIMARY_ID': station['THINGSPEAK_PRIMARY_ID'], 'THINGSPEAK_PRIMARY_ID_READ_KEY': station['THINGSPEAK_PRIMARY_ID_READ_KEY']}

        if station['ParentID'] is not None:
            stationsToDownload.append(aStation)

            for nps in noParentStations:
                if nps['ID'] == station['ParentID']:
                    stationsToDownload.append(nps)
                    break
        else:
            noParentStations.append(aStation)

    return stationsToDownload


def getPurpleAirJSON():
    purpleAirJSONUrl = "https://map.purpleair.org/json"
    errorMsg_acquiringData = 'Problem acquiring PurpleAir data; their server appears to be down.'

    try:
        purpleAirData = urllib2.urlopen(purpleAirJSONUrl).read()
    except urllib2.URLError:
        sys.stderr.write('%s\t' + errorMsg_acquiringData + '\n' % TIMESTAMP)
        return []

    purpleAirData = unicode(purpleAirData, 'ISO-8859-1')
    purpleAirData = json.loads(purpleAirData)['results']

    return purpleAirData


def getHistoricalPurpleAirData(client, startDate, endDate):

    purpleAirData = getPurpleAirJSON()

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
        primaryPart2 = '/feed.json?api_key='
        primaryPart3 = '&offset=0&start='
        primaryPart4 = '&end='
        queryPrimaryFeed = primaryPart1 + primaryID + primaryPart2 + primaryIDReadKey + primaryPart3 + startDate + primaryPart4 + endDate

        print 'primaryfeed'
        print queryPrimaryFeed

        try:
            purpleAirDataPrimary = urllib2.urlopen(queryPrimaryFeed).read()
        except urllib2.URLError:
            sys.stderr.write('%s\tProblem acquiring PurpleAir data from thingspeak; their server appears to be down.\n' % TIMESTAMP)
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
        print start

        # getting thingspeak secondary feed data: PM1 and PM10
        secondaryID = station['THINGSPEAK_SECONDARY_ID']
        secondaryIDReadKey = station['THINGSPEAK_SECONDARY_ID_READ_KEY']

        if secondaryID is None or secondaryIDReadKey is None:
            # logging.info('secondary information is None')
            pass

        secondaryPart1 = 'https://api.thingspeak.com/channels/'
        secondaryPart2 = '/feed.json?api_key='
        secondaryPart3 = '&offset=0&start='
        secondaryPart4 = '&end='

        querySecondaryFeed = secondaryPart1 + secondaryID + secondaryPart2 + secondaryIDReadKey + secondaryPart3 + startDate + secondaryPart4 + endDate
        print 'secondaryID'
        print querySecondaryFeed

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
        purpleAirDataSecondaryFeed = json.loads(purpleAirDataSecondary)['feeds']
        print 'purpleAirDataSecondaryFeed'
        print len(purpleAirDataSecondaryFeed)
        print 'purpleAirDataPrimaryFeed'
        print len(purpleAirDataPrimaryFeed)

        diff = 0
        if len(purpleAirDataPrimaryFeed) != len(purpleAirDataSecondaryFeed):
            print 'do not have the same length'
            print 'purpleAirDataPrimaryFeed' + str(len(purpleAirDataPrimaryFeed)) and 'purpleAirDataSecondaryFeed' + str(len(purpleAirDataSecondaryFeed))
            diff = len(purpleAirDataPrimaryFeed) - len(purpleAirDataSecondaryFeed)
            print diff

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
                try:
                    if purpleKey in purpleAirDataSecondaryFeed[idx].keys():
                        point['fields'][standardKey] = purpleAirDataSecondaryFeed[idx][purpleKey]
                except IndexError:
                    point['fields'][standardKey] = None

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

            # print point['tags']['ID']

            try:
                client.write_points([point])
            except InfluxDBClientError:
                print point['time']
                print point['tags']
                print point['fields']
                sys.stderr.write('%s\tInfluxDBClientError\tWriting Purple Air data to influxdb lead to a write error.\n' % TIMESTAMP)


def storeDualSensorDataInCSV(client, startDate, endDate):

    filename = 'winter-dual-sensor-pm-data.csv'

    # transform to datetime
    start = datetime.strptime(startDate, '%Y-%m-%d%%00%H:%M:%S')
    end = datetime.strptime(endDate, '%Y-%m-%d%%00%H:%M:%S')

    # print start + ' ' + end

    # writing header
    writeLoggingDataToFile(filename, [
        'time',
        'ID',
        'ParentID',
        'Latitude',
        'Longitude',
        'pm2.5 (ug/m^3)'
    ])

    hourlyDates = generateHourlyDates(start, end, timedelta(hours=1))
    initialDate = start.strftime('%Y-%m-%d%%00%H:%M:%S')

    dualStations = getDualStationsWithPartner()

    for station in dualStations:
        stationID = station['ID']
        print stationID

        for anEndDate in hourlyDates:
            print initialDate
            print anEndDate
            # print 'SELECT * FROM airQuality WHERE Source = \'Purple Air\' AND time >= ' + initialDate + ' AND time <= ' + anEndDate + ';'
        #         result = client.query('SELECT * FROM airQuality WHERE ID=\'84\' AND time >= \'' + initialDate + '\' AND time <= \'' + anEndDate + '\';')
            result = client.query('SELECT * FROM airQuality WHERE ID = \'' + str(stationID) + '\' AND time >= \'' + initialDate + '\' AND time <= \'' + anEndDate + '\';')

            result = list(result.get_points())
            print result
            for row in result:

                writeLoggingDataToFile(filename, [row['time'], row['ID'], station['ParentID'], row['Latitude'], row['Longitude'], row['pm2.5 (ug/m^3)']])

            initialDate = anEndDate

        print 'DONE'


if __name__ == '__main__':
    config = getConfig()
    client = InfluxDBClient(
        # 'air.eng.utah.edu',
        'localhost',
        8086,
        config['influxdbUsername'],
        config['influxdbPassword'],
        'historicalPurpleAirData'
    )

    # roughly 15 Dec to 28 Feb
    startDate = '2016-12-15%0000:00:00'
    endDate = '2016-12-22%0000:00:00'


    # uncomment when building the db
    getHistoricalPurpleAirData(client, startDate, endDate)
    sys.stdout.write('%s\tPolling successful.\n' % TIMESTAMP)

    # take the data for the dual sensors from the db and store it in a file
    # storeDualSensorDataInCSV(client, startDate, endDate)
