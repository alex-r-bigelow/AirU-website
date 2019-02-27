import csv
import json
# import os
import requests
import sys

import pandas as pd

from datetime import datetime
from datetime import timedelta


from influxdb import InfluxDBClient

nowTimestamp = datetime.now()
TIMESTAMP = nowTimestamp.isoformat()


def getConfig():
    with open(sys.path[0] + '/config.json', 'r') as configfile:
        return json.loads(configfile.read())
    sys.stderr.write('%s\tProblem reading config file.\n' % TIMESTAMP)
    sys.exit(1)


def writeLoggingDataToFile(source, theBinFreq, data):

    fileNameWithTimestamp = "queriedData-%s-%d-%d-%d-%d-%d-%d-%d.csv" % (source, theBinFreq, nowTimestamp.year, nowTimestamp.month, nowTimestamp.day, nowTimestamp.hour, nowTimestamp.minute, nowTimestamp.second)

    # fileName = 'queriedData10min.csv'
    fileName = fileNameWithTimestamp
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


def AQDataQuery(sensorSource, startDate, endDate, binFreq=3600, maxLat=42.0013885498047, minLong=-114.053932189941, minLat=36.9979667663574, maxLong=-109.041069030762):
    borderBox = {'left':   minLong,
                 'right':  maxLong,
                 'bottom': minLat,
                 'top':    maxLat
                 }

    # Reading the config file
    config = getConfig()
    # Purple Air client
    pAirClient = InfluxDBClient(
        config['influx_host'],
        config['influx_port'],
        config['influx_username'],
        config['influx_pwd'],
        config['purpleAir_db'],
        ssl=True,
        verify_ssl=True
    )
    # airU client
    airUClient = InfluxDBClient(
        config['influx_host'],
        config['influx_port'],
        config['influx_username'],
        config['influx_pwd'],
        config['airu_db'],
        ssl=True,
        verify_ssl=True
    )

    # Creating the time stamps using the start date, end date, and the binning frequency
    tPartsNT = 500
    datePartitions = generateDatePartitions(startDate, endDate, timedelta(seconds=tPartsNT * binFreq))

    if len(datePartitions)>1:
        nt = (len(datePartitions)-1)*500 + \
        (datetime.strptime(datePartitions[-1],'%Y-%m-%dT%H:%M:%SZ')-\
        datetime.strptime(datePartitions[-2],'%Y-%m-%dT%H:%M:%SZ')).total_seconds()/binFreq
    else:
        nt = (datetime.strptime(datePartitions[-1],'%Y-%m-%dT%H:%M:%SZ')-startDate).total_seconds()/binFreq
    nt = int(nt)

    pAirUniqueIDs = []
    latitudes = []
    longitudes = []
    sensorModels = []
    airUUniqueIDs = []
    initialDate = startDate.strftime('%Y-%m-%dT%H:%M:%SZ')

    source = ''
    if sensorSource == 'PurpleAir+airU':
        source = 'Purple Air'
    elif sensorSource == 'DAQ':
        source = 'DAQ'
    else:
        source = 'unknown'

    print(source)

    for anEndDate in datePartitions:
        # Querying the Purple Air sensor IDs with their coordinates and sensor model
        result = pAirClient.query('SELECT "pm2.5 (ug/m^3)","ID","Longitude","Latitude","Sensor Model" FROM airQuality WHERE "Sensor Source" = \'' + source + '\' AND time >= \'' + initialDate + '\' AND time <= \'' + anEndDate + '\';')
        result = list(result.get_points())

        for row in result:
            if row['Latitude'] is None or row['Longitude'] is None:
                print("Skipped sensor with ID:" + row['ID'] + " -> Latitude/Longitude information not available!")
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

        if sensorSource == 'PurpleAir+airU':
            # Querying the airU sensor IDs with their coordinates and sensor model
            result = airUClient.query('SELECT "PM2.5","ID","SensorModel" FROM ' + config['airu_pm25_measurement'] + ' WHERE time >= \'' + initialDate + '\' AND time <= \'' + anEndDate + '\';')
            result = list(result.get_points())

            # Querying the sensor IDs
            tmpIDs = []
            for row in result:
                if row['ID'] not in tmpIDs and row['ID'] not in airUUniqueIDs:
                    tmpIDs += [row['ID']]

            # Querying the coordinates and model of each sensor in the queried geographic area
            for anID in tmpIDs:
                last = airUClient.query('SELECT LAST(Latitude),"SensorModel" FROM ' \
                         + config['airu_lat_measurement'] + ' WHERE ID=\'' + anID +'\' AND time >= \'' \
                         + initialDate + '\' AND time <= \'' + anEndDate + '\';')
                last = list(last.get_points())[0]
                senModel = last['SensorModel']
                lat = last['last']

                last = airUClient.query('SELECT LAST(Longitude),"SensorModel" FROM ' \
                         + config['airu_long_measurement'] + ' WHERE ID=\'' + anID +'\' AND time >= \'' \
                         + initialDate + '\' AND time <= \'' + anEndDate + '\';')
                last = list(last.get_points())[0]
                long = last['last']

                if lat is None or long is None:
                    print("Skipped sensor with ID:" + anID + " -> Latitude/Longitude information not available!")
                    continue
                if lat == 0 or long == 0:
                    print("Skipped sensor with ID:" + anID + " -> Latitude/Longitude has not been aquired!")
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
        initialDate = anEndDate

    nres = 0
    data = []
    times = []
    initialDate = startDate.strftime('%Y-%m-%dT%H:%M:%SZ')
    for anEndDate in datePartitions:
        for anID in pAirUniqueIDs:
            # print 'SELECT * FROM airQuality WHERE "Sensor Source" = \'Purple Air\' AND time >= ' + initialDate + ' AND time <= ' + anEndDate + ';'
            result = pAirClient.query('SELECT MEAN("pm2.5 (ug/m^3)") FROM airQuality WHERE "Sensor Source" = \'' + source + '\' AND time >= \'' + initialDate + '\' AND time < \'' + anEndDate + '\' AND ID = \'' + anID + '\' group by time(' + str(binFreq) + 's);')
            result = list(result.get_points())

            # print('####### debugging #######')
            # print(result)
            # print('####### debugging #######')
            # print('')
            # print('')

            if anID == pAirUniqueIDs[0]:
                if not result:
                    for i in range(min(tPartsNT, nt-nres)):
                        data.append([None])
                    t = datetime.strptime(initialDate, '%Y-%m-%dT%H:%M:%SZ') - timedelta(hours=7)
                    et = datetime.strptime(anEndDate, '%Y-%m-%dT%H:%M:%SZ') - timedelta(hours=7)
                    while(t<et):
                        times += [t]
                        t += timedelta(seconds=binFreq)
                else:
                    for row in result:
                        t = datetime.strptime(row['time'], '%Y-%m-%dT%H:%M:%SZ') - timedelta(hours=7)
                        times += [t]
                        data.append([row['mean']])
            else:
                if not result:
                    for i in range(min(tPartsNT, nt-nres)):
                        data[i+nres] += [None]
                else:
                    for i in range(len(result)):
                        data[i + nres] += [result[i]['mean']]

        if sensorSource == 'PurpleAir+airU':
                        for anID in airUUniqueIDs:
                            # print 'SELECT * FROM airQuality WHERE "Sensor Source" = \'Purple Air\' AND time >= ' + initialDate + ' AND time <= ' + anEndDate + ';'
                            result = airUClient.query('SELECT MEAN("PM2.5") FROM ' \
                                     + config['airu_pm25_measurement'] + ' WHERE time >= \'' + initialDate + \
                                     '\' AND time < \'' + anEndDate  + '\' AND ID = \'' + anID + \
                                     '\' group by time('+ str(binFreq)+ 's);')
                            result = list(result.get_points())
                            if len(pAirUniqueIDs) == 0 and anID == airUUniqueIDs[0]:
                                if not result:
                                    for i in range(min(tPartsNT, nt-nres)):
                                        data.append([None])
                                    t = datetime.strptime(initialDate, '%Y-%m-%dT%H:%M:%SZ') - timedelta(hours=7)
                                    et = datetime.strptime(anEndDate, '%Y-%m-%dT%H:%M:%SZ') - timedelta(hours=7)
                                    while(t<et):
                                        times += [t]
                                        t += timedelta(seconds=binFreq)
                                else:
                                    for row in result:
                                        t = datetime.strptime(row['time'], '%Y-%m-%dT%H:%M:%SZ') - timedelta(hours=7)
                                        times += [t]
                                        data.append([row['mean']])
                            else:
                                if not result:
                                    for i in range(min(tPartsNT, nt-nres)):
                                        data[i+nres] += [None]
                                else:
                                    for i in range(len(result)):
                                        data[i + nres] += [result[i]['mean']]

        initialDate = anEndDate
        nres += tPartsNT

    IDs = pAirUniqueIDs + airUUniqueIDs

    return [data, longitudes, latitudes, times, sensorModels, IDs]


if __name__ == "__main__":

    # python AQ_DataQuery_API.py 2018-11-10 2018-11-12 1:00:00 DAQ
    # python AQ_DataQuery_API.py 2018-11-10 2018-11-12 1:00:00 PurpleAir+airU

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
    print "Sensor Source (DAQ, PurpleAir+airU): " + sys.argv[4]

    startDate = datetime.strptime(sys.argv[1], '%Y-%m-%d')
    endDate   = datetime.strptime(sys.argv[2], '%Y-%m-%d')
    # converting MST to UTC
    startDate = startDate + timedelta(hours=7)
    endDate   = endDate + timedelta(hours=7)

    binFreqT = datetime.strptime(sys.argv[3], '%H:%M:%S')
    binFreq  = binFreqT.hour * 3600 + binFreqT.minute * 60 + binFreqT.second

    # which sensor source
    sensorSource = sys.argv[4]

    # Reading the Geographic area box's GPS coordinates if provided
    if len(sys.argv) >= 7:
        print "Geographic area [top left bottom right]: [" + sys.argv[5] + ", " + sys.argv[6] + ", " + sys.argv[7] + ", " + sys.argv[8] + "]"
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

    if sensorSource == 'DAQ' and binFreq < 3600:
        print("bin frenquency needs to be at least 1h")
    elif sensorSource in ['PurpleAir+airU', 'DAQ']:

        data = AQDataQuery(sensorSource, startDate, endDate, binFreq, utahBbox['top'], utahBbox['left'], utahBbox['bottom'], utahBbox['right'])

        pm25 = data[0]
        longitudes = data[1]
        latitudes = data[2]
        times = data[3]
        sensorModels = data[4]
        IDs = data[5]

        airuSensorMacs = []
        for index, aSensorModel in enumerate(sensorModels):
            anID = IDs[index]
            if aSensorModel == 'H1.1' and len(anID) == 12:
                airuSensorMacs.append(anID)

        try:
            mappingMACTobatch = requests.post("http://air.eng.utah.edu/dbapi/api/macToBatch", json={'mac': airuSensorMacs})
            mappingMACTobatch.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print 'Problem acquiring mapping data (http://air.eng.utah.edu/dbapi/api/macToBatch);\t%s.' % e
        except requests.exceptions.Timeout as e:
            print 'Problem acquiring mapping data (http://air.eng.utah.edu/dbapi/api/macToBatch);\t%s.' % e
        except requests.exceptions.TooManyRedirects as e:
            print 'Problem acquiring mapping data (http://air.eng.utah.edu/dbapi/api/macToBatch);\t%s.' % e
        except requests.exceptions.RequestException as e:
            print 'Problem acquiring mapping data (http://air.eng.utah.edu/dbapi/api/macToBatch);\t%s.' % e

        try:
            mappingMACTobatch = mappingMACTobatch.json()
        except Exception, e:
            print 'JSON parsing error. \t%s' % e

        print('********** mappingMACTobatch **********')
        print(mappingMACTobatch)

        for index, aSensorModel in enumerate(sensorModels):
            anID = IDs[index]
            if aSensorModel == 'H1.1' and len(anID) == 12:
                theBatch = mappingMACTobatch[anID]
                sensorModels[index] = aSensorModel + '_' + theBatch

        # Writing the Purple air and the airU sensor IDs with their coordinates and sensor models into the output file
        writeLoggingDataToFile(sensorSource, binFreq, sum([[''], ['ID'], IDs], []))
        writeLoggingDataToFile(sensorSource, binFreq, sum([[''], ['Model'], sensorModels], []))
        writeLoggingDataToFile(sensorSource, binFreq, sum([[''], ['Latitude'], latitudes], []))
        writeLoggingDataToFile(sensorSource, binFreq, sum([['time'], ['Longitude'], longitudes], []))

        for ind, row in enumerate(pm25):
            writeLoggingDataToFile(sensorSource, binFreq, sum([[times[ind].strftime('%Y-%m-%dT%H:%M:%SZ')], [''], row], []))

        print('DONE')

    elif sensorSource == 'all':

        # getting the Purple Air, airUdata
        purpleAirAndAiruData = AQDataQuery('PurpleAir+airU', startDate, endDate, binFreq, utahBbox['top'], utahBbox['left'], utahBbox['bottom'], utahBbox['right'])

        pm25_purpleAirAirU = purpleAirAndAiruData[0]
        longitudes_purpleAirAirU = purpleAirAndAiruData[1]
        latitudes_purpleAirAirU = purpleAirAndAiruData[2]
        times_purpleAirAirU = purpleAirAndAiruData[3]
        sensorModels_purpleAirAirU = purpleAirAndAiruData[4]
        IDs_purpleAirAirU = purpleAirAndAiruData[5]

        airuSensorMacs = []
        for index, aSensorModel in enumerate(sensorModels_purpleAirAirU):
            anID = IDs_purpleAirAirU[index]
            if aSensorModel == 'H1.1' and len(anID) == 12:
                airuSensorMacs.append(anID)

        try:
            mappingMACTobatch = requests.post("http://air.eng.utah.edu/dbapi/api/macToBatch", json={'mac': airuSensorMacs})
            mappingMACTobatch.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print 'Problem acquiring mapping data (http://air.eng.utah.edu/dbapi/api/macToBatch);\t%s.' % e
        except requests.exceptions.Timeout as e:
            print 'Problem acquiring mapping data (http://air.eng.utah.edu/dbapi/api/macToBatch);\t%s.' % e
        except requests.exceptions.TooManyRedirects as e:
            print 'Problem acquiring mapping data (http://air.eng.utah.edu/dbapi/api/macToBatch);\t%s.' % e
        except requests.exceptions.RequestException as e:
            print 'Problem acquiring mapping data (http://air.eng.utah.edu/dbapi/api/macToBatch);\t%s.' % e

        try:
            mappingMACTobatch = mappingMACTobatch.json()
        except Exception, e:
            print 'JSON parsing error. \t%s' % e

        # print('********** mappingMACTobatch **********')
        # print(mappingMACTobatch)

        for index, aSensorModel in enumerate(sensorModels_purpleAirAirU):
            anID = IDs_purpleAirAirU[index]
            if aSensorModel == 'H1.1' and len(anID) == 12:
                theBatch = mappingMACTobatch[anID]
                sensorModels_purpleAirAirU[index] = aSensorModel + '_' + theBatch

        # getting the DAQ data
        daqData = AQDataQuery('DAQ', startDate, endDate, 3600, utahBbox['top'], utahBbox['left'], utahBbox['bottom'], utahBbox['right'])

        pm25_daq = daqData[0]
        longitudes_daq = daqData[1]
        latitudes_daq = daqData[2]
        times_daq = daqData[3]
        sensorModels_daq = daqData[4]
        IDs_daq = daqData[5]

        # print(pm25_purpleAirAirU)
        # print(pm25_daq)

        # print(pd.Series(times_purpleAirAirU[0:10], index=times_purpleAirAirU[0:10]))
        # print(pd.Series(pm25_purpleAirAirU[0:10], index=times_purpleAirAirU[0:10]))
        # print(pd.Series(pm25_daq[0:10], index=times_daq[0:10]))

        df1aligned, df2aligned = pd.Series(pm25_purpleAirAirU, index=times_purpleAirAirU).align(pd.Series(pm25_daq, index=times_daq), join='outer', axis=0, method='ffill')

        # print('*********** alignment 1 ***********')
        # print(df1aligned)

        # print('*********** alignment 2 ***********')
        pm25Aligned_daq = df2aligned.tolist()

        # print(pm25Aligned_daq)

        IDs = IDs_purpleAirAirU + IDs_daq
        sensorModels = sensorModels_purpleAirAirU + sensorModels_daq
        latitudes = latitudes_purpleAirAirU + latitudes_daq
        longitudes = longitudes_purpleAirAirU + longitudes_daq

        # Writing the Purple air and the airU sensor IDs with their coordinates and sensor models into the output file
        writeLoggingDataToFile(sensorSource, binFreq, sum([[''], ['ID'], IDs], []))
        writeLoggingDataToFile(sensorSource, binFreq, sum([[''], ['Model'], sensorModels], []))
        writeLoggingDataToFile(sensorSource, binFreq, sum([[''], ['Latitude'], latitudes], []))
        writeLoggingDataToFile(sensorSource, binFreq, sum([['time'], ['Longitude'], longitudes], []))

        for ind, row in enumerate(pm25_purpleAirAirU):
            writeLoggingDataToFile(sensorSource, binFreq, sum([[times_purpleAirAirU[ind].strftime('%Y-%m-%dT%H:%M:%SZ')], [''], row + pm25Aligned_daq[ind]], []))

        print('DONE')

    else:
        print('Something is wrong with the sensorSource')
