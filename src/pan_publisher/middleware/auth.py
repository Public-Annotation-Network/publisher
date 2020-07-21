from secrets import compare_digest

import falcon
from falcon_auth import FalconAuthMiddleware, TokenAuthBackend

from pan_publisher.config import SECRET_KEY, TOKEN_CHARSET, TOKEN_LENGTH
from pan_publisher.model import User
from pan_publisher.utils.auth import AuthManager


class TokenAuthMiddleware(FalconAuthMiddleware):
    def __init__(self, db_session, exempt_routes=None, exempt_methods=None):
        super().__init__(
            backend=TokenAuthBackend(self.user_loader),
            exempt_routes=exempt_routes,
            exempt_methods=exempt_methods,
        )
        self.db_session = db_session
        self.auth_manager = AuthManager(
            secret_key=SECRET_KEY,
            token_charset=TOKEN_CHARSET,
            token_length=TOKEN_LENGTH,
        )

    def user_loader(self, token):
        user = User.find_by_token(self.db_session, token)
        # user does not exist
        if user is None:
            raise falcon.HTTPUnauthorized()

        # sid mismatch
        sid = self.auth_manager.decrypt(token)
        if sid is None or not compare_digest(user.sid.encode("utf-8"), sid):
            raise falcon.HTTPUnauthorized()

        return user
