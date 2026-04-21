import os

SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URI")

if os.getenv("MAX_SIZE"):
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_SIZE")) * 1024 * 1024

# Force HTTPS for generated URLs
PREFERRED_URL_SCHEME = "https"

# WSGI middleware to override request scheme for url_for
class ForceSchemeMiddleware:
    def __init__(self, app, scheme='https'):
        self.app = app
        self.scheme = scheme

    def __call__(self, environ, start_response):
        environ['wsgi.url_scheme'] = self.scheme
        return self.app(environ, start_response)
