import json
from copy import deepcopy

import falcon
import requests
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_keys import keys
from eth_utils import remove_0x_prefix
from falcon.media.validators import jsonschema
from falcon_cors import CORS
from gql import AIOHTTPTransport, Client, gql
from loguru import logger

from app.model.annotation import Annotation

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


PAN_SUBGRAPH = (
    "https://api.thegraph.com/subgraphs/name/public-annotation-network/subgraph"
)
ANNOTATION_LIST_QUERY = gql(
    """
{
  annotations(first: $first, skip: $skip) {
    id
    cid
    batchCID
  }
}
"""
)

ANNOTATION_FILTER_QUERY = gql(
    """
{
  annotations( id: $id ) {
    id
    cid
    batchCID
  }
}
"""
)


class AnnotationResource:
    cors = CORS(allow_methods_list=["POST", "OPTIONS"])
    auth = {"exempt_methods": ["POST", "OPTIONS"]}

    def __init__(self):
        transport = AIOHTTPTransport(url=PAN_SUBGRAPH)
        self.client = Client(transport=transport)

    def on_get(self, req: falcon.Request, res: falcon.Response, annotation_id=None):
        session = req.context["session"]
        published = req.get_param_as_bool("published", default=True)
        limit = req.context["pagination"]["limit"]
        offset = req.context["pagination"]["offset"]
        output = []

        if published:
            # TODO: caching of existing annotations
            if not annotation_id:
                # list query
                # TODO: handle transport errors
                tg_resp = self.client.execute(
                    ANNOTATION_LIST_QUERY,
                    variable_values={"first": limit, "skip": offset,},
                )
            else:
                # filter query
                # TODO: handle transport errors
                tg_resp = self.client.execute(
                    ANNOTATION_FILTER_QUERY, variable_values={"id": annotation_id}
                )
            logger.debug(tg_resp)
            # TODO: handle http errors, check schema
            for annotation in tg_resp.get("annotations", []):
                # resolve through IPFS gateway
                try:
                    annotation_data = requests.get(
                        f"https://gateway.ipfs.io/ipfs/{annotation['cid']}"
                    ).json()
                except json.JSONDecodeError:
                    logger.warning(
                        f"Failed to decode annotation CID: {annotation['cid']}"
                    )
                    continue
                output.append(annotation_data)
        else:
            annotations = session.query(Annotation).offset(offset).limit(limit).all()
            for annotation in annotations:
                output.append(annotation.to_dict())
        res.body = json.dumps(output)
        if len(output) == 0:
            res.status = falcon.HTTP_NOT_FOUND

    @jsonschema.validate(req_schema=ANNOTATION_SCHEMA)
    def on_post(self, req: falcon.Request, res: falcon.Response, annotation_id=None):
        logger.debug(f"Received annotation {req.media}")
        message = deepcopy(req.media)
        del message["proof"]["jws"]
        encoded_message = json.dumps(message, sort_keys=True, separators=(",", ":"))
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
            logger.debug(f"Bad signature issuer: {request_issuer} != {signature_issuer}")
            res.status = falcon.HTTP_BAD_REQUEST
            return

        # create annotation DB object
        annotation = Annotation.from_dict(req.media)
        session = req.context["session"]

        # publish annotation on IPFS and add subject ID
        # TODO: return IPFS cid in response

        annotation.subject_id = "Look mom, I'm on IPFS!"
        session.add(annotation)

        # add annotation to batch

        # init publish workflow if batch full

        # publish workflow:
        # send transaction to registry contract
