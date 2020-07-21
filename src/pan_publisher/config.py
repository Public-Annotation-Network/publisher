import os


class ConfigurationError(Exception):
    pass


SERVICE_NAME = os.environ.get("SERVICE_NAME", "PAN Publisher API")
SECRET_KEY = os.environ.get("SECRET_KEY")
if SECRET_KEY is None:
    raise ConfigurationError("Please specify a secret key")

try:
    TOKEN_LENGTH = int(os.environ.get("TOKEN_LENGTH", 16))
except ValueError:
    raise ConfigurationError("TOKEN_LENGTH must be a valid integer")

TOKEN_CHARSET = os.environ.get("TOKEN_CHARSET", "".join(map(chr, range(48, 58))))
ENVIRONMENT = os.environ.get("ENVIRONMENT", "production")  # {production,local}

DB_USER = os.environ.get("POSTGRES_USER")
DB_PASSWORD = os.environ.get("POSTGRES_PASSWORD")
DB_HOST = os.environ.get("POSTGRES_HOST")
DB_NAME = os.environ.get("POSTGRES_DB")

if any(map(lambda x: x is None, (DB_USER, DB_PASSWORD, DB_HOST, DB_NAME))):
    raise ConfigurationError("Please specify all required database environment variables")

DB_ECHO = True if os.environ.get("DB_ECHO") == "true" else False
DB_AUTOCOMMIT = True

DATABASE_URL = "postgresql+psycopg2://{user}:{password}@{host}/{database}".format(
    user=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    database=DB_NAME,
)

LOG_LEVEL = os.environ.get("LOG_LEVEL", "info")
