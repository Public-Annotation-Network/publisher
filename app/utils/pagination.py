class PaginationMiddleware:
    def _fetch_and_convert(self, req, name, default):
        value = req.params.get(name, default)
        return int(value)

    def process_request(self, req, resp):
        offset = self._fetch_and_convert(req, name="offset", default=0)
        limit = self._fetch_and_convert(req, name="limit", default=10)
        req.context.setdefault("pagination", {"offset": offset, "limit": limit})
