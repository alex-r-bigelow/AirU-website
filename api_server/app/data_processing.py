import logging

import pandas as pd

from . import db
from . import utils

LOGGER = logging.getLogger(__name__)


def get_data(site, start, end):
    site, start, end = validate_params(site, start, end)
    LOGGER.info("Requesting data for %s (%s to %s)", site, start, end)

    query = 'SELECT value, entity_id FROM "pm", "ug/m3" WHERE ' \
            'home_id = \'{}\' and time > \'{}\' and ' \
            'time < \'{}\''.format(site, start, end)
    LOGGER.debug("Query: %s", query)

    # Pull data from database
    data = db.query(query)

    if len(data) == 0:
        raise ValueError("No data from {} to {}".format(start, end))

    # Process data
    data = pd.concat([_rows_to_columns(d) for d in data.values()])
    data = data.sort_index()

    return data


def get_events(site, start, end):
    site, start, end = validate_params(site, start, end)
    LOGGER.info("Requesting events for %s (%s to %s)", site, start, end)

    query = 'SELECT value FROM event WHERE home_id = \'{}\' ' \
            'and time > \'{}\' and time < \'{}\''.format(
                site, start, end)
    LOGGER.debug("Query: %s", query)

    # Pull data from database
    data = db.query(query)

    if len(data) == 0:
        raise ValueError("No events from {} to {}".format(start, end))

    data = data['event']
    data = data.sort_index()
    return data


def get_data_sites():
    LOGGER.info("Requesting data sites")

    query = 'SHOW TAG VALUES WITH KEY = "home_id"'
    LOGGER.debug("Query: %s", query)

    data = db.query(query)
    data_sites = set([x['value'] for measurement in data for x in measurement])

    return data_sites


def get_vendors():
    return utils.read_json("assets/vendors.json")


def validate_params(site, start, end):
    # These calls will raise exceptions if a problem occurs
    site = utils.validate_data_site(site, get_data_sites())
    start = utils.validate_date(start)
    end = utils.validate_date(end)

    return site, start, end


def _rows_to_columns(data):
    def combine_rows(name, data):
        time = data.ix[0].name
        values = {m: v for m, v in zip(data.measurement, data.value)}

        # Delete keys if they exist because they serve no purpose
        values.pop('updated', None)
        values.pop('sequence', None)

        # For older data that doesn't have vendor information
        if 'vendor' not in values:
            values['vendor'] = 'dylos' if 'monitor' in name else 'airu'

        return {**values, "monitor": name, "time": time}

    # Split entity id
    data['monitor'], data['measurement'] = zip(
        *data['entity_id'].str.rsplit('_', 1).tolist())
    data = data.drop('entity_id', 1)

    # Group measurements from the same sensor at the same time
    group = data.groupby(['monitor', pd.Grouper(freq='15S')], sort=False)

    data = pd.DataFrame([combine_rows(name, data)
                         for (name, time), data in group])
    data = data.set_index('time').sort_index()

    # Fill in missing data
    data = data.groupby('monitor', sort=False).ffill()
    data = data.where((pd.notnull(data)), None)

    data = data.sort_index()

    # Put all values into list
    columns = data.columns.tolist()
    columns.remove('monitor')  # We don't want to group
    columns.remove('vendor')  # We don't want to group
    columns = sorted(columns)
    data['values'] = data[columns].values.tolist()
    data = data.drop(columns, 1)

    return data
