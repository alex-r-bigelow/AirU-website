class Config:
    DEBUG = False
    TESTING = False


class DevelopmentConfig(Config):
    DEBUG = True

    INFLUXDB_USER = ""
    INFLUXDB_PASSWORD = ""
    INFLUXDB_HOST = ""
    INFLUXDB_PORT = 443
    INFLUXDB_DATABASE = "home_assistant"
    INFLUXDB_SSL = True


class ProductionConfig(Config):
    INFLUXDB_USER = ""
    INFLUXDB_PASSWORD = ""
    INFLUXDB_HOST = "localhost"
    INFLUXDB_PORT = 8086
    INFLUXDB_DATABASE = "home_assistant"
    INFLUXDB_SSL = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
