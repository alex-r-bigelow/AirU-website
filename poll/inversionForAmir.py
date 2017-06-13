import csv
import json
import os
import sys

from datetime import datetime
from datetime import timedelta

from influxdb import InfluxDBClient


TIMESTAMP = datetime.now().isoformat()
fileName = 'inversion06-01To19-01.csv'
startDate = datetime(2017, 1, 6)
endDate = datetime(2017, 1, 20)


def getConfig():
    with open(sys.path[0] + './../config/config.json', 'r') as configfile:
        return json.loads(configfile.read())
    sys.stderr.write('%s\tProblem reading config file.\n' % TIMESTAMP)
    sys.exit(1)


def writeLoggingDataToFile(data):

    with open(fileName, 'ab') as csvFile:
        writer = csv.writer(csvFile, delimiter=',', quoting=csv.QUOTE_ALL)
        writer.writerow(data)


def generateHourlyDates(start, end, delta):

    result = []
    start += delta
    while start < end:
        result.append(start.strftime('%Y-%m-%dT%H:%M:%SZ'))
        start += delta

    return result


if __name__ == "__main__":

    # simplified bbox
    # from: https://gist.github.com/mishari/5ecfccd219925c04ac32
    utahBbox = {
        'left': 36.9979667663574,
        'right': 42.0013885498047,
        'bottom': -114.053932189941,
        'top': -109.041069030762
    }

    try:
        os.remove(fileName)
    except OSError:
        pass

    config = getConfig()
    client = InfluxDBClient(
        'air.eng.utah.edu',
        8086,
        config['influxdbUsername'],
        config['influxdbPassword'],
        'historicalPurpleAirData'
    )

    writeLoggingDataToFile([
        'time',
        'ID',
        'Latitude',
        'Longitude',
        'pm2.5 (ug/m^3)'
    ])

    hourlyDates = generateHourlyDates(startDate, endDate, timedelta(hours=1))
    initialDate = startDate.strftime('%Y-%m-%dT%H:%M:%SZ')
    for anEndDate in hourlyDates:
        print initialDate
        print anEndDate
        # print 'SELECT * FROM airQuality WHERE Source = \'Purple Air\' AND time >= ' + initialDate + ' AND time <= ' + anEndDate + ';'
#         result = client.query('SELECT * FROM airQuality WHERE ID=\'84\' AND time >= \'' + initialDate + '\' AND time <= \'' + anEndDate + '\';')
        result = client.query('SELECT * FROM airQuality WHERE time >= \'' + initialDate + '\' AND time <= \'' + anEndDate + '\';')

        result = list(result.get_points())
        for row in result:
            # if row['Latitude'] is None or row['Longitude'] is None:
#                 continue
# 
#             if not((float(row['Longitude']) < float(utahBbox['top'])) and (float(row['Longitude']) > float(utahBbox['bottom']))) or not((float(row['Latitude']) > float(utahBbox['left'])) and (float(row['Latitude']) < float(utahBbox['right']))):
#                 continue

            writeLoggingDataToFile([row['time'], row['ID'], row['Latitude'], row['Longitude'], row['pm2.5 (ug/m^3)']])

        initialDate = anEndDate

    print 'DONE'
