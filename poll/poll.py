import sys
import json
from datetime import datetime
from influxdb import InfluxDBClient
from purpleAir import uploadLatestPurpleAirData

TIMESTAMP = datetime.now().isoformat()


def getConfig():
    with open(sys.path[0] + '/../config/config.json', 'r') as configfile:
        return json.loads(configfile.read())
    sys.stderr.write('%s\tProblem reading config file.\n' % TIMESTAMP)
    sys.exit(1)

if __name__ == '__main__':
    config = getConfig()
    client = InfluxDBClient('127.0.0.1', 8086, config['influxdbUsername'], config['influxdbPassword'], 'defaultdb')
    uploadLatestPurpleAirData(client)
    sys.stdout.write('%s\tPolling successful.\n' % TIMESTAMP)
