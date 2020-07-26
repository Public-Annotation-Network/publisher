import json
from datetime import datetime
from uuid import uuid4

import celery
import requests
import web3
from eth_account.account import SignedMessage
from eth_account.messages import encode_defunct
from loguru import logger
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Query, Session, sessionmaker

from pan_publisher.config import (
    BATCH_SIZE,
    CELERY_BACKEND,
    CELERY_BROKER,
    INFURA_URL,
    PINATA_API_KEY,
    PINATA_ENDPOINT,
    PINATA_SECRET_API_KEY,
    PUBLISHER_ACCOUNT,
    PUBLISHER_PUBKEY,
    REGISTRY_ABI,
    REGISTRY_CONTRACT,
    THEGRAPH_IPFS_ENDPOINT,
)
from pan_publisher.model.annotation import Annotation
from pan_publisher.repository.database import engine

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
    logger.debug("Adding and pinning annotation on TheGraph")
    response = requests.post(
        THEGRAPH_IPFS_ENDPOINT,
        files={"batch.json": json.dumps(batch).encode("utf-8")},
    )
    if response.status_code != 200:
        logger.error(f"Publishing to TheGraph failed with response '{response.text}'")
        return

    try:
        ipfs_hash = response.json()["Hash"]
    except (json.JSONDecodeError, KeyError):
        logger.error(f"TheGraph returned an invalid JSON response: '{response.text}'")
        return

    logger.debug("Pinning annotation to Pinata")
    response = requests.post(
        PINATA_ENDPOINT,
        headers={
            "pinata_api_key": PINATA_API_KEY,
            "pinata_secret_api_key": PINATA_SECRET_API_KEY,
        },
        json={"hashToPin": ipfs_hash},
    )
    if response.status_code != 200:
        logger.error(f"Pinning on Pinata failed with response '{response.text}'")
        return

    logger.debug(f"Published batch at content hash {ipfs_hash}")

    for annotation in annotations:
        logger.debug(f"Marking annotation {annotation.id} as published")
        annotation.published = True

    logger.debug("Starting registry batch transaction")
    w3 = web3.Web3(web3.HTTPProvider(INFURA_URL))
    registry = w3.eth.contract(REGISTRY_CONTRACT, abi=REGISTRY_ABI)
    logger.debug("Build raw registry transaction")
    tx = registry.functions.storeCID(ipfs_hash).buildTransaction(
        {
            "nonce": w3.eth.getTransactionCount(PUBLISHER_ACCOUNT.address),
            "chainId": 3,  # 1 = mainnet, 3 = ropsten
            "gas": 25_000,
            "gasPrice": w3.toWei("10", "gwei"),
        }
    )
    logger.debug("Signing raw transaction with publisher key")
    signed_tx = w3.eth.account.signTransaction(
        tx, private_key=PUBLISHER_ACCOUNT.privateKey
    )
    logger.debug("Sending raw transaction")
    tx_hash = w3.eth.sendRawTransaction(signed_tx.rawTransaction)
    logger.info(f"Published batch to registry in transaction {tx_hash.hex()}")

    # store in DB
    logger.debug("Committing batch state changes")
    try:
        session.commit()
    except SQLAlchemyError as e:
        logger.error(f"Encountered error during database commit: {e}")
        session.rollback()

    return ipfs_hash  # so we can see the CID in the job dashboard results
