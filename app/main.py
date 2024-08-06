
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from mangum import Mangum
from rich.logging import RichHandler
from gradioapp import run
import os

import logging

# Setup logging
logging_level = (os.environ.get("LOG_LEVEL") or "NOTSET").upper()
logging.basicConfig(
    level=logging_level, format="%(message)s", datefmt="[%X]", handlers=[RichHandler()]
)

logger = logging.getLogger()
logger.setLevel(logging_level)

app = FastAPI()

#app.mount("/static", StaticFiles(directory="static"), name="static")

app = run(app)
#handler = Mangum(app)


def handler(event, context):
    """Lambda handler."""
    
    print("Event: ", event)
    print("Context: ", context)

    asgi_handler = Mangum(app)
    return asgi_handler(event, context)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8081)