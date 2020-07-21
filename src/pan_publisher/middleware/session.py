import falcon
import sqlalchemy.orm.scoping as scoping
from loguru import logger
from sqlalchemy.exc import SQLAlchemyError

from pan_publisher import config


class DatabaseSessionManager:
    def __init__(self, db_session):
        self._session_factory = db_session
        self._scoped = isinstance(db_session, scoping.ScopedSession)

    def process_request(self, req, res, resource=None):
        """
        Handle post-processing of the response (after routing).
        """
        req.context["session"] = self._session_factory

    def process_response(self, req, res, resource=None, req_succeeded=None):
        """
        Handle post-processing of the response (after routing).
        """
        if not req.context.get("session"):
            return
        session = req.context["session"]

        if config.DB_AUTOCOMMIT:
            try:
                session.commit()
            except SQLAlchemyError as e:
                logger.warning(f"Encountered error during database commit: {e}")
                session.rollback()
                raise falcon.HTTPBadRequest()

        if self._scoped:
            # remove any database-loaded state from all current objects
            # so that the next access of any attribute, or any query execution will retrieve new state
            session.remove()
        else:
            session.close()
