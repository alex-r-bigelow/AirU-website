from influxdb import InfluxDBClient
from datetime import datetime, timedelta
import string
import random


MAC_ADDRESSES = set()
EMAIL_ADDRESSES = set()
RANGES = {
    'Latitude': (40.5, 40.8),
    'Longitude': (-112.1, -111.6),
    'Radius': (0, 5),
    'PM 2.5': (0.0, 400.0),
    'PM 10': (0.0, 400.0),
    'CO2': (0.0, 400.0),
    'NO2': (0.0, 400.0),
    'Ambient Lux': (0.0, 100000.0),
    'Humidity': (0.0, 1.0),
    'Temperature': (-10.0, 110.0)
}
TIME_RANGE = (datetime.now() - timedelta(weeks=3), datetime.now())
SAMPLE_INTERVAL = timedelta(hours=3)
ONLINE_STATUS_CHANGE_THRESHOLD = 0.95
N_STATIONS = 30


def generateMacAddress():
    macAddress = None
    while macAddress is None or macAddress in MAC_ADDRESSES:
        macAddress = '-'.join([hex(random.randint(0, 0xFF))[2:].zfill(2) for x in xrange(6)])
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
        'latitude': generateNumberInRange(RANGES['Latitude']),
        'longitude': generateNumberInRange(RANGES['Longitude']),
        'radius': generateNumberInRange(RANGES['Radius']),
        'mac_address': generateMacAddress(),
        'contact_email': generateEmailAddress()
    }


def generateReading(lastReading=None):
    if lastReading is None:
        lastReading = {}
        for k, v in RANGES.iteritems():
            lastReading[k] = generateNumberInRange(v)

    # apply up to a 5% change to each reading
    newReading = {}
    for k, v in RANGES.iteritems():
        newReading[k] = adjustNumberInRange(lastReading[k], v, 0.05)
    return newReading


def generateReadingSeries():
    series = []
    t = TIME_RANGE[0]
    reading = None
    online = True
    while t < TIME_RANGE[1]:
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
    client = InfluxDBClient('localhost', 8086, 'admin', 'password', 'defaultdb')
    for s in xrange(N_STATIONS):
        print '.',
        station = generateStation()
        series = generateReadingSeries()
        client.write_points(series, tags=station, batch_size=100)
