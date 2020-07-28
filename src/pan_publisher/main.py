import falcon
from falcon_cors import CORS
from loguru import logger

from pan_publisher.api import AnnotationResource
from pan_publisher.middleware import DatabaseSessionManager, RequireJSON
from pan_publisher.repository.annotations import AnnotationsRepository
from pan_publisher.repository.database import db_session, init_session
from pan_publisher.utils.pagination import PaginationMiddleware

import logging
logging.basicConfig(level=logging.DEBUG)


class PublisherAPI(falcon.API):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info("API Server is starting")

        annotations_repository = AnnotationsRepository(db_session)

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
        self.add_route("/annotations/", AnnotationResource(annotations_repository))
        self.add_route(
            "/annotations/{annotation_id}", AnnotationResource(annotations_repository)
        )


init_session()
# public_cors = CORS(allow_all_origins=True)
middleware = [
    RequireJSON(),
    # public_cors.middleware,
    # TokenAuthMiddleware(db_session),
    DatabaseSessionManager(db_session),
    PaginationMiddleware(),
]
application = PublisherAPI(middleware=middleware, cors_enable=True)


if __name__ == "__main__":
    from wsgiref import simple_server

    httpd = simple_server.make_server("127.0.0.1", 5000, application)
    httpd.serve_forever()
