import json
import time

import requests
from aiohttp.client_exceptions import ClientConnectionError
from gql import AIOHTTPTransport, Client, gql
from loguru import logger
from requests.exceptions import ConnectionError, ReadTimeout
from sqlalchemy import desc
from sqlalchemy.orm import Session

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

    def get_subgraph_annotation(self, annotation_id):
        try:
            tg_resp = self.client.execute(
                ANNOTATION_FILTER_QUERY, variable_values={"id": annotation_id}
            )
        except ClientConnectionError:
            logger.warning("The IPFS gateway server dropped the connection - skipping")
            return []
        return self._resolve_subgraph_response(tg_resp)

    def get_by_cid(self, annotation_id):
        annotations = (
            self.session.query(Annotation)
            .filter(Annotation.subject_id == annotation_id)
            .all()
        )
        output = [a.to_dict() for a in annotations]
        return output

    @staticmethod
    def _resolve_subgraph_response(response):
        start_time = time.time()
        output = []
        for annotation in response.get("annotations", []):
            # resolve through IPFS gateway
            try:
                annotation_data = requests.get(
                    f"https://api.thegraph.com/ipfs/api/v0/cat?arg={annotation['cid']}",
                    timeout=1.5,
                ).json()
            except (json.JSONDecodeError, ReadTimeout, ConnectionError):
                logger.warning(f"Failed to decode annotation CID: {annotation['cid']}")
                continue
            output.append(annotation_data)
        logger.info(
            f"Gateway content retrieval took {time.time() - start_time} seconds"
        )
        return output

    def list(self, filter_value, offset, limit):
        output = []
        if filter_value is None:
            logger.debug(
                f"Fetching unpublished annotations from DB with filter={filter_value} limit={limit} offset={offset}"
            )
            annotations = (
                self.session.query(Annotation)
                .order_by(desc(Annotation.issuance_date))
                .offset(offset)
                .limit(limit)
                .all()
            )
            output = [a.to_dict() for a in annotations]
        elif filter_value is not None:
            logger.debug(
                f'Fetching unpublished annotations filtered by "{filter_value}" '
                f"from DB with limit={limit} offset={offset}"
            )
            annotations = (
                self.session.query(Annotation)
                .order_by(desc(Annotation.issuance_date))
                .filter(Annotation.original_content.like(f"%{filter_value}%"))
                .offset(offset)
                .limit(limit)
                .all()
            )
            output = [a.to_dict() for a in annotations]

        return output
