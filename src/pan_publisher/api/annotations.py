import json
from copy import deepcopy
from datetime import datetime

import falcon
import requests
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils import remove_0x_prefix
from falcon.media.validators import jsonschema
from falcon_cors import CORS
from loguru import logger
from sqlalchemy.orm import Session

from pan_publisher.api.background import batch_publish
from pan_publisher.config import (
    PINATA_API_KEY,
    PINATA_SECRET_API_KEY,
    THEGRAPH_IPFS_ENDPOINT,
    PINATA_ENDPOINT
)
from pan_publisher.model.annotation import Annotation
from pan_publisher.repository.annotations import AnnotationsRepository

# TODO: Move to config
ANNOTATION_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "properties": {
        "@context": {"type": "array", "items": [{"type": "string"}]},
        "type": {"type": "array", "items": [{"type": "string"}, {"type": "string"}]},
        "issuer": {"type": "string"},
        "issuanceDate": {"type": "string"},
        "credentialSubject": {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "annotation": {"type": "string"},
            },
            "required": ["content", "annotation"],
        },
        "proof": {
            "type": "object",
            "properties": {
                "type": {"type": "string"},
                "created": {"type": "string"},
                "proofPurpose": {"type": "string"},
                "verificationMethod": {"type": "string"},
                "jws": {"type": "string"},
            },
            "required": [
                "type",
                "created",
                "proofPurpose",
                "verificationMethod",
                "jws",
            ],
        },
    },
    "required": [
        "@context",
        "type",
        "issuer",
        "issuanceDate",
        "credentialSubject",
        "proof",
    ],
}


class AnnotationResource:
    cors = CORS(allow_methods_list=["POST", "OPTIONS"])
    auth = {"exempt_methods": ["POST", "OPTIONS"]}

    def __init__(self, annotation_repository: AnnotationsRepository):
        self.annotation_repository = annotation_repository

    def on_get(self, req: falcon.Request, res: falcon.Response, annotation_id=None):
        published = req.get_param_as_bool("published", default=True)
        content_filter = req.get_param("content", default=None)
        limit = req.context["pagination"]["limit"]
        offset = req.context["pagination"]["offset"]

        if annotation_id:
            logger.debug("Fetching data by annotation ID")
            output = self.annotation_repository.get_by_id(
                annotation_id=annotation_id, published=published
            )
        else:
            logger.debug("Fetching annotation list")
            output = self.annotation_repository.list(
                published=published,
                filter_value=content_filter,
                offset=offset,
                limit=limit,
            )

        res.body = json.dumps(output)
        if len(output) == 0:
            res.status = falcon.HTTP_NOT_FOUND

    @jsonschema.validate(req_schema=ANNOTATION_SCHEMA)
    def on_post(self, req: falcon.Request, res: falcon.Response, annotation_id=None):
        logger.debug(f"Received annotation {req.media}")
        message = deepcopy(req.media)
        del message["proof"]["jws"]
        encoded_message = json.dumps(message, separators=(",", ":"))
        signed_message = encode_defunct(text=encoded_message)

        raw_signature = remove_0x_prefix(req.media["proof"]["jws"])
        request_issuer = req.media["issuer"].split(":")[2]
        signature_issuer = Account.recover_message(
            signable_message=signed_message,
            vrs=(
                int(raw_signature[128:130], 16),  # 0x1c or bust
                int(raw_signature[0:64], 16),
                int(raw_signature[64:128], 16),
            ),
        )

        if request_issuer.lower() != signature_issuer.lower():
            logger.debug(
                f"Bad signature issuer: {request_issuer} != {signature_issuer}"
            )
            res.status = falcon.HTTP_BAD_REQUEST
            return

        # create annotation DB object
        annotation = Annotation.from_dict(req.media)
        session: Session = req.context["session"]
        session.add(annotation)

        # publish annotation on IPFS and add subject ID
        logger.debug("Adding and pinning annotation on TheGraph")
        response = requests.post(
            THEGRAPH_IPFS_ENDPOINT,
            files={"batch.json": json.dumps(req.media).encode("utf-8")},
        )
        if response.status_code != 200:
            logger.error(f"Publishing to TheGraph failed with response '{response.text}'")
            res.status = falcon.HTTP_FAILED_DEPENDENCY
            return

        try:
            ipfs_hash = response.json()["Hash"]
        except (json.JSONDecodeError, KeyError):
            logger.error(f"TheGraph returned an invalid JSON response: '{response.text}'")
            res.status = falcon.HTTP_FAILED_DEPENDENCY
            return
        annotation.subject_id = ipfs_hash

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
            res.status = falcon.HTTP_FAILED_DEPENDENCY
            return

        session.add(annotation)
        res.body = json.dumps({"ipfsHash": ipfs_hash})

        # check whether we should publish a new batch
        logger.debug("Running batch check background job")
        batch_publish.delay()
