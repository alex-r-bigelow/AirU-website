import urllib2
import json
from datetime import datetime
from dateutil import parser
from pytz import utc

PURPLE_AIR_FIELDS = {
    'Latitude': 'Lat',
    'Longitude': 'Lon',
    'Pressure (Pa)': 'pressure',
    'Humidity (%)': 'humidity',
    'Temp (*C)': 'temp_f',  # this gets converted specifically in the upload functions
    'pm2.5 (ug/m^3)': 'PM2_5Value',
    'Sensor age': 'AGE'
}

PURPLE_AIR_TAGS = {
    'ID': 'THINGSPEAK_PRIMARY_ID',
    'Sensor Model': 'Type',
    'Sensor Version': 'Version'
}


def getThingspeakUrl(latestMeasurement, start, end):
    start = '%i-%i-%i%%20%i:%i:%i' % (start.year, start.month, start.day,
                                      start.hour, start.minute, start.second)
    end = '%i-%i-%i%%20%i:%i:%i' % (end.year, end.month, end.day,
                                    end.hour, end.minute, end.second)
    return 'https://thingspeak.com/channels/%s/feed.json?start=%s&end=%s' % (
        latestMeasurement['THINGSPEAK_PRIMARY_ID'], start, end)


def uploadHistoricalPurpleAirData(client, start, end):
    '''try:
        purpleAirData = urllib2.urlopen("https://map.purpleair.org/json").read()
    except URLError:
        sys.stderr.write('%s\tProblem acquiring PurpleAir data; their server appears to be down.\n' % TIMESTAMP)
        return

    purpleAirData = unicode(purpleAirData, 'ISO-8859-1')
    purpleAirData = json.loads(purpleAirData)['results']
    for latestMeasurement in purpleAirData:
        sensorUrl = getThingspeakUrl(latestMeasurement, start, end)
        try:
            allMeasurements = urllib2.urlopen(sensorUrl).read()
        except URLError:
            # Just skip any sensors that we can't access
            continue'''
    pass


def uploadLatestPurpleAirData(client):
    try:
        purpleAirData = urllib2.urlopen("https://map.purpleair.org/json").read()
    except URLError:
        sys.stderr.write('%s\tProblem acquiring PurpleAir data; their server appears to be down.\n' % TIMESTAMP)
        return

    purpleAirData = unicode(purpleAirData, 'ISO-8859-1')
    purpleAirData = json.loads(purpleAirData)['results']
    for measurement in purpleAirData:
        point = {
            'measurement': 'airQuality',
            'fields': {},
            'tags': {
                'Source': 'Purple Air'
            }
        }
        # Figure out the time stamp
        try:
            point['time'] = datetime.fromtimestamp(measurement['LastSeen'], tz=utc)
        except TypeError:
            continue    # don't include the point if we can't parse the timestamp

        # Attach the tags - values about the station that shouldn't change across measurements
        for standardKey, purpleKey in PURPLE_AIR_TAGS.iteritems():
            if purpleKey in measurement:
                point['tags'][standardKey] = measurement[purpleKey]

        if 'ID' not in point['tags']:
            continue    # don't include the point if it doesn't have an ID
        # prefix the ID with "Purple Air " so that there aren't collisions with other data sources
        point['tags']['ID'] = 'Purple Air %i' % point['tags']['ID']

        # Only include the point if we haven't stored this measurement before
        lastPoint = client.query("""SELECT last("Temp (*C)") FROM airQuality WHERE "ID" = '%s'""" % point['tags']['ID'])
        if len(lastPoint) > 0:
            lastPoint = lastPoint.get_points().next()
            if point['time'] <= parser.parse(lastPoint['time']):
                continue

        # Convert all the fields to floats
        for standardKey, purpleKey in PURPLE_AIR_FIELDS.iteritems():
            if purpleKey in measurement:
                try:
                    point['fields'][standardKey] = float(measurement[purpleKey])
                except (ValueError, TypeError):
                    pass    # just leave bad / missing values blank

        # Convert the purple air deg F to deg C
        if 'Temp (*C)' in point['fields']:
            point['fields']['Temp (*C)'] = (point['fields']['Temp (*C)'] - 32) * 5 / 9

        client.write_points([point])
