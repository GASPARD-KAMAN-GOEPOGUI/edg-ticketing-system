import os
import sys

BASE_DIR = os.path.dirname(__file__)
sys.path.insert(0, BASE_DIR)

from a2wsgi import ASGIMiddleware
from api.main import app

application = ASGIMiddleware(app)


# import imp
# import os
# import sys


# sys.path.insert(0, os.path.dirname(__file__))

# wsgi = imp.load_source('wsgi', 'passenger_wsgi.py')
# application = wsgi.application
