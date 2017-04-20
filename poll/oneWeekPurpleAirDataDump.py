import os
import csv
import sys
import json

from datetime import date, datetime, timedelta

from influxdb import InfluxDBClient


def getConfig():
    with open (sys.path[0] + './../config/config.json', 'r') as configfile:
        return json.loads(configfile.read())
    sys.stderr.write('%s\tProblem reading config file.\n' % TIMESTAMP)
    sys.exit(1)


def writeLoggingDataToFile(data):
    fileName = 'oneWeekPurpleAirData.csv'
    with open(fileName, 'ab') as csvFile:
        writer = csv.writer(csvFile, delimiter = ',', quoting=csv.QUOTE_ALL)
        writer.writerow(data)


def generateHourlyDates(start, end, delta):

    result = []
    start += step
    while start < end:
        result.append(start.strftime('%Y-%m-%dT%H:%M:%SZ'))
        start += step

    return result



if __name__ == "__main__":

    # using CURL to get the data:
    # curl -G 'http://air.eng.utah.edu:8086/query' --data-urlencode "db=defaultdb" --data-urlencode "chunked=true" --data-urlencode "chunk_size=20000" --data-urlencode "q=SELECT * FROM airQuality WHERE Source = 'Purple Air' AND time >= '2017-04-11T00:00:00.000000000Z'"

    # simplified bbox from: https://gist.github.com/mishari/5ecfccd219925c04ac32
    utahBbox = {'left': 36.9979667663574, 'right': 42.0013885498047, 'bottom': -114.053932189941, 'top': -109.041069030762}

    try:
        os.remove('oneWeekPurpleAirData.csv')
    except OSError:
        pass

    config = getConfig()
    client = InfluxDBClient('air.eng.utah.edu', 8086, config['influxdbUsername'], config['influxdbPassword'], 'defaultdb')

    startDate = datetime(2017, 04, 10)
    endDate = datetime(2017, 04, 17)

    writeLoggingDataToFile(['time', 'Latitude', 'Longitude', 'pm2.5 (ug/m^3)', 'Temp (*C)', 'Humidity (%)'])

    hourlyDates = generateHourlyDates(startDate, endDate, timedelta(hours=1))
    initialDate = startDate.strftime('%Y-%m-%dT%H:%M:%SZ')
    for anEndDate in hourlyDates:
        print initialDate
        print anEndDate
        # print 'SELECT * FROM airQuality WHERE Source = \'Purple Air\' AND time >= ' + initialDate + ' AND time <= ' + anEndDate + ';'
        result = client.query('SELECT * FROM airQuality WHERE Source = \'Purple Air\' AND time >= \'' + initialDate + '\' AND time <= \'' + anEndDate + '\';')

        result = list(result.get_points())
        for row in result:
            if row['Latitude'] is None or row['Longitude'] is None:
                continue

            if not((float(row['Longitude']) < float(utahBbox['top'])) and (float(row['Longitude']) > float(utahBbox['bottom']))) or not((float(row['Latitude']) > float(utahBbox['left'])) and (float(row['Latitude']) < float(utahBbox['right']))):
                continue

            writeLoggingDataToFile([row['time'], row['Latitude'], row['Longitude'], row['pm2.5 (ug/m^3)'], row['Temp (*C)'], row['Humidity (%)']])

        initialDate = anEndDate

        # print result


    # result = client.query('SELECT * FROM airQuality WHERE Source = \'Purple Air\' AND time >= \'2017-04-10T00:00:00.000000000Z\' AND time <= \'2017-04-17T00:00:00.000000000Z\';')
    # # time >= \'2017-04-10\' AND time <= \'2017-04-17\';')
    # print result
    # result = list(result.get_points())
    #
    #
    # writeLoggingDataToFile(['time', 'Latitude', 'Longitude', 'pm2.5 (ug/m^3)', 'Temp (*C)', 'Humidity (%)'])
    #
    # for row in result:
    #     writeLoggingDataToFile([row['time'], row['Latitude'], row['Longitude'], row['pm2.5 (ug/m^3)'], row['Temp (*C)'], row['Humidity (%)']])
    #
    #
    print 'DONE'
    # # print result
