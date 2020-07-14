import falcon


class RequireJSON(object):
    def process_request(self, req, resp):
        if not req.client_accepts_json:
            raise falcon.HTTPNotAcceptable(
                "This API only supports responses encoded as JSON."
            )

        if req.method in ("POST", "PUT"):
            if req.content_type is None or "application/json" not in req.content_type:
                raise falcon.HTTPUnsupportedMediaType(
                    "This API only supports requests encoded as JSON."
                )
