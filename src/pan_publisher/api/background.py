import json
import os
from datetime import datetime
from uuid import uuid4

import celery
import requests
from eth_account.account import SignedMessage
from eth_account.messages import encode_defunct
from loguru import logger
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Query, Session, sessionmaker

from pan_publisher.config import (
    BATCH_SIZE,
    PINATA_API_KEY,
    PINATA_SECRET_API_KEY,
    PUBLISHER_ACCOUNT,
    PUBLISHER_PUBKEY,
    SERVICE_NAME,
)
from pan_publisher.database import engine
from pan_publisher.model.annotation import Annotation

# TODO: Move to config
CELERY_BROKER = os.environ.get("CELERY_BROKER")
CELERY_BACKEND = os.environ.get("CELERY_BACKEND")
TG_ENDPOINT = "https://api.thegraph.com/ipfs/api/v0/add"
PINATA_ENDPOINT = "https://api.pinata.cloud/pinning/pinJSONToIPFS"

app = celery.Celery("tasks", broker=CELERY_BROKER, backend=CELERY_BACKEND)


@app.task
def batch_publish():
    session: Session = sessionmaker(bind=engine)()
    # get all annotations from the DB that aren't published yet
    annotations: Query = session.query(Annotation).filter(Annotation.published == False)
    logger.debug(f"Got {annotations.count()} unpublished annotations")
    if annotations.count() < BATCH_SIZE:
        # if number below threshold, exit
        logger.debug("Skipping batch submission due to insufficient batch size")
        return

    # construct batch JSON with annotation cids
    batch_id = str(uuid4())
    batch = {
        "@context": ["https://pan.network/batch/v1"],
        "type": ["VerifiableCredential", "PANBatchCredential"],
        "issuer": "urn:ethereum:" + PUBLISHER_PUBKEY,
        "issuanceDate": datetime.now().isoformat(),
        "credentialSubject": {
            "id": batch_id,
            "content": [annotation.subject_id for annotation in annotations],
        },
        "proof": {
            "type": "EthereumECDSA",
            "created": datetime.now().isoformat(),
            "proofPurpose": "PANBatch",
            "verificationMethod": "urn:ethereum:messageHash",
        },
    }

    # add batch ID to each annotation (for internal consistency)
    for annotation in annotations:
        annotation.batch_id = batch_id

    # sign batch with publisher private key
    sig: SignedMessage = PUBLISHER_ACCOUNT.sign_message(
        encode_defunct(text=json.dumps(batch, sort_keys=True, separators=(",", ":")))
    )
    batch["proof"]["jws"] = sig.signature.hex()

    # publish and pin batch claim on IPFS (TheGraph and Pinata)
    logger.debug("Adding and pinning annotation to IPFS")
    response = requests.post(
        PINATA_ENDPOINT,
        headers={
            "pinata_api_key": PINATA_API_KEY,
            "pinata_secret_api_key": PINATA_SECRET_API_KEY,
        },
        json={
            "pinataMetadata": {
                "name": f"batch-{batch_id}",
                "pan": {
                    "service": SERVICE_NAME,
                    "pubkey": PUBLISHER_PUBKEY,
                    "timestamp": datetime.now().isoformat(),
                },
            },
            "pinataContent": batch,
        },
    )
    if response.status_code != 200:
        logger.error(f"Publishing to Pinata failed with response '{response.text}'")
        return

    try:
        pinata_json = response.json()
    except json.JSONDecodeError:
        logger.error(f"Pinata returned an invalid JSON response: '{response.text}'")
        return

    batch_cid = pinata_json["IpfsHash"]
    logger.debug(f"Published batch at content hash {batch_cid}")

    for annotation in annotations:
        logger.debug(f"Marking annotation {annotation.id} as published")
        annotation.published = True

    # TODO: create tx with batch cid to smart contract registry
    # TODO: publish transaction through Infura to the registry contract

    # store in DB
    try:
        session.commit()
    except SQLAlchemyError as e:
        logger.error(f"Encountered error during database commit: {e}")
        session.rollback()

    return batch_cid  # so we can see the CID in the job dashboard results
