import json

import falcon
import requests
from falcon_cors import CORS
from gql import AIOHTTPTransport, Client, gql
from loguru import logger

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
        # TODO: caching of existing annotations
        output = []
        if not annotation_id:
            # list query
            # TODO: handle transport errors
            limit = req.context["pagination"]["limit"]
            offset = req.context["pagination"]["offset"]
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
                logger.warning(f"Failed to decode annotation CID: {annotation['cid']}")
                continue
            output.append(annotation_data)
        res.body = json.dumps(output)
        if len(output) == 0:
            res.status = falcon.HTTP_NOT_FOUND

    def on_post(self, req, res, annotation_id=None):
        # add annotation to batch
        # init publish workflow if batch full
        pass
