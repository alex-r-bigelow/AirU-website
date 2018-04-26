import json
import logging
import logging.handlers as handlers
import pytz
import requests
import sys

from datetime import datetime
from influxdb.exceptions import InfluxDBClientError
from influxdb import InfluxDBClient


TIMESTAMP = datetime.now().isoformat()


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - [%(funcName)s:%(lineno)d] - %(levelname)s - %(message)s')

logHandler = handlers.RotatingFileHandler('mesowestPoller.log', maxBytes=5000000, backupCount=5)
logHandler.setLevel(logging.INFO)
logHandler.setFormatter(formatter)
LOGGER.addHandler(logHandler)


def getConfig():
    with open(sys.path[0] + '/../config/config.json', 'r') as configfile:
        return json.loads(configfile.read())
    sys.stderr.write('%s\tConfigError\tProblem reading config file.\n' % TIMESTAMP)
    sys.exit(1)


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


# new values are generated every 60sec by mesowest
def uploadMesowestData(client):

    # the recent argument is in minutes
    mesowestURL = 'http://api.mesowest.net/v2/stations/timeseries?recent=15&token=demotoken&stid=mtmet,wbb,NAA,MSI01,UFD10,UFD11&vars=wind_speed,air_temp,solar_radiation,wind_gust,relative_humidity,wind_direction,pressure,ozone_concentration,altimeter,PM_25_concentration,sensor_error_code,clear_sky_solar_radiation,internal_relative_humidity,air_flow_temperature'

    try:
        mesowestData = requests.get(mesowestURL)
        mesowestData.raise_for_status()
    except requests.exceptions.HTTPError as e:
        # statusCode = e.response.status_code
        LOGGER.error('Problem acquiring Mesowest data;\t%s.' % e, exc_info=True)
        # sys.stderr.write('%s\tProblem acquiring Mesowest data;\t%s.\n' % (TIMESTAMP, e))
        return []
    except requests.exceptions.Timeout as e:
        # Maybe set up for a retry, or continue in a retry loop
        LOGGER.error('Problem acquiring Mesowest data;\t%s.' % e, exc_info=True)
        # sys.stderr.write('%s\tProblem acquiring Mesowest data;\t%s.\n' % (TIMESTAMP, e))
        return []
    except requests.exceptions.TooManyRedirects as e:
        # Tell the user their URL was bad and try a different one
        LOGGER.error('Problem acquiring Mesowest data;\t%s.' % e, exc_info=True)
        # sys.stderr.write('%s\tProblem acquiring Mesowest data;\t%s.\n' % (TIMESTAMP, e))
        return []
    except requests.exceptions.RequestException as e:
        # catastrophic error. bail.
        LOGGER.error('Problem acquiring Mesowest data;\t%s.' % e, exc_info=True)
        # sys.stderr.write('%s\tProblem acquiring Mesowest data;\t%s.\n' % (TIMESTAMP, e))
        return []

    mesowestData = mesowestData.json()['STATION']

    # go through the stations
    for aMesowestStation in mesowestData:

        point = {
            # 'measurement': 'airQuality_Mesowest',
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
        # print mesowestStartTag

        try:
            point['tags']['Start'] = datetime.strptime(aMesowestStation[mesowestStartTag]['start'], '%Y-%m-%dT%H:%M:%SZ')
        except ValueError:
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
                    LOGGER.info('data point for %s and ID=%s stored' % (str(point['time']), str(point['tags']['ID'])))
                except InfluxDBClientError as e:
                    LOGGER.error('InfluxDBClientError\tWriting mesowest data to influxdb lead to a write error.', exc_info=True)
                    LOGGER.error('point[time]%s' % str(point['time']))
                    LOGGER.error('point[tags]%s' % str(point['tags']))
                    LOGGER.error('point[fields]%s' % str(point['fields']))
                    LOGGER.error('%s.' % e)
                    # sys.stderr.write('%s\tInfluxDBClientError\tWriting mesowest data to influxdb lead to a write error.\n' % TIMESTAMP)
                    # sys.stderr.write('%s\tpoint[time]%s\n' % (TIMESTAMP, str(point['time'])))
                    # sys.stderr.write('%s\tpoint[tags]%s\n' % (TIMESTAMP, str(point['tags'])))
                    # sys.stderr.write('%s\tpoint[fields]%s\n' % (TIMESTAMP, str(point['fields'])))
                    # sys.stderr.write('%s\t%s.\n' % (TIMESTAMP, e))
                else:
                    LOGGER.info('Mesowest Polling successful.')
                    # sys.stdout.write('%s\tMesowest Polling successful.\n' % TIMESTAMP)


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

    uploadMesowestData(client)

    LOGGER.info('Mesowest polling done.')
    # sys.stdout.write('%s\tPolling successful.\n' % TIMESTAMP)
