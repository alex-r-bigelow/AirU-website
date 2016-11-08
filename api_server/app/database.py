from influxdb import DataFrameClient


class InfluxDB():
    def __init__(self):
        self.client = None

    def init_app(self, app):
        self.client = DataFrameClient(host=app.config['INFLUXDB_HOST'],
                                      port=app.config['INFLUXDB_PORT'],
                                      username=app.config['INFLUXDB_USER'],
                                      password=app.config['INFLUXDB_PASSWORD'],
                                      database=app.config['INFLUXDB_DATABASE'],
                                      ssl=app.config['INFLUXDB_SSL'],
                                      verify_ssl=app.config['INFLUXDB_SSL'])

    def query(self, *args, **kwargs):
        return self.client.query(*args, **kwargs)
