import json

import falcon
from cerberus import Validator
from loguru import logger
from sqlalchemy.orm.exc import NoResultFound

from pan_publisher.model import User
from pan_publisher.utils.auth import AuthManager

FIELDS = {
    "username": {"type": "string", "required": True, "minlength": 4, "maxlength": 20},
    "password": {
        "type": "string",
        "regex": "[0-9a-zA-Z]\w{3,14}",
        "required": True,
        "minlength": 8,
        "maxlength": 64,
    },
}


def validate_user_create(req, res, resource, params):
    schema = {"username": FIELDS["username"], "password": FIELDS["password"]}

    v = Validator(schema)
    if not v.validate(req.media):
        logger.warning(f"User validation failed with {v.errors}")
        raise falcon.HTTPBadRequest("Invalid user object", v.errors)


class UserResource:
    def __init__(self, auth_manager):
        self.auth_manager = auth_manager

    @falcon.before(validate_user_create)
    def on_post(self, req, res, user_id=None):
        session = req.context["session"]
        user = User()
        user.username = req.media["username"]
        user.password = self.auth_manager.hash_password(req.media["password"]).decode(
            "utf-8"
        )
        user.sid = self.auth_manager.generate_session_id()
        user.token = self.auth_manager.encrypt(user.sid).decode("utf-8")
        session.add(user)
        return falcon.HTTP_CREATED

    def on_get(self, req, res, user_id=None):
        session = req.context["session"]
        if user_id is not None:
            try:
                user_db = User.find_one(session, user_id)
                res.body = json.dumps(user_db.to_dict())
                return falcon.HTTP_OK
            except NoResultFound:
                raise falcon.HTTP_NOT_FOUND
        else:
            limit = req.context["pagination"]["limit"]
            offset = req.context["pagination"]["offset"]
            user_dbs = session.query(User).offset(offset).limit(limit).all()
            if user_dbs:
                obj = [user.to_dict() for user in user_dbs]
                res.body = json.dumps(obj)
            else:
                res.status = falcon.HTTP_NO_CONTENT

    def on_put(self, req, res):
        # reset password
        pass


class LoginResource:
    def __init__(self, auth_manager: AuthManager):
        self.auth_manager = auth_manager

    def on_post(self, req, res):
        user = User.find_by_username(req.context["session"], req.media["username"])
        if self.auth_manager.verify_password(
            req.media["password"], user.password.encode("utf-8")
        ):
            user.sid = self.auth_manager.generate_session_id()
            user.token = self.auth_manager.encrypt(user.sid).decode("utf-8")
            res.body = json.dumps({"token": user.token})
        else:
            raise falcon.HTTP_BAD_REQUEST()


class LogoutResource:
    def __init__(self, auth_manager: AuthManager):
        self.auth_manager = auth_manager

    def on_post(self, req, res):
        user = req.context["user"]
        user.sid = None
        user.token = None
