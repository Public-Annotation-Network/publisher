from secrets import compare_digest
from uuid import uuid4

from sqlalchemy import Column, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from app.config import TOKEN_LENGTH
from app.model import Base


class User(Base):
    id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid4, unique=True, nullable=False
    )
    username = Column(String(20), nullable=False, unique=True)
    password = Column(String(80), nullable=False)
    token = Column(String(255), nullable=True)

    sid = Column(String(TOKEN_LENGTH), nullable=True)

    def __repr__(self):
        return "<User(name='%s', token='%s')>" % (self.username, self.token)

    @classmethod
    def get_id(cls):
        return User.id

    @classmethod
    def find_by_token(cls, session, token):
        result = None
        collision = False
        for user in session.query(User).all():
            if user.token is not None and compare_digest(
                user.token.encode("utf-8"), token.encode("utf-8")
            ):
                if result is not None:
                    collision = True
                    continue
                result = user

        if not collision and result is not None:
            return result

    @classmethod
    def find_by_username(cls, session, username):
        return session.query(User).filter(User.username == username).one()

    FIELDS = {"username": str, "token": str}
    FIELDS.update(Base.FIELDS)
