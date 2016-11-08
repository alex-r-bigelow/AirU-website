from datetime import datetime
import json
import logging

import arrow
import pandas as pd
import pytz

LOGGER = logging.getLogger(__name__)


def validate_date(value):
    try:
        return arrow.get(value)
    except arrow.parser.ParserError:
        LOGGER.info("Invalid date: %s", value)
        raise ValueError('Invalid date "{}"'.format(value))


def validate_data_site(value, data_sites):
    if value in data_sites:
        return value
    else:
        LOGGER.info("Invalid data site: %s", value)
        raise ValueError('Invalid data site "{}"'.format(value))


def current_time():
    return datetime.now(tz=pytz.utc)


def read_json(file_name):
    with open(file_name) as f:
        return json.load(f)


def write_json(obj, file_name):
    with open(file_name, 'w') as f:
        return json.dump(obj, f, sort_keys=True, indent=4)


def jsonify_df(*args, **kwargs):
    class DataFrameJSONEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, datetime):
                return obj.isoformat()

            if isinstance(obj, pd.tslib.Timestamp):
                return obj.to_datetime().isoformat()

            if isinstance(obj, pd.DataFrame):
                return obj.to_dict(orient='split')['data']

            return json.JSONEncoder.default(self, obj)

    if args and kwargs:
        raise TypeError(
            'jsonify() behavior undefined when passed both args and kwargs')
    elif len(args) == 1:  # single args are passed directly to dumps()
        data = args[0]
    else:
        data = args or kwargs

    return json.dumps(data, cls=DataFrameJSONEncoder)
