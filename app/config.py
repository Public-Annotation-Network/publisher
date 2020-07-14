import configparser
import os

SERVICE_NAME = "PAN Publisher API"
SECRET_KEY = "xs4G5ZD9SwNME6nWRfrK_aq6Yb9H8VJpdwCzkTErFPw="
TOKEN_LENGTH = 10
TOKEN_CHARSET = "".join(map(chr, range(48, 58)))

APP_ENV = os.environ.get("APP_ENV") or "local"  # or 'live' to load live
INI_FILE = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "../conf/{}.ini".format(APP_ENV)
)

CONFIG = configparser.ConfigParser()
CONFIG.read(INI_FILE)
POSTGRES = CONFIG["postgres"]
DATABASE_URL = "postgresql+psycopg2://{user}:{password}@{host}/{database}".format(
    user=POSTGRES["user"],
    password=POSTGRES["password"],
    host=POSTGRES["host"],
    database=POSTGRES["database"],
)

DB_ECHO = True if CONFIG["database"]["echo"] == "yes" else False
DB_AUTOCOMMIT = True
LOG_LEVEL = CONFIG["logging"]["level"]
