import json

import requests
from gql import AIOHTTPTransport, Client, gql
from loguru import logger
from sqlalchemy.orm import Session
from requests.exceptions import ReadTimeout, ConnectionError
from pan_publisher.config import PAN_SUBGRAPH
from pan_publisher.model.annotation import Annotation


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

ANNOTATION_CONTENT_FILTER_QUERY = gql(
    """
query MyQuery ($first: Int = 10, $skip: Int = 0, $reference: String) {
  annotations(first: $first , skip: $skip , where: { ref_contains: $reference }) {
    cid
    batchCID
    ref
  }
}
"""
)


class AnnotationsRepository:
    def __init__(self, session: Session):
        self.session = session
        self.client = Client(transport=AIOHTTPTransport(url=PAN_SUBGRAPH))

    def get_by_id(self, annotation_id, published):
        if published:
            # TODO: handle transport errors
            tg_resp = self.client.execute(
                ANNOTATION_FILTER_QUERY, variable_values={"id": annotation_id}
            )
            output = self._resolve_subgraph_response(tg_resp)
        else:
            annotations = (
                self.session.query(Annotation)
                .filter(Annotation.id == annotation_id)
                .all()
            )
            output = [a.to_dict() for a in annotations]
        return output

    def _resolve_subgraph_response(self, response):
        output = []
        for annotation in response.get("annotations", []):
            # resolve through IPFS gateway
            try:
                annotation_data = requests.get(
                    f"https://api.thegraph.com/ipfs/api/v0/cat?arg={annotation['cid']}", timeout=1.5
                ).json()
            except (json.JSONDecodeError, ReadTimeout, ConnectionError):
                logger.warning(f"Failed to decode annotation CID: {annotation['cid']}")
                continue
            output.append(annotation_data)
        return output

    def list(self, published, filter_value, offset, limit):
        output = []
        if published and filter_value is None:
            logger.debug(
                f"Fetching published annotations from subgraph with limit={limit} offset={offset}"
            )
            # TODO: handle transport errors
            tg_resp = self.client.execute(
                ANNOTATION_LIST_QUERY, variable_values={"first": limit, "skip": offset},
            )
            output = self._resolve_subgraph_response(tg_resp)
        elif published and filter_value is not None:
            logger.debug(
                f'Fetching published filtered by "{filter_value}" '
                f"annotations from subgraph with limit={limit} offset={offset}"
            )
            tg_resp = self.client.execute(
                ANNOTATION_CONTENT_FILTER_QUERY,
                variable_values={
                    "first": limit,
                    "skip": offset,
                    "reference": filter_value,
                },
            )
            output = self._resolve_subgraph_response(tg_resp)
        elif not published and filter_value is None:
            logger.debug(
                f"Fetching unpublished annotations from DB with limit={limit} offset={offset}"
            )
            annotations = (
                self.session.query(Annotation).offset(offset).limit(limit).all()
            )
            output = [a.to_dict() for a in annotations]
        elif not published and filter_value is not None:
            logger.debug(
                f'Fetching unpublished annotations filtered by "{filter_value}" '
                f"from DB with limit={limit} offset={offset}"
            )
            annotations = (
                self.session.query(Annotation)
                .filter(Annotation.original_content.like(filter_value))
                .offset(offset)
                .limit(limit)
                .all()
            )
            output = [a.to_dict() for a in annotations]

        return output
