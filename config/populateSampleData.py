from influxdb import InfluxDBClient
from datetime import datetime, timedelta
from dateutil import parser
import string
import random


MAC_ADDRESSES = set()
EMAIL_ADDRESSES = set()
RANGES = {
    'Time (UTC)': (parser.parse('2016-08-31 16:00:00.000000'),
                   parser.parse('2016-09-01 04:00:00.000000')),
    'Latitude': (40.5, 40.8),
    'Longitude': (-112.1, -111.6),
    'Altitude (m)': (1400.0, 1600.0),
    'Pressure (Pa)': (84000.0, 86000.0),
    'Humidity (%)': (3.0, 40.0),
    'Temp (*C)': (-10.0, 110.0),
    'pm1 (ug/m^3)': (0.0, 400.0),
    'pm2.5 (ug/m^3)': (0.0, 400.0),
    'pm10 (ug/m^3)': (0.0, 400.0)
}
IGNORE_RANGES_FOR_READINGS = set(['Time (UTC)', 'Latitude', 'Longitude'])
SAMPLE_INTERVAL = timedelta(minutes=1)
ONLINE_STATUS_CHANGE_THRESHOLD = 0.95
N_STATIONS = 30


def generateMacAddress():
    macAddress = None
    while macAddress is None or macAddress in MAC_ADDRESSES:
        macAddress = ''.join([hex(random.randint(0, 0xFF))[2:].zfill(2) for x in xrange(6)])
    return macAddress


def generateEmailAddress():
    emailAddress = None
    while emailAddress is None or emailAddress in EMAIL_ADDRESSES:
        emailAddress = ''.join([random.choice(string.letters) for x in xrange(random.randint(10, 15))]) + '@gmail.com'
    return emailAddress


def generateNumberInRange(r):
    return r[0] + random.random() * (r[1] - r[0])


def adjustNumberInRange(n, r, perc):
    d = (r[1] - r[0]) * perc
    newRange = (max(n - d, r[0]), min(n + d, r[1]))
    return generateNumberInRange(newRange)


def generateStation():
    return {
        'Latitude': generateNumberInRange(RANGES['Latitude']),
        'Longitude': generateNumberInRange(RANGES['Longitude']),
        'Mac Address': generateMacAddress(),
        'Contact Email': generateEmailAddress()
    }


def generateReading(lastReading=None):
    if lastReading is None:
        lastReading = {}
        for k, v in RANGES.iteritems():
            if k not in IGNORE_RANGES_FOR_READINGS:
                lastReading[k] = generateNumberInRange(v)

    # apply up to a 5% change to each reading
    newReading = {}
    for k, v in RANGES.iteritems():
        if k not in IGNORE_RANGES_FOR_READINGS:
            newReading[k] = adjustNumberInRange(lastReading[k], v, 0.05)
    return newReading


def generateReadingSeries():
    series = []
    t = RANGES['Time (UTC)'][0]
    reading = None
    online = True
    while t < RANGES['Time (UTC)'][1]:
        reading = generateReading(reading)
        point = {
            'measurement': 'airQuality',
            'time': t.isoformat(),
            'fields': reading
        }
        if random.random() >= random.random() < ONLINE_STATUS_CHANGE_THRESHOLD:
            online = not online
        if online:
            series.append(point)
        t += SAMPLE_INTERVAL
    return series

if __name__ == '__main__':
    client = InfluxDBClient('127.0.0.1', 8086, 'admin', 'password', 'defaultdb')
    for s in xrange(N_STATIONS):
        print '.',
        station = generateStation()
        series = generateReadingSeries()
        client.write_points(series, tags=station, batch_size=100)
