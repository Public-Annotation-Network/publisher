import json
import time
from datetime import datetime, timedelta
from uuid import uuid4

import celery
import dateutil.parser
import requests
import web3
from aiohttp.client_exceptions import ClientConnectionError
from eth_account.account import SignedMessage
from eth_account.messages import encode_defunct
from gql import AIOHTTPTransport, Client, gql
from loguru import logger
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Query, Session, sessionmaker
from sqlalchemy.orm.exc import MultipleResultsFound

from pan_publisher.config import (
    BATCH_SIZE,
    CELERY_BACKEND,
    CELERY_BROKER,
    INFURA_URL,
    PAN_SUBGRAPH,
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
from pan_publisher.repository.annotations import AnnotationsRepository
from pan_publisher.repository.database import engine

app = celery.Celery("tasks", broker=CELERY_BROKER, backend=CELERY_BACKEND)


@app.task
def batch_publish():
    session: Session = sessionmaker(bind=engine)()
    # get all annotations from the DB that aren't published yet
    annotations: Query = session.query(Annotation).filter(Annotation.published == False)
    logger.info(f"Got {annotations.count()} unpublished annotations")
    if annotations.count() < BATCH_SIZE:
        # if number below threshold, exit
        logger.info("Skipping batch submission due to insufficient batch size")
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
    logger.info("Adding and pinning annotation on TheGraph")
    response = requests.post(
        THEGRAPH_IPFS_ENDPOINT, files={"batch.json": json.dumps(batch).encode("utf-8")}
    )
    if response.status_code != 200:
        logger.error(f"Publishing to TheGraph failed with response '{response.text}'")
        return

    try:
        ipfs_hash = response.json()["Hash"]
    except (json.JSONDecodeError, KeyError):
        logger.error(f"TheGraph returned an invalid JSON response: '{response.text}'")
        return

    logger.info("Pinning annotation to Pinata")
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

    logger.info(f"Published batch at content hash {ipfs_hash}")

    for annotation in annotations:
        logger.info(f"Marking annotation {annotation.id} as published")
        annotation.published = True

    logger.info("Starting registry batch transaction")
    w3 = web3.Web3(web3.HTTPProvider(INFURA_URL))
    registry = w3.eth.contract(REGISTRY_CONTRACT, abi=REGISTRY_ABI)
    logger.info("Build raw registry transaction")
    tx = registry.functions.storeCID(ipfs_hash).buildTransaction(
        {
            "nonce": w3.eth.getTransactionCount(PUBLISHER_ACCOUNT.address),
            "chainId": 3,  # 1 = mainnet, 3 = ropsten
            "gas": 25_000,
            "gasPrice": w3.toWei("10", "gwei"),
        }
    )
    logger.info("Signing raw transaction with publisher key")
    signed_tx = w3.eth.account.signTransaction(
        tx, private_key=PUBLISHER_ACCOUNT.privateKey
    )
    logger.info("Sending raw transaction")
    tx_hash = w3.eth.sendRawTransaction(signed_tx.rawTransaction)
    logger.info(f"Published batch to registry in transaction {tx_hash.hex()}")

    # store in DB
    logger.info("Committing batch state changes")
    try:
        session.commit()
    except SQLAlchemyError as e:
        logger.error(f"Encountered error during database commit: {e}")
        session.rollback()

    return ipfs_hash  # so we can see the CID in the job dashboard results


ANNOTATION_LIST_QUERY = gql(
    """
query MyQuery ($first: Int = 10, $skip: Int = 0) {
  annotations (first: $first, skip: $skip) {
    cid
    batchCID
  }
}
"""
)


def fetch_registry_annotations(client, offset, limit):
    start_time = time.time()
    try:
        annotations = client.execute(
            ANNOTATION_LIST_QUERY, variable_values={"first": limit, "skip": offset}
        ).get("annotations", [])
    except ClientConnectionError:
        logger.warning("The IPFS gateway server dropped the connection - skipping")
        return []

    logger.info(
        f"Fetched {len(annotations)} annotations in {time.time() - start_time} seconds"
    )
    return annotations


@app.task
def sync_registry():
    logger.info("Synchronizing with the contract registry")
    session: Session = sessionmaker(bind=engine)()
    repository = AnnotationsRepository(session)
    gql_client = Client(transport=AIOHTTPTransport(url=PAN_SUBGRAPH))

    offset = 0
    limit = 100
    annotations = fetch_registry_annotations(
        client=gql_client, offset=offset, limit=limit
    )

    while annotations:
        # TODO: This takes long - parallelize
        for annotation in annotations:
            # skip if annotation already in DB
            try:
                annotation_exists = (
                    session.query(Annotation)
                    .filter_by(subject_id=annotation["cid"])
                    .scalar()
                )
            except MultipleResultsFound:
                annotation_exists = True
            if annotation_exists is not None:
                continue

            # fetch new annotation from IPFS and create DB object
            try:
                content = repository.get_subgraph_annotation(
                    annotation_id=annotation["cid"]
                )[0]
            except IndexError:
                continue
            # content = repository.get_by_cid(annotation_id=annotation["cid"], published=True)[0]
            annotation_obj = Annotation(
                context=content["@context"],
                credential_type=content["type"],
                issuer=content["issuer"].split(":")[2],
                issuance_date=dateutil.parser.parse(content["issuanceDate"]),
                original_content=content["credentialSubject"]["content"],
                annotation_content=content["credentialSubject"]["annotation"],
                proof_type=content["proof"]["type"],
                proof_date=dateutil.parser.parse(content["proof"]["created"]),
                proof_purpose=content["proof"]["proofPurpose"],
                verification_method=content["proof"]["verificationMethod"],
                proof_jws=content["proof"]["jws"],
                subject_id=annotation["cid"],
                published=True,
            )

            try:
                session.add(annotation_obj)
                session.commit()
            except SQLAlchemyError as e:
                logger.error(f"Encountered error during database commit: {e}")
                session.rollback()

        offset += limit
        annotations = fetch_registry_annotations(
            client=gql_client, offset=offset, limit=limit
        )


app.conf.beat_schedule = {
    "sync-registry": {
        "task": "pan_publisher.api.background.sync_registry",
        "schedule": 300,
        "options": {"expires": 10.0},
    }
}
