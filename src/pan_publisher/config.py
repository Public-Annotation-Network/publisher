import os

from eth_account import Account


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

DB_USER = os.environ.get("POSTGRES_USER")
DB_PASSWORD = os.environ.get("POSTGRES_PASSWORD")
DB_HOST = os.environ.get("POSTGRES_HOST")
DB_NAME = os.environ.get("POSTGRES_DB")

if any(map(lambda x: x is None, (DB_USER, DB_PASSWORD, DB_HOST, DB_NAME))):
    raise ConfigurationError(
        "Please specify all required database environment variables"
    )

DB_ECHO = True if os.environ.get("DB_ECHO") == "true" else False
DB_AUTOCOMMIT = True

DATABASE_URL = "postgresql+psycopg2://{user}:{password}@{host}/{database}".format(
    user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME,
)

LOG_LEVEL = os.environ.get("LOG_LEVEL", "info")
PINATA_API_KEY = os.environ.get("PINATA_API_KEY")
PINATA_SECRET_API_KEY = os.environ.get("PINATA_SECRET_API_KEY")
PINATA_ENDPOINT = os.environ.get("PINATA_ENDPOINT")
if not all((PINATA_API_KEY, PINATA_SECRET_API_KEY, PINATA_ENDPOINT)):
    raise ConfigurationError(
        "Pinata API keys and an endpoint are needed to add and pin annotations on IPFS"
    )

PUBLISHER_PRIVKEY = os.environ.get("PUBLISHER_PRIVATE_KEY")
if not PUBLISHER_PRIVKEY:
    raise ConfigurationError("A valid publisher private key is required")
PUBLISHER_ACCOUNT = Account.from_key(PUBLISHER_PRIVKEY)
PUBLISHER_PUBKEY = PUBLISHER_ACCOUNT.address
BATCH_SIZE = 2
REGISTRY_CONTRACT = os.environ.get("REGISTRY_CONTRACT")
if REGISTRY_CONTRACT is None:
    raise ConfigurationError("Please provide a registry contract address")
INFURA_URL = os.environ.get("INFURA_URL")
if INFURA_URL is None:
    raise ConfigurationError("Please provide an Infura endpoint URL")

CELERY_BROKER = os.environ.get("CELERY_BROKER")
CELERY_BACKEND = os.environ.get("CELERY_BACKEND")

if CELERY_BACKEND is None or CELERY_BROKER is None:
    raise ConfigurationError("Missing celery config parameters")

THEGRAPH_IPFS_ENDPOINT = os.environ.get("THEGRAPH_IPFS_ENDPOINT")
if THEGRAPH_IPFS_ENDPOINT is None:
    raise ConfigurationError(
        "Please provide a valid TheGraph endpoint for IPFS publishing and pinning"
    )

REGISTRY_ABI = [
    {
        "inputs": [{"internalType": "string", "name": "cid", "type": "string"}],
        "name": "storeCID",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]
PAN_SUBGRAPH = (
    "https://api.thegraph.com/subgraphs/name/public-annotation-network/subgraph"
)
