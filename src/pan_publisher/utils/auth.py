import bcrypt
import shortuuid
from cryptography.fernet import Fernet, InvalidToken


class AuthManager:
    def __init__(self, secret_key, token_charset, token_length):
        self.secret_key = secret_key
        self.fernet_key = Fernet(secret_key)
        self.token_charset = token_charset
        self.token_length = token_length

    def generate_session_id(self):
        return shortuuid.ShortUUID(alphabet=self.token_charset).random(
            self.token_length
        )

    def encrypt(self, data):
        return self.fernet_key.encrypt(data.encode("utf-8"))

    def decrypt(self, data):
        try:
            return self.fernet_key.decrypt(data.encode("utf-8"))
        except InvalidToken:
            return None

    @staticmethod
    def hash_password(password):
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

    @staticmethod
    def verify_password(password, hashed):
        return bcrypt.hashpw(password.encode("utf-8"), hashed) == hashed
