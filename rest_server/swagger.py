from eve_swagger import swagger, add_documentation


class SwaggerWrapper:
    def __init__(self, app):
        self.app = app
        self.app.register_blueprint(swagger)

        self.app.config['SWAGGER_INFO'] = {
            'title': 'My Supercool API',
            'version': '1.0',
            'description': 'an API description',
            'termsOfService': 'my terms of service',
            'contact': {
                'name': 'nicola',
                'url': 'http://nicolaiarocci.com'
            },
            'license': {
                'name': 'BSD',
                'url': 'https://github.com/nicolaiarocci/eve-swagger/blob/master/LICENSE',
            }
        }

        # app.config['SWAGGER_HOST'] = 'http://localhost.com'
