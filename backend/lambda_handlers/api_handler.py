"""
The only file in this project that AWS actually calls for the API path.
Its whole job is "hand the FastAPI app to Mangum". Mangum translates
API Gateway's event/context shape into the ASGI calls FastAPI expects,
and translates the ASGI response back into what API Gateway wants.

This file stays this thin on purpose: if the API ever needs to run
somewhere that isn't Lambda (a container on EC2, another cloud), only
this file changes - app/main.py never has to know Mangum exists.
"""
from mangum import Mangum

from app.main import app

handler = Mangum(app)
