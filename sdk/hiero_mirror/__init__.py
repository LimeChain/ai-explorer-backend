"""Hiero Mirror Node Python SDK.

A Python SDK for interacting with the Hiero Mirror Node REST API.

Example:
    >>> from hiero_mirror import MirrorNodeClient
    >>> client = MirrorNodeClient.for_testnet()
    >>> accounts = client.get_accounts(limit=10)
    >>> print(f"Found {len(accounts.accounts)} accounts")
"""

__version__ = "0.134.0"
__author__ = "Hiero Mirror Node Team"
__email__ = "mirrornode@hedera.com"
__license__ = "Apache-2.0"

from .client import MirrorNodeClient
from .async_client import AsyncMirrorNodeClient
from .exceptions import (
    MirrorNodeException,
    NotFoundError,
    BadRequestError,
    ServiceUnavailableError,
    TooManyRequestsError,
    ValidationError,
)
from .models import *
from .utils import *

__all__ = [
    # Version info
    "__version__",
    "__author__",
    "__email__",
    "__license__",
    # Main client classes
    "MirrorNodeClient",
    "AsyncMirrorNodeClient",
    # Exceptions
    "MirrorNodeException",
    "NotFoundError",
    "BadRequestError",
    "ServiceUnavailableError",
    "TooManyRequestsError",
    "ValidationError",
    # Models (exported from models module)
    # Utils (exported from utils module)
]