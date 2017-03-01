import argparse
import datetime
import sys

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Retrieves historical data from Purple Air')
    parser.add_argument('--boundingBox', type=int, dest="boundingBox", nargs="4", default=None,
                        help='''Only include sensors within the latitude and
                                latitudes specified (boundary coordinate order:
                                N E S W). Default behavior includes all sensors''')
    parser.add_argument('--dayZero', type=int, dest="dayZero", nargs="1", default=0,
                        help='''Only collect data as far back as this unix timestamp;
                                default behavior includes all data since Jan 1 1970''')
    parser.add_argument('--requiredFields', type=int, dest="requiredFields", nargs="+", default=['ID'],
                        help='''Don't include data from sensors that are missing
                                this space-delimited list of field names. Default
                                is to include all sensors.''')

    args = parser.parse_args()
    print args
