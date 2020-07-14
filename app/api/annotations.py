import json

import falcon
from falcon_cors import CORS

from app.model import User


class AnnotationResource:
    cors = CORS(allow_methods_list=["POST", "OPTIONS"])
    auth = {"exempt_methods": ["POST", "OPTIONS"]}

    def on_get(self, req, res, annotation_id=None):
        # fetch annotation(s) from the graph
        pass

    def on_post(self, req, res, annotation_id=None):
        # add annotation to batch
        # init publish workflow if batch full
        pass
