import csv
import json
import os
import requests
import sys

import pandas as pd

from datetime import datetime, timedelta
from influxdb import InfluxDBClient

nowTimestamp = datetime.now()
TIMESTAMP = nowTimestamp.isoformat()


def getConfig():
    # with open(sys.path[0] + '/config.json', 'r') as configfile:
    with open('/Users/pascalgoffin/Documents/Research Projects/AirU-website/modeling/Wei_Data_API' + '/config.json', 'r') as configfile:
        return json.loads(configfile.read())
    sys.stderr.write('%s\tProblem reading config file.\n' % TIMESTAMP)
    sys.exit(1)


def writeLoggingDataToFile(fileName, data):

    # fileNameWithTimestamp = "queriedData-%s-%d%s-%s_%s.csv" % (source, theBinFreq, 's', start, end)

    # fileName = 'queriedData10min.csv'
    # fileName = fileNameWithTimestamp
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
    borderBox = {'left': minLong,
                 'right': maxLong,
                 'bottom': minLat,
                 'top': maxLat
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

    if len(datePartitions) > 1:
        nt = (len(datePartitions) - 1) * 500 + (datetime.strptime(datePartitions[-1], '%Y-%m-%dT%H:%M:%SZ') - datetime.strptime(datePartitions[-2], '%Y-%m-%dT%H:%M:%SZ')).total_seconds() / binFreq
    else:
        nt = (datetime.strptime(datePartitions[-1], '%Y-%m-%dT%H:%M:%SZ') - startDate).total_seconds() / binFreq
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
    elif sensorSource == 'airU':
        source = 'airU'
    elif sensorSource == 'PurpleAir':
        source = 'Purple Air'
    else:
        source = 'unknown'

    print(source)

    for anEndDate in datePartitions:
        # Querying the Purple Air sensor IDs with their coordinates and sensor model
        if sensorSource in ['PurpleAir', 'DAQ']:
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

        if sensorSource == 'airU':
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
                last = airUClient.query('SELECT LAST(Latitude),"SensorModel" FROM ' +
                                        config['airu_lat_measurement'] + ' WHERE ID=\'' + anID + '\' AND time >= \'' +
                                        initialDate + '\' AND time <= \'' + anEndDate + '\';')
                last = list(last.get_points())[0]
                senModel = last['SensorModel']
                lat = last['last']

                last = airUClient.query('SELECT LAST(Longitude),"SensorModel" FROM ' +
                                        config['airu_long_measurement'] + ' WHERE ID=\'' + anID + '\' AND time >= \'' +
                                        initialDate + '\' AND time <= \'' + anEndDate + '\';')
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

        if sensorSource in ['PurpleAir', 'DAQ']:
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
                        for i in range(min(tPartsNT, nt - nres)):
                            data.append([None])
                        t = datetime.strptime(initialDate, '%Y-%m-%dT%H:%M:%SZ') - timedelta(hours=7)
                        et = datetime.strptime(anEndDate, '%Y-%m-%dT%H:%M:%SZ') - timedelta(hours=7)
                        while(t < et):
                            times += [t]
                            t += timedelta(seconds=binFreq)
                    else:
                        for row in result:
                            t = datetime.strptime(row['time'], '%Y-%m-%dT%H:%M:%SZ') - timedelta(hours=7)
                            times += [t]
                            data.append([row['mean']])
                else:
                    if not result:
                        for i in range(min(tPartsNT, nt - nres)):
                            data[i + nres] += [None]
                    else:
                        for i in range(len(result)):
                            data[i + nres] += [result[i]['mean']]

        if sensorSource == 'airU':
            for anID in airUUniqueIDs:
                # print 'SELECT * FROM airQuality WHERE "Sensor Source" = \'Purple Air\' AND time >= ' + initialDate + ' AND time <= ' + anEndDate + ';'
                result = airUClient.query('SELECT MEAN("PM2.5") FROM ' +
                                          config['airu_pm25_measurement'] + ' WHERE time >= \'' + initialDate +
                                          '\' AND time < \'' + anEndDate + '\' AND ID = \'' + anID +
                                          '\' group by time(' + str(binFreq) + 's);')
                result = list(result.get_points())
                if len(pAirUniqueIDs) == 0 and anID == airUUniqueIDs[0]:
                    if not result:
                        for i in range(min(tPartsNT, nt - nres)):
                            data.append([None])
                        t = datetime.strptime(initialDate, '%Y-%m-%dT%H:%M:%SZ') - timedelta(hours=7)
                        et = datetime.strptime(anEndDate, '%Y-%m-%dT%H:%M:%SZ') - timedelta(hours=7)
                        while(t < et):
                            times += [t]
                            t += timedelta(seconds=binFreq)
                    else:
                        for row in result:
                            t = datetime.strptime(row['time'], '%Y-%m-%dT%H:%M:%SZ') - timedelta(hours=7)
                            times += [t]
                            data.append([row['mean']])
                else:
                    if not result:
                        for i in range(min(tPartsNT, nt - nres)):
                            data[i + nres] += [None]
                    else:
                        for i in range(len(result)):
                            data[i + nres] += [result[i]['mean']]

        initialDate = anEndDate
        nres += tPartsNT

    IDs = pAirUniqueIDs + airUUniqueIDs

    return [data, longitudes, latitudes, times, sensorModels, IDs]


def getIDToSensorIDMapping(sensorModels, IDs):
    # get airu IDs to get the mapping ID to sensorID

    airuSensorMacs = []

    for index, aSensorModel in enumerate(sensorModels):
        anID = IDs[index]

        # print(aSensorModel + ' and ' + anID)

        if aSensorModel[0] == 'H' and len(anID) == 12:
            airuSensorMacs.append(anID)

    # get the mapping ID to sensorID, call to aqandu API
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

    # adding batch information to sensorModel
    for index, aSensorModel in enumerate(sensorModels):
        anID = IDs[index]
        if aSensorModel[0] == 'H' and len(anID) == 12:
            theBatch = mappingMACTobatch[anID]
            sensorModels[index] = aSensorModel + '_' + theBatch
        else:
            sensorModels[index] = aSensorModel + '_' + 'NoMapping'

    return [sensorModels, IDs]


def exportDataToCSV(aFileName, IDs, sensorModels, latitudes, longitudes, pm25s, times, extra):

    # Writing the Purple air and the airU sensor IDs with their coordinates and sensor models into the output file
    writeLoggingDataToFile(aFileName, sum([[''], ['ID'], IDs], []))
    writeLoggingDataToFile(aFileName, sum([[''], ['Model'], sensorModels], []))
    writeLoggingDataToFile(aFileName, sum([[''], ['Latitude'], latitudes], []))
    writeLoggingDataToFile(aFileName, sum([['time'], ['Longitude'], longitudes], []))

    if not extra:
        # extra is empty
        for ind, row in enumerate(pm25s):
            writeLoggingDataToFile(aFileName, sum([[times[ind].strftime('%Y-%m-%dT%H:%M:%SZ')], [''], row], []))
    else:
        for ind, row in enumerate(pm25s):
            writeLoggingDataToFile(aFileName, sum([[times[ind].strftime('%Y-%m-%dT%H:%M:%SZ')], [''], row + extra[ind]], []))


if __name__ == "__main__":

    # w
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

    startDateMST = sys.argv[1]
    endDateMST = sys.argv[2]

    startDate = datetime.strptime(startDateMST, '%Y-%m-%d')
    endDate = datetime.strptime(endDateMST, '%Y-%m-%d')

    # converting MST to UTC
    startDate = startDate + timedelta(hours=7)
    endDate = endDate + timedelta(hours=7)

    binFreqT = datetime.strptime(sys.argv[3], '%H:%M:%S')
    binFreq = binFreqT.hour * 3600 + binFreqT.minute * 60 + binFreqT.second

    # which sensor source
    sensorSource = sys.argv[4]

    fileNameWithTimestamp = "queriedData-%s-%d%s-%s_%s.csv" % (sensorSource, binFreq, 's', startDateMST, endDateMST)

    try:
        os.remove(fileNameWithTimestamp)
    except OSError:
        pass

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

    elif sensorSource in ['PurpleAir+airU', 'DAQ', 'airU', 'PurpleAir']:

        data = AQDataQuery(sensorSource, startDate, endDate, binFreq, utahBbox['top'], utahBbox['left'], utahBbox['bottom'], utahBbox['right'])

        pm25 = data[0]
        longitudes = data[1]
        latitudes = data[2]
        times = data[3]
        sensorModels = data[4]
        IDs = data[5]

        # get airu IDs to get the mapping ID to sensorID
        if sensorSource in ['PurpleAir+airU', 'airU']:
            mappingResult = getIDToSensorIDMapping(sensorModels, IDs)

            theIDs = mappingResult[0]
            theSensorModels = mappingResult[1]

        exportDataToCSV(fileNameWithTimestamp, theIDs, theSensorModels, latitudes, longitudes, pm25, times, [])

        print('DONE')

    elif sensorSource == 'all':

        # getting the Purple Air data
        purpleAirData = AQDataQuery('PurpleAir', startDate, endDate, binFreq, utahBbox['top'], utahBbox['left'], utahBbox['bottom'], utahBbox['right'])

        pm25_purpleAir = purpleAirData[0]
        longitudes_purpleAir = purpleAirData[1]
        latitudes_purpleAir = purpleAirData[2]
        times_purpleAir = purpleAirData[3]
        sensorModels_purpleAir = purpleAirData[4]
        IDs_purpleAir = purpleAirData[5]

        # fileName_purpleAir = "queriedData-%s-%d%s-%s_%s.csv" % ('PurpleAir', binFreq, 's', startDateMST, endDateMST)
        # exportDataToCSV(fileName_purpleAir, IDs_purpleAir, sensorModels_purpleAir, latitudes_purpleAir, longitudes_purpleAir, pm25_purpleAir, times_purpleAir, [])

        # getting the Purple Air, airUdata
        airuData = AQDataQuery('airU', startDate, endDate, binFreq, utahBbox['top'], utahBbox['left'], utahBbox['bottom'], utahBbox['right'])

        pm25_airU = airuData[0]
        longitudes_airU = airuData[1]
        latitudes_airU = airuData[2]
        times_airU = airuData[3]
        sensorModels_airU = airuData[4]
        IDs_airU = airuData[5]

        mappingResult = getIDToSensorIDMapping(sensorModels_airU, IDs_airU)

        theIDs_airU = mappingResult[0]
        theSensorModels_airU = mappingResult[1]

        # fileName_airu = "queriedData-%s-%d%s-%s_%s.csv" % ('airU', binFreq, 's', startDateMST, endDateMST)
        # exportDataToCSV(fileName_airu, theIDs_airU, theSensorModels_airU, latitudes_airU, longitudes_airU, pm25_airU, times_airU, [])

        # getting the DAQ data
        daqData = AQDataQuery('DAQ', startDate, endDate, 3600, utahBbox['top'], utahBbox['left'], utahBbox['bottom'], utahBbox['right'])

        pm25_daq = daqData[0]
        longitudes_daq = daqData[1]
        latitudes_daq = daqData[2]
        times_daq = daqData[3]
        sensorModels_daq = daqData[4]
        IDs_daq = daqData[5]

        # change the sensorModel of DAQ sensors to 'DAQ'
        for idx, aModel in enumerate(sensorModels_daq):
            sensorModels_daq[idx] = 'DAQ'

        # remove whitespaces for the ID
        for idx, anID in enumerate(IDs_daq):
            IDs_daq[idx] = anID.replace(" ", "")

        # fileName_daq = "queriedData-%s-%d%s-%s_%s.csv" % ('airU', binFreq, 's', startDateMST, endDateMST)
        # exportDataToCSV(fileName_daq, IDs_daq, sensorModels_daq, latitudes_daq, longitudes_daq, pm25_daq, times_daq, [])

        # print(pd.Series(pm25_purpleAir[0:10], index=times_purpleAir[0:10]))
        # print(pd.Series(pm25_airU[0:10], index=times_airU[0:10]))

        # align purpleAir and airu
        purpleAir_aligned, airU_aligned = pd.Series(pm25_purpleAir, index=times_purpleAir).align(pd.Series(pm25_airU, index=times_airU), join='outer', axis=0, method='ffill')

        purpleAir_aligned_list = purpleAir_aligned.tolist()
        airU_aligned_list = airU_aligned.tolist()

        purpleAir_airU = []
        for idx, row in enumerate(purpleAir_aligned_list):
            purpleAir_airU.append(sum([row, airU_aligned_list[idx]], []))

        # align purpleAir + airu and daq
        purpleAirAirU_aligned, daq_aligned = pd.Series(purpleAir_airU, index=times_purpleAir).align(pd.Series(pm25_daq, index=times_daq), join='outer', axis=0, method='ffill')

        purpleAirAirU_aligned_list = purpleAirAirU_aligned.tolist()
        daq_aligned_list = daq_aligned.tolist()

        # concatenate the different sensor source data
        IDs = IDs_purpleAir + IDs_airU + IDs_daq
        sensorModels = sensorModels_purpleAir + sensorModels_airU + sensorModels_daq
        latitudes = latitudes_purpleAir + latitudes_airU + latitudes_daq
        longitudes = longitudes_purpleAir + longitudes_airU + longitudes_daq

        exportDataToCSV(fileNameWithTimestamp, IDs, sensorModels, latitudes, longitudes, purpleAir_airU, times_purpleAir, daq_aligned_list)

        print('DONE')

    else:
        print('Something is wrong with the sensorSource')
