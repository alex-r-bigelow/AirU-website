import csv
# import httplib
import json
# import logging
import pytz
import sys
# import urllib2
import requests

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


def getConfig(locationRun):

    configPath = ''
    if locationRun == 'vagrant':
        configPath = './../config/config.json'
    elif locationRun == 'airUServer':
        configPath = '/../config/config.json'

    with open(sys.path[0] + configPath, 'r') as configfile:
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


def generateDailyDates(start, end, delta):

    result = [start.strftime('%Y-%m-%d%%20%H:%M:%S')]
    start += delta
    while start < end:
        result.append(start.strftime('%Y-%m-%d%%20%H:%M:%S'))
        start += delta

    result.append(end.strftime('%Y-%m-%d%%20%H:%M:%S'))
    return result


def writeLoggingDataToFile(fileName, data):

    with open(fileName, 'ab') as csvFile:
        writer = csv.writer(csvFile, delimiter=',', quoting=csv.QUOTE_ALL)
        writer.writerow(data)


def getDualStationsWithPartner():
    # try:
    #     purpleAirData = urllib2.urlopen("https://map.purpleair.org/json").read()
    # except urllib2.URLError, e:
    #     sys.stderr.write('%s\tProblem acquiring PurpleAir data; their server appears to be down.\n' % TIMESTAMP)
    #     sys.stderr.write('%s\t%s.\n' % TIMESTAMP, e.reason)
    #
    # purpleAirData = unicode(purpleAirData, 'ISO-8859-1')
    # purpleAirData = json.loads(purpleAirData)['results']

    try:
        purpleAirData = requests.get("https://map.purpleair.org/json")
        purpleAirData.raise_for_status()
    except requests.exceptions.HTTPError as e:
        sys.stderr.write('%s\tProblem acquiring PurpleAir data; HTTP error.\n' % TIMESTAMP)
        # sys.stderr.write('%s\t%s.\n' % (TIMESTAMP, e.reason))
    except requests.exceptions.Timeout as e:
        # Maybe set up for a retry, or continue in a retry loop
        sys.stderr.write('%s\tProblem acquiring PurpleAir data; timeout error.\n' % TIMESTAMP)
        # sys.stderr.write('%s\t%s.\n' % (TIMESTAMP, e.reason))
    except requests.exceptions.TooManyRedirects as e:
        # Tell the user their URL was bad and try a different one
        sys.stderr.write('%s\tProblem acquiring PurpleAir data; URL was bad.\n' % TIMESTAMP)
        # sys.stderr.write('%s\t%s.\n' % (TIMESTAMP, e.reason))
    except requests.exceptions.RequestException as e:
        # catastrophic error. bail.
        sys.stderr.write('%s\tProblem acquiring PurpleAir data; catastrophic error.\n' % TIMESTAMP)
        # sys.stderr.write('%s\t%s.\n' % (TIMESTAMP, e.reason))
        sys.exit(1)

    purpleAirData = purpleAirData.json()['results']

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
    # errorMsg_acquiringData = 'Problem acquiring PurpleAir data; their server appears to be down.'

    # try:
    #     purpleAirData = urllib2.urlopen(purpleAirJSONUrl).read()
    # except urllib2.URLError, e:
    #     sys.stderr.write('%s\t' + errorMsg_acquiringData + '\n' % TIMESTAMP)
    #     sys.stderr.write('%s\t%s.\n' % TIMESTAMP, e.reason)
    #     return []

    # purpleAirData = unicode(purpleAirData, 'ISO-8859-1')
    # purpleAirData = json.loads(purpleAirData)['results']

    try:
        purpleAirData = requests.get(purpleAirJSONUrl)
        purpleAirData.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print purpleAirJSONUrl
        sys.stderr.write('%s\tProblem acquiring PurpleAir data; HTTP error.\n' % TIMESTAMP)
        # sys.stderr.write('%s\t%s.\n' % (TIMESTAMP, e.reason))
        return []
    except requests.exceptions.Timeout as e:
        print purpleAirJSONUrl
        # Maybe set up for a retry, or continue in a retry loop
        sys.stderr.write('%s\tProblem acquiring PurpleAir data; timeout error.\n' % TIMESTAMP)
        # sys.stderr.write('%s\t%s.\n' % (TIMESTAMP, e.reason))
        return []
    except requests.exceptions.TooManyRedirects as e:
        print purpleAirJSONUrl
        # Tell the user their URL was bad and try a different one
        sys.stderr.write('%s\tProblem acquiring PurpleAir data; URL was bad.\n' % TIMESTAMP)
        # sys.stderr.write('%s\t%s.\n' % (TIMESTAMP, e.reason))
        return []
    except requests.exceptions.RequestException as e:
        print purpleAirJSONUrl
        # catastrophic error. bail.
        sys.stderr.write('%s\tProblem acquiring PurpleAir data; catastrophic error.\n' % TIMESTAMP)
        # sys.stderr.write('%s\t%s.\n' % (TIMESTAMP, e.reason))
        return []

    purpleAirData = purpleAirData.json()['results']

    return purpleAirData


def getPurpleAirUtahStations():

    purpleAirData = getPurpleAirJSON()

    utahPurpleAirStations = []

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

        # tmpStation = {'label': station['Label'], 'ID': station['ID'], 'THINGSPEAK_PRIMARY_ID': station['THINGSPEAK_PRIMARY_ID'], 'THINGSPEAK_PRIMARY_ID_READ_KEY': station['THINGSPEAK_PRIMARY_ID_READ_KEY'], 'THINGSPEAK_SECONDARY_ID': station['THINGSPEAK_SECONDARY_ID'], 'THINGSPEAK_SECONDARY_ID_READ_KEY': ['THINGSPEAK_SECONDARY_ID_READ_KEY'], 'parentID': station['ParentID'], 'Lat': station['Lat'], 'Lon': station['Lon'],' Type': station['Type'], 'Version': station['Version'], 'created_at': station['created_at'], 'LastSeen': station['LastSeen']}

        utahPurpleAirStations.append(station)

    # store in json file
    fileName = './poll/purpleAirUtahStations.json'

    with open(fileName, 'w') as jsonfile:
            json.dump(utahPurpleAirStations, jsonfile, indent=4)

    return utahPurpleAirStations


def getHistoricalPurpleAirData(client, startDate, endDate):

    # purpleAirData = getPurpleAirJSON()
    utahStations = getPurpleAirUtahStations()

    for station in utahStations:
        # # print station
        #
        # # simplified bbox from:
        # # https://gist.github.com/mishari/5ecfccd219925c04ac32
        # utahBbox = {
        #     'left': 36.9979667663574,
        #     'right': 42.0013885498047,
        #     'bottom': -114.053932189941,
        #     'top': -109.041069030762
        # }
        # # lat = specifies north-south position
        # # log = specifies east-west position
        #
        # if station['Lat'] is None or station['Lon'] is None:
        #     # logging.info('latitude or longitude is None')
        #     continue
        #
        # if not((float(station['Lon']) < float(utahBbox['top'])) and (float(station['Lon']) > float(utahBbox['bottom']))) or not((float(station['Lat']) > float(utahBbox['left'])) and(float(station['Lat']) < float(utahBbox['right']))):
        #     # logging.info('Not in Utah')
        #     continue

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

        # transform to datetime
        # start = datetime.strptime(startDate, '%Y-%m-%d%%00%H:%M:%S')
        # end = datetime.strptime(endDate, '%Y-%m-%d%%00%H:%M:%S')

        dailyDates = generateDailyDates(startDate, endDate, timedelta(days=1))
        # print dailyDates

        initialDate = dailyDates[0]
        for aDay in dailyDates[1:]:
            # print aDay

            # because we poll every 5min, and purple Air has a new value roughly every 1min 10sec, to be safe take the last 10 results
            primaryPart1 = 'https://api.thingspeak.com/channels/'
            primaryPart2 = '/feed.json?api_key='
            primaryPart3 = '&offset=0&start='
            primaryPart4 = '&end='
            queryPrimaryFeed = primaryPart1 + primaryID + primaryPart2 + primaryIDReadKey + primaryPart3 + initialDate + primaryPart4 + aDay

            # print 'primaryfeed'
            # print queryPrimaryFeed

            # try:
            #     purpleAirDataPrimary = urllib2.urlopen(queryPrimaryFeed).read()
            # except urllib2.URLError, e:
            #     sys.stderr.write('%s\tProblem acquiring PurpleAir data from thingspeak; their server appears to be down.\n' % TIMESTAMP)
            #     sys.stderr.write('%s\t%s.\n' % TIMESTAMP, e.reason)
            #     continue

            try:
                purpleAirDataPrimary = requests.get(queryPrimaryFeed)
                purpleAirDataPrimary.raise_for_status()
            except requests.exceptions.HTTPError as e:
                print aDay
                print queryPrimaryFeed
                sys.stderr.write('%s\tProblem acquiring PurpleAir data; HTTP error.\n' % TIMESTAMP)
                continue
                # sys.stderr.write('%s\t%s.\n' % (TIMESTAMP, e.reason))
            except requests.exceptions.Timeout as e:
                print aDay
                print queryPrimaryFeed
                # Maybe set up for a retry, or continue in a retry loop
                sys.stderr.write('%s\tProblem acquiring PurpleAir data; timeout error.\n' % TIMESTAMP)
                continue
                # sys.stderr.write('%s\t%s.\n' % (TIMESTAMP, e.reason))
            except requests.exceptions.TooManyRedirects as e:
                print aDay
                print queryPrimaryFeed
                # Tell the user their URL was bad and try a different one
                sys.stderr.write('%s\tProblem acquiring PurpleAir data; URL was bad.\n' % TIMESTAMP)
                continue
                # sys.stderr.write('%s\t%s.\n' % (TIMESTAMP, e.reason))
            except requests.exceptions.RequestException as e:
                print aDay
                print queryPrimaryFeed
                # catastrophic error. bail.
                sys.stderr.write('%s\tProblem acquiring PurpleAir data; catastrophic error.\n' % TIMESTAMP)
                # sys.stderr.write('%s\t%s.\n' % (TIMESTAMP, e.reason))
                continue

            purpleAirDataPrimaryChannel = purpleAirDataPrimary.json()['channel']
            purpleAirDataPrimaryFeed = purpleAirDataPrimary.json()['feeds']

            # purpleAirDataPrimary = unicode(purpleAirDataPrimary, 'ISO-8859-1')
            # purpleAirDataPrimaryChannel = json.loads(purpleAirDataPrimary)['channel']
            # purpleAirDataPrimaryFeed = json.loads(purpleAirDataPrimary)['feeds']
            # print 'purpleAirDataPrimaryFeed'
            # print purpleAirDataPrimaryFeed

            try:
                start = datetime.strptime(purpleAirDataPrimaryChannel['created_at'], '%Y-%m-%dT%H:%M:%SZ')
            except ValueError:
                # ok if we do not have that date, not crucial
                # logging.info('No start date')
                pass

            point['tags']['Start'] = start
            # print start

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

            querySecondaryFeed = secondaryPart1 + secondaryID + secondaryPart2 + secondaryIDReadKey + secondaryPart3 + initialDate + secondaryPart4 + aDay

            # print 'secondaryID'
            # print querySecondaryFeed

            initialDate = aDay

            # try:
            #     purpleAirDataSecondary = urllib2.urlopen(querySecondaryFeed).read()
            # except urllib2.URLError, e:
            #     sys.stderr.write('%s\tURLError\tProblem acquiring PurpleAir data from the secondary feed; their server appears to be down. The problematic ID is %s and the key is %s.\n' % (TIMESTAMP, secondaryID, secondaryIDReadKey))
            #     sys.stderr.write('%s\t%s.\n' % TIMESTAMP, e.reason)
            #     # return []
            #     continue
            # except httplib.BadStatusLine:
            #     sys.stderr.write('%s\tBadStatusLine\t%s\n' % (TIMESTAMP, queryPrimaryFeed))
            #     continue

            try:
                purpleAirDataSecondary = requests.get(querySecondaryFeed)
                purpleAirDataSecondary.raise_for_status()
            except requests.exceptions.HTTPError as e:
                print aDay
                print querySecondaryFeed
                sys.stderr.write('%s\tProblem acquiring PurpleAir data; HTTP error.\n' % TIMESTAMP)
                continue
                # sys.stderr.write('%s\t%s.\n' % (TIMESTAMP, e.reason))
            except requests.exceptions.Timeout as e:
                print aDay
                print querySecondaryFeed
                # Maybe set up for a retry, or continue in a retry loop
                sys.stderr.write('%s\tProblem acquiring PurpleAir data; timeout error.\n' % TIMESTAMP)
                continue
                # sys.stderr.write('%s\t%s.\n' % (TIMESTAMP, e.reason))
            except requests.exceptions.TooManyRedirects as e:
                print aDay
                print querySecondaryFeed
                # Tell the user their URL was bad and try a different one
                sys.stderr.write('%s\tProblem acquiring PurpleAir data; URL was bad.\n' % TIMESTAMP)
                continue
                # sys.stderr.write('%s\t%s.\n' % (TIMESTAMP, e.reason))
            except requests.exceptions.RequestException as e:
                print aDay
                print querySecondaryFeed
                # catastrophic error. bail.
                sys.stderr.write('%s\tProblem acquiring PurpleAir data; catastrophic error.\n' % TIMESTAMP)
                # sys.stderr.write('%s\t%s.\n' % (TIMESTAMP, e.reason))
                continue

            purpleAirDataSecondaryFeed = purpleAirDataSecondary.json()['feeds']

            # purpleAirDataSecondary = unicode(purpleAirDataSecondary, 'ISO-8859-1')
            # purpleAirDataSecondaryFeed = json.loads(purpleAirDataSecondary)['feeds']
            # print 'purpleAirDataSecondaryFeed'
            # print len(purpleAirDataSecondaryFeed)
            # print 'purpleAirDataPrimaryFeed'
            # print len(purpleAirDataPrimaryFeed)

            diff = 0
            if len(purpleAirDataPrimaryFeed) != len(purpleAirDataSecondaryFeed):
                print 'do not have the same length'
                print 'purpleAirDataPrimaryFeed' + str(len(purpleAirDataPrimaryFeed)) and 'purpleAirDataSecondaryFeed' + str(len(purpleAirDataSecondaryFeed))
                diff = len(purpleAirDataPrimaryFeed) - len(purpleAirDataSecondaryFeed)
                # print diff

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
                print 'writing the point'
                print point['time']
                print point['tags']
                print point['fields']

                try:
                    client.write_points([point])
                except InfluxDBClientError:
                    print point['time']
                    print point['tags']
                    print point['fields']
                    sys.stderr.write('%s\tInfluxDBClientError\tWriting Purple Air data to influxdb lead to a write error.\n' % TIMESTAMP)


def storeDualSensorDataInCSV(client, startDate, endDate):

    filename = '/home/pgoffin/winter-dual-sensor-pm-data.csv'

    # transform to datetime
    # start = datetime.strptime(startDate, '%Y-%m-%d%%00%H:%M:%S')
    # end = datetime.strptime(endDate, '%Y-%m-%d%%00%H:%M:%S')

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

    hourlyDates = generateHourlyDates(startDate, endDate, timedelta(hours=1))
    initialDate = startDate.strftime('%Y-%m-%dT%H:%M:%SZ')

    dualStations = getDualStationsWithPartner()

    for station in dualStations:
        stationID = station['ID']
        print stationID

        for anEndDate in hourlyDates:
            # print initialDate
            # print anEndDate
            # print 'SELECT * FROM airQuality WHERE Source = \'Purple Air\' AND time >= ' + initialDate + ' AND time <= ' + anEndDate + ';'
            # result = client.query('SELECT * FROM airQuality WHERE ID=\'84\' AND time >= \'' + initialDate + '\' AND time <= \'' + anEndDate + '\';')
            result = client.query('SELECT * FROM airQuality WHERE ID = \'' + str(stationID) + '\' AND time >= \'' + initialDate + '\' AND time <= \'' + anEndDate + '\';')

            result = list(result.get_points())
            print result
            for row in result:

                writeLoggingDataToFile(filename, [row['time'], row['ID'], station['parentID'], row['Latitude'], row['Longitude'], row['pm2.5 (ug/m^3)']])

            initialDate = anEndDate

        print 'DONE'


# usage python getHistoricalPurpleAirData.py vagrant/airUServer populateDB/storeDualSensorsInFile/getUtahPA 2016-12-15T00:00:00Z 2016-12-22T00:00:00Z
# vagrant/airUServer is found in sys.argv[1]
# populateDB/storeDualSensorsInFile is found in sys.argv[2]
if __name__ == '__main__':
    config = getConfig(sys.argv[1])

    serverUrl = ''
    if sys.argv[1] == 'vagrant':
        serverUrl = 'localhost'
    elif sys.argv[1] == 'airUServer':
        serverUrl = 'air.eng.utah.edu'

    client = InfluxDBClient(
        serverUrl,
        8086,
        config['influxdbUsername'],
        config['influxdbPassword'],
        'purpleAirHistoricData'
    )

    # roughly 15 Dec to 28 Feb
    # startDate = '2016-12-15%0000:00:00'
    # endDate = '2016-12-22%0000:00:00'
    # print len(sys.argv)
    if len(sys.argv) > 3:
        startDate = sys.argv[3]
        endDate = sys.argv[4]

        startDate = datetime.strptime(startDate, '%Y-%m-%dT%H:%M:%SZ')
        endDate = datetime.strptime(endDate, '%Y-%m-%dT%H:%M:%SZ')

    if (sys.argv[2] == 'populateDB'):
        # to populate the db
        getHistoricalPurpleAirData(client, startDate, endDate)
        sys.stdout.write('%s\tPopulating db has been successful.\n' % TIMESTAMP)

    elif (sys.argv[2] == 'storeDualSensorsInFile'):
        # to store the dual sensors in a csv file
        storeDualSensorDataInCSV(client, startDate, endDate)
        sys.stdout.write('%s\tAll the dual sensors have been written to the file.\n' % TIMESTAMP)

    elif (sys.argv[2] == 'getUtahPA'):
        # usage: python poll/getHistoricalPurpleAirData.py airUServer getUtahPA
        getPurpleAirUtahStations()
        sys.stdout.write('%s\tInformation about the Utah PA stations.\n' % TIMESTAMP)
