import falcon
from falcon_cors import CORS
from loguru import logger

from app.api import AnnotationResource, LoginResource, LogoutResource, UserResource
from app.config import SECRET_KEY, TOKEN_CHARSET, TOKEN_LENGTH
from app.database import db_session, init_session
from app.middleware import DatabaseSessionManager, RequireJSON, TokenAuthMiddleware
from app.utils.auth import AuthManager
from app.utils.pagination import PaginationMiddleware


class PublisherAPI(falcon.API):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info("API Server is starting")

        # auth_manager = AuthManager(
        #     secret_key=SECRET_KEY,
        #     token_charset=TOKEN_CHARSET,
        #     token_length=TOKEN_LENGTH,
        # )
        #
        # # user management
        # self.add_route("/users/", UserResource(auth_manager))
        # self.add_route("/users/{user_id}", UserResource(auth_manager))
        #
        # # auth
        # self.add_route("/login", LoginResource(auth_manager))
        # self.add_route("/logout", LogoutResource(auth_manager))

        # annotations
        self.add_route("/annotations/", AnnotationResource())
        self.add_route("/annotations/{annotation_id}", AnnotationResource())


init_session()
public_cors = CORS(allow_all_origins=True)
middleware = [
    RequireJSON(),
    public_cors.middleware,
    # TokenAuthMiddleware(db_session),
    DatabaseSessionManager(db_session),
    PaginationMiddleware(),
]
application = PublisherAPI(middleware=middleware)


if __name__ == "__main__":
    from wsgiref import simple_server

    httpd = simple_server.make_server("127.0.0.1", 5000, application)
    httpd.serve_forever()
