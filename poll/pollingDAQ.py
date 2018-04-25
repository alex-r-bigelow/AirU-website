import json
import logging
import logging.handlers as handlers
import pytz
import requests
import sys

from bs4 import BeautifulSoup
from datetime import datetime
from influxdb.exceptions import InfluxDBClientError
from influxdb import InfluxDBClient


TIMESTAMP = datetime.now().isoformat()

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - [%(funcName)s:%(lineno)d] - %(levelname)s - %(message)s')

logHandler = handlers.RotatingFileHandler('daqPoller.log', maxBytes=5000000, backupCount=5)
logHandler.setLevel(logging.INFO)
logHandler.setFormatter(formatter)
LOGGER.addHandler(logHandler)

# logging.basicConfig(filename='poller.log', level=logging.DEBUG, format='%(asctime)s %(message)s')

# Rose Park: http://air.utah.gov/xmlFeed.php?id=rp
# (1354 West Goodwin Avenue, SLC; Lat: 40.7955; Long: -111.9309;
# Elevation (m): 1295 )
# Hawthorne http://air.utah.gov/xmlFeed.php?id=slc
# (1675 South 600 East, SLC; Lat: 40.7343; Long: -111.8721;
# Elevation (m): 1306)
# Herriman http://air.utah.gov/xmlFeed.php?id=h3    DOES NOT GIVE PM data anymore
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


# new values are generated every 1h by DAQ
def uploadDAQAirData(client):

    local = pytz.timezone('MST')

    for daqSites in DAQ_SITES:

        try:
            daqData = requests.get(daqSites['dataFeed'])
            daqData.raise_for_status()
        except requests.exceptions.HTTPError as e:
            LOGGER.error('Problem acquiring DAQ data (HTTPError);\t%s.' % e, exc_info=True)
            # sys.stderr.write('%s\tProblem acquiring DAQ data;\t%s.\n' % (TIMESTAMP, e))
            continue
        except requests.exceptions.Timeout as e:
            LOGGER.error('Problem acquiring DAQ data (Timeout);\t%s.' % e, exc_info=True)
            # sys.stderr.write('%s\tProblem acquiring DAQ data;\t%s.\n' % (TIMESTAMP, e))
            continue
        except requests.exceptions.TooManyRedirects as e:
            LOGGER.error('Problem acquiring DAQ data (TooManyRedirects);\t%s.' % e, exc_info=True)
            # sys.stderr.write('%s\tProblem acquiring DAQ data;\t%s.\n' % (TIMESTAMP, e))
            continue
        except requests.exceptions.RequestException as e:
            LOGGER.error('Problem acquiring DAQ data (RequestException);\t%s.' % e, exc_info=True)
            # sys.stderr.write('%s\tProblem acquiring DAQ data;\t%s.\n' % (TIMESTAMP, e))
            continue

        daqData = daqData.content
        soup = BeautifulSoup(daqData, "html5lib")

        for measurement in soup.findAll('data'):

            point = {
                'measurement': 'airQuality_DAQ',
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

            try:
                client.write_points([point])
                LOGGER.info('data point for %s stored' % str(point['time']))
            except InfluxDBClientError as e:
                LOGGER.error('InfluxDBClientError\tWriting DAQ data to influxdb lead to a write error.' % TIMESTAMP, exc_info=True)
                LOGGER.error('point[time]%s' % str(point['time']))
                LOGGER.error('point[tags]%s' % str(point['tags']))
                LOGGER.error('point[fields]%s' % str(point['fields']))
                LOGGER.error('%s.' % e)
                # sys.stderr.write('%s\tInfluxDBClientError\tWriting DAQ data to influxdb lead to a write error.\n' % TIMESTAMP)
                # sys.stderr.write('%s\tpoint[time]%s\n' % (TIMESTAMP, str(point['time'])))
                # sys.stderr.write('%s\tpoint[tags]%s\n' % (TIMESTAMP, str(point['tags'])))
                # sys.stderr.write('%s\tpoint[fields]%s\n' % (TIMESTAMP, str(point['fields'])))
                # sys.stderr.write('%s\t%s.\n' % (TIMESTAMP, e))
            else:
                LOGGER.info('DAQ Polling successful.')
                # sys.stdout.write('%s\tDAQ Polling successful.\n' % TIMESTAMP)


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

    uploadDAQAirData(client)

    LOGGER.info('DAQ Polling done.')
