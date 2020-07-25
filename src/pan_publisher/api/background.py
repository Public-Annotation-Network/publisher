import os
from loguru import logger
import celery

CELERY_BROKER = os.environ.get("CELERY_BROKER")
CELERY_BACKEND = os.environ.get("CELERY_BACKEND")

app = celery.Celery("tasks", broker=CELERY_BROKER, backend=CELERY_BACKEND)


@app.task
def batch_publish():
    # TODO: query db for complete batch and publish if full
    # publish workflow:
    # publish and pin batch claim on IPFS
    # generate new batch ID and add to each annotation
    # store in DB
    # add batch with cid to registry contract
    logger.info("Batch processing go brrrrr")
