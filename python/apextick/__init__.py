"""Official Python client for the ApexTick market data API.

>>> from apextick import ApexTickClient, Ticker
>>> client = ApexTickClient()  # reads APEXTICK_API_KEY
>>> client.quote(["AAPL", "MSFT", "NVDA"])
>>> Ticker("SPY").options_chain(contract_type="call")
"""

from ._version import __version__
from .client import (
    DEFAULT_BASE_URL,
    DEFAULT_INDICATORS,
    MAX_QUOTE_SYMBOLS,
    ApexTickAPIError,
    ApexTickClient,
    ApexTickConnectionError,
    Ticker,
    to_dataframe,
)

__all__ = [
    "__version__",
    "ApexTickAPIError",
    "ApexTickClient",
    "ApexTickConnectionError",
    "DEFAULT_BASE_URL",
    "DEFAULT_INDICATORS",
    "MAX_QUOTE_SYMBOLS",
    "Ticker",
    "to_dataframe",
]
