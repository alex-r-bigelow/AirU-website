#!/usr/bin/env python
from eve import Eve
from swagger import SwaggerWrapper
app = Eve()
wrapper = SwaggerWrapper(app)

if __name__ == '__main__':
    app.run()
