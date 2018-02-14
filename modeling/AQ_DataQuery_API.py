import csv
import json
import os
import sys

from datetime import datetime
from datetime import timedelta
# import numpy as np

# from influxdb import InfluxDBClient


TIMESTAMP = datetime.now().isoformat()


def getConfig():
    with open(sys.path[0] + '/config/config.json', 'r') as configfile:
        return json.loads(configfile.read())
    sys.stderr.write('%s\tProblem reading config file.\n' % TIMESTAMP)
    sys.exit(1)


def writeLoggingDataToFile(data):
    fileName = 'queriedData.csv'
    with open(fileName, 'ab') as csvFile:
        writer = csv.writer(csvFile, delimiter=',', quoting=csv.QUOTE_ALL)
        writer.writerow(data)


def generateDatePartitions(start, end, delta):

    result = []
    start += delta
    while start < end:
        result.append(start.strftime('%Y-%m-%dT%H:%M:%SZ'))
        start += delta
    result.append(end.strftime('%Y-%m-%dT%H:%M:%SZ'))

    return result


def AQDataQuery(pAirClient, airUClient, dbs, startDate, endDate, binFreq=3600, maxLat=42.0013885498047, minLong=-114.053932189941, minLat=36.9979667663574, maxLong=-109.041069030762):
    borderBox = {'left': minLong,
                 'right': maxLong,
                 'bottom': minLat,
                 'top': maxLat
                 }

    # # Reading the config file
    # config = getConfig()
    # # Purple Air client
    # pAirClient = InfluxDBClient(
    #     config['influx_host'],
    #     config['influx_port'],
    #     config['influx_username'],
    #     config['influx_pwd'],
    #     config['purpleAir_db'],
    #     ssl=True,
    #     verify_ssl=True
    # )
    # # airU client
    # airUClient = InfluxDBClient(
    #     config['influx_host'],
    #     config['influx_port'],
    #     config['influx_username'],
    #     config['influx_pwd'],
    #     config['airu_db'],
    #     ssl=True,
    #     verify_ssl=True
    # )

    # Creating the time stamps using the start date, end date, and the binning frequency
    datePartitions = generateDatePartitions(startDate, endDate, timedelta(seconds=500 * binFreq))
    initialDate = startDate.strftime('%Y-%m-%dT%H:%M:%SZ')
    finalDate = endDate.strftime('%Y-%m-%dT%H:%M:%SZ')

    # Querying the Purple Air sensor IDs with their coordinates and sensor model
    result = pAirClient.query('SELECT "pm2.5 (ug/m^3)","ID","Longitude","Latitude","Sensor Model" FROM airQuality WHERE "Sensor Source" = \'Purple Air\' AND time >= \'' + initialDate + '\' AND time <= \'' + finalDate + '\';')
    result = list(result.get_points())

    pAirUniqueIDs = []
    latitudes = []
    longitudes = []
    sensorModels = []
    for row in result:
        if row['Latitude'] is None or row['Longitude'] is None:
            print "Skipped sensor with ID:" + row['ID'] + " -> Latitude/Longitude information not available!"
            continue

        if not((float(row['Longitude']) < borderBox['right']) and (float(row['Longitude']) > borderBox['left'])) or not((float(row['Latitude']) > borderBox['bottom']) and (float(row['Latitude']) < borderBox['top'])):
            continue

        if row['ID'] not in pAirUniqueIDs:
            pAirUniqueIDs += [row['ID']]
            latitudes += [float(row['Latitude'])]
            longitudes += [float(row['Longitude'])]
            if row['Sensor Model'] is None:
                sensorModels += ['PMS5003']
            else:
                sensorModels += [row['Sensor Model'].split('+')[0]]

    # Querying the airU sensor IDs with their coordinates and sensor model
    result = airUClient.query('SELECT "PM2.5","ID","SensorModel" FROM ' + dbs['airu_pm25_measurement'] + ' WHERE time >= \'' + initialDate + '\' AND time <= \'' + finalDate + '\';')
    result = list(result.get_points())

    # Querying the sensor IDs
    tmpIDs = []
    for row in result:
        if row['ID'] not in tmpIDs:
            tmpIDs += [row['ID']]

    # Querying the coordinates and model of each sensor in the queried geographic area
    airUUniqueIDs = []
    for anID in tmpIDs:
        last = airUClient.query('SELECT LAST(Latitude),"SensorModel" FROM ' +
                                dbs['airu_lat_measurement'] + ' WHERE ID=\'' + anID + '\' AND time >= \'' +
                                initialDate + '\' AND time <= \'' + finalDate + '\';')
        last = list(last.get_points())[0]
        senModel = last['SensorModel']
        lat = last['last']

        last = airUClient.query('SELECT LAST(Longitude),"SensorModel" FROM ' +
                                dbs['airu_long_measurement'] + ' WHERE ID=\'' + anID + '\' AND time >= \'' +
                                initialDate + '\' AND time <= \'' + finalDate + '\';')
        last = list(last.get_points())[0]
        long = last['last']

        if lat is None or long is None:
            print "Skipped sensor with ID:" + anID + " -> Latitude/Longitude information not available!"
            continue
        if lat == 0 or long == 0:
            print "Skipped sensor with ID:" + anID + " -> Latitude/Longitude has not been aquired!"
            continue

        if not((float(long) < borderBox['right']) and (float(long) > borderBox['left'])) or not((float(lat) > borderBox['bottom']) and (float(lat) < borderBox['top'])):
            continue

        airUUniqueIDs += [anID]
        latitudes += [float(lat)]
        longitudes += [float(long)]
        if senModel is None:
            sensorModels += ['']
        else:
            sensorModels += [senModel.split('+')[0]]

    for anEndDate in datePartitions:
        data = []
        times = []
        for anID in pAirUniqueIDs:
            # print 'SELECT * FROM airQuality WHERE "Sensor Source" = \'Purple Air\' AND time >= ' + initialDate + ' AND time <= ' + anEndDate + ';'
            query = 'SELECT MEAN("pm2.5 (ug/m^3)") FROM airQuality WHERE "Sensor Source" = \'Purple Air\' AND time >= \'' + initialDate + '\' AND time < \'' + anEndDate + '\' AND ID = \'' + anID + '\' group by time(' + str(binFreq) + 's);'
            result = pAirClient.query('SELECT MEAN("pm2.5 (ug/m^3)") FROM airQuality WHERE "Sensor Source" = \'Purple Air\' AND time >= \'' + initialDate + '\' AND time < \'' + anEndDate + '\' AND ID = \'' + anID + '\' group by time(' + str(binFreq) + 's);')
            result = list(result.get_points())
            if anID == pAirUniqueIDs[0]:
                for row in result:
                    t = datetime.strptime(row['time'], '%Y-%m-%dT%H:%M:%SZ') - timedelta(hours=7)
                    times += [t]
                    print('pAirUniqueIDs')
                    print(query)
                    print(row['mean'])
                    data.append([row['mean']])
            else:
                for i in range(len(result)):
                    data[i] += [result[i]['mean']]

        for anID in airUUniqueIDs:
            # print 'SELECT * FROM airQuality WHERE "Sensor Source" = \'Purple Air\' AND time >= ' + initialDate + ' AND time <= ' + anEndDate + ';'
            queryAiru = 'SELECT MEAN("PM2.5") FROM ' + dbs['airu_pm25_measurement'] + ' WHERE time >= \'' + initialDate + '\' ' + 'AND time < \'' + anEndDate + '\' AND ID = \'' + anID + '\' ' + 'group by time(' + str(binFreq) + 's);'
            result = airUClient.query('SELECT MEAN("PM2.5") FROM ' +
                                      dbs['airu_pm25_measurement'] + ' WHERE time >= \'' + initialDate + '\' ' +
                                      'AND time < \'' + anEndDate + '\' AND ID = \'' + anID + '\' ' +
                                      'group by time(' + str(binFreq) + 's);')
            result = list(result.get_points())
            if len(pAirUniqueIDs) == 0 and anID == airUUniqueIDs[0]:        # TODO does that line make sense
                for row in result:
                    t = datetime.strptime(row['time'], '%Y-%m-%dT%H:%M:%SZ') - timedelta(hours=7)
                    times += [t]
                    print('airUUniqueIDs')
                    print(queryAiru)
                    print(row['mean'])
                    data.append([row['mean']])
            else:
                for i in range(len(result)):
                    data[i] += [result[i]['mean']]
        initialDate = anEndDate

    IDs = pAirUniqueIDs + airUUniqueIDs

    # return [data, longitudes_float, latitudes_float, times, sensorModels, IDs]
    return [data, longitudes, latitudes, times, sensorModels, IDs]


if __name__ == "__main__":

    # using CURL to get the data:
    # curl -G 'http://air.eng.utah.edu:8086/query'
    # --data-urlencode "db=defaultdb" --data-urlencode "chunked=true"
    # --data-urlencode "chunk_size=20000"
    # --data-urlencode "q=SELECT * FROM airQuality
    # WHERE Source = 'Purple Air' AND time >= '2017-04-11T00:00:00.000000000Z'"
    # small box 2017-07-16 2017-07-21 12:00:00 -111.795549 40.700310 -112.105912 40.856297
    # biggest box 2018-01-07 2018-01-21 3:00:00 40.884547 -112.133074  40.470062 -111.668308
    # run for uncertainty 2018-01-07 2018-01-21 3:00:00 40.810476 -112.001349  40.598850 -111.713403

    # simplified bbox
    # from: https://gist.github.com/mishari/5ecfccd219925c04ac32
    print "Starting date: " + sys.argv[1]
    print "Ending date: " + sys.argv[2]
    print "Binning frequency: " + sys.argv[3]  # The frequency that we use to bin the sensor reading (e.g. every 6 hours)

    startDate = datetime.strptime(sys.argv[1], '%Y-%m-%d')
    endDate = datetime.strptime(sys.argv[2], '%Y-%m-%d')
    # converting MST to UTC
    startDate = startDate + timedelta(hours=7)
    endDate = endDate + timedelta(hours=7)

    binFreqT = datetime.strptime(sys.argv[3], '%H:%M:%S')
    binFreq = binFreqT.hour * 3600 + binFreqT.minute * 60 + binFreqT.second

    # Reading the Geographic area box's GPS coordinates if provided
    if len(sys.argv) >= 7:
        print "Geographic area [top left bottom right]: [" + sys.argv[4] + ", " + sys.argv[5] + ", " + sys.argv[6] + ", " + sys.argv[7] + "]"
        utahBbox = {
            'left': float(sys.argv[5]),
            'right': float(sys.argv[7]),
            'bottom': float(sys.argv[6]),
            'top': float(sys.argv[4])
        }
    else:
        # Default values for the geographic area box's GPS coordinates (Utah for now)
        print "Geographic area [top left bottom right]: [42.0013885498047 -114.053932189941 36.9979667663574 -109.041069030762]"
        utahBbox = {
            'bottom': 36.9979667663574,
            'top': 42.0013885498047,
            'left': -114.053932189941,
            'right': -109.041069030762
        }

    # Removing any previous csv file with the same name
    try:
        os.remove('queriedData.csv')
    except OSError:
        pass

    data = AQDataQuery(startDate, endDate, binFreq, utahBbox['top'], utahBbox['left'], utahBbox['bottom'], utahBbox['right'])

    pm25 = data[0]
    longitudes = data[1]
    latitudes = data[2]
    times = data[3]
    sensorModels = data[4]
    IDs = data[5]

    # Writing the Purple air and the airU sensor IDs with their coordinates and sensor models into the output file
    writeLoggingDataToFile(sum([[''], ['ID'], IDs], []))
    writeLoggingDataToFile(sum([[''], ['Model'], sensorModels], []))
    writeLoggingDataToFile(sum([[''], ['Latitude'], latitudes], []))
    writeLoggingDataToFile(sum([['time'], ['Longitude'], longitudes], []))

    for ind, row in enumerate(pm25):
        writeLoggingDataToFile(sum([[times[ind].strftime('%Y-%m-%dT%H:%M:%SZ')], [''], row], []))

    print('DONE')
