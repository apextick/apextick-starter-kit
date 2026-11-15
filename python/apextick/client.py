"""ApexTick REST API client built on the Python standard library."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

from ._version import __version__

DEFAULT_BASE_URL = "https://api.apextick.com"

#: Symbols accepted by one ``/v1/market/quote`` request; larger lists are split into batches.
MAX_QUOTE_SYMBOLS = 50

#: Indicators requested by :meth:`ApexTickClient.technicals` unless others are given.
DEFAULT_INDICATORS = ("sma20", "sma50", "sma200", "rsi14", "macd14", "atr14", "stoch_k14", "volatility30")

# Standard market notation: AAPL, BRK-B, ^GSPC, EURUSD=X, BTC-USD. Commas are excluded so a
# symbol can never alter a batched request.
_SYMBOL_RE = re.compile(r"^[A-Z0-9^][A-Z0-9.\-=^]{0,23}$")

# A padded (21 characters) or unpadded OCC contract: root, YYMMDD, C or P, strike x 1000.
_OCC_RE = re.compile(r"^(?=.{16,21}$)[A-Z0-9.\-]{1,6}\s*\d{6}[CP]\d{8}$")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_CONTRACT_TYPES = {"call": "c", "c": "c", "calls": "c", "put": "p", "p": "p", "puts": "p"}

SymbolsArg = Union[str, Sequence[str]]


class ApexTickAPIError(Exception):
    """An error response from the API, such as 401 (bad key), 403 (plan) or 429 (rate limit)."""

    def __init__(self, status_code: int, message: str, retry_after: Optional[float] = None) -> None:
        super().__init__(f"HTTP {status_code}: {message}" if status_code else message)
        self.status_code = status_code
        self.message = message
        #: Seconds to wait before retrying, when a 429 response says so.
        self.retry_after = retry_after


class ApexTickConnectionError(ApexTickAPIError):
    """The API could not be reached (network failure or timeout); ``status_code`` is 0."""

    def __init__(self, message: str) -> None:
        super().__init__(0, message)


def _symbol(raw: str) -> str:
    sym = str(raw or "").strip().upper()
    if not _SYMBOL_RE.match(sym):
        raise ValueError(f"invalid symbol {raw!r}: use standard market notation such as AAPL, BRK-B or BTC-USD")
    return sym


def _symbols(symbols: SymbolsArg) -> List[str]:
    """Normalizes "aapl, msft" or ["AAPL", "MSFT"] to unique upper-case symbols, keeping order."""
    parts: Iterable[str] = symbols.split(",") if isinstance(symbols, str) else symbols
    seen: Dict[str, None] = {}
    for part in parts:
        if str(part).strip():
            seen.setdefault(_symbol(part), None)
    if not seen:
        raise ValueError("at least one symbol is required")
    return list(seen)


def _date(value: Optional[str], name: str) -> Optional[str]:
    if value is None or value == "":
        return None
    if not _DATE_RE.match(str(value)):
        raise ValueError(f"{name} must be a YYYY-MM-DD date, got {value!r}")
    return str(value)


def _contract(contract_type: Optional[str], required: bool) -> Optional[str]:
    """Maps call/put spellings to the API's c/p; None or "all" means both sides."""
    key = str(contract_type or "").strip().lower()
    if key in ("", "all", "both"):
        if required:
            raise ValueError("contract_type must be 'call' or 'put' for a single contract")
        return None
    if key not in _CONTRACT_TYPES:
        raise ValueError(f"contract_type must be 'call', 'put' or 'all', got {contract_type!r}")
    return _CONTRACT_TYPES[key]


def _positive_int(value: Optional[int], name: str, maximum: Optional[int] = None) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or (maximum is not None and value > maximum):
        bound = f"between 1 and {maximum}" if maximum else "a positive integer"
        raise ValueError(f"{name} must be {bound}, got {value!r}")
    return value


def _strike(strike: float) -> str:
    value = float(strike)
    if value <= 0:
        raise ValueError(f"strike must be positive, got {strike!r}")
    return str(int(value)) if value.is_integer() else repr(value)


class ApexTickClient:
    """Client for the ApexTick REST API.

    >>> client = ApexTickClient()            # reads APEXTICK_API_KEY
    >>> client.quote(["AAPL", "MSFT", "NVDA"])

    Each method call is one request against your daily quota, except :meth:`quote`
    with more than 50 symbols, which sends one request per 50 symbols.
    """

    def __init__(self, api_key: Optional[str] = None, base_url: str = DEFAULT_BASE_URL, timeout: float = 10.0) -> None:
        key = api_key if api_key is not None else os.environ.get("APEXTICK_API_KEY", "")
        if not key or not key.strip():
            raise ValueError(
                "An API key is required: pass api_key=... or set the APEXTICK_API_KEY environment variable. "
                "Get a free key at https://dash.apextick.com/register"
            )
        self.api_key = key.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def __repr__(self) -> str:
        # Never include the key, which would leak into logs and notebook outputs.
        return f"ApexTickClient(base_url={self.base_url!r})"

    # ------------------------------------------------------------------ transport

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        query = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
        url = f"{self.base_url}{path}"
        if query:
            # Commas stay readable in symbol lists; everything else is percent-encoded.
            url += "?" + urllib.parse.urlencode(query, safe=",", quote_via=urllib.parse.quote)
        request = urllib.request.Request(
            url,
            headers={
                "apikey": self.api_key,
                "Accept": "application/json",
                "User-Agent": f"apextick-python/{__version__}",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                status, raw = response.status, response.read()
        except urllib.error.HTTPError as err:
            raise self._api_error(err) from None
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            reason = getattr(err, "reason", err)
            raise ApexTickConnectionError(f"Could not reach {self.base_url}: {reason}") from None
        try:
            return json.loads(raw.decode("utf-8"))
        except ValueError:
            raise ApexTickAPIError(status, "The API returned a response that is not valid JSON") from None

    @staticmethod
    def _api_error(err: urllib.error.HTTPError) -> ApexTickAPIError:
        message = err.reason or "Request failed"
        try:
            body = json.loads(err.read().decode("utf-8"))
            if isinstance(body, dict):
                message = body.get("error") or body.get("message") or message
        except (ValueError, OSError):
            pass
        retry_after = None
        header = err.headers.get("Retry-After") if err.headers else None
        if header:
            try:
                retry_after = float(header)
            except ValueError:
                pass
        return ApexTickAPIError(err.code, str(message), retry_after)

    # ------------------------------------------------------------------ market data

    def quote(self, symbols: SymbolsArg) -> List[Dict[str, Any]]:
        """Latest quotes (``GET /v1/market/quote``).

        ``symbols`` is ``"AAPL"``, ``"AAPL,MSFT"`` or a list. Up to 50 symbols go in one
        request; longer lists are split into batches of 50 and the results concatenated.
        """
        syms = _symbols(symbols)
        rows: List[Dict[str, Any]] = []
        for start in range(0, len(syms), MAX_QUOTE_SYMBOLS):
            batch = syms[start : start + MAX_QUOTE_SYMBOLS]
            rows.extend(self._get("/v1/market/quote", {"symbol": ",".join(batch)}).get("data") or [])
        return rows

    def candles(
        self,
        symbol: str,
        resolution: str = "1d",
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: Optional[int] = 30,
    ) -> List[Dict[str, Any]]:
        """OHLCV bars, oldest first (``GET /v1/market/candles``).

        ``resolution`` is one of 1m, 5m, 15m, 30m, 1h, 1d, 1wk or 1mo. ``limit`` keeps the
        most recent bars; pass ``None`` for every bar in the window. History depth
        depends on your plan.
        """
        limit = _positive_int(limit, "limit")
        body = self._get(
            "/v1/market/candles",
            {
                "symbol": _symbol(symbol),
                "resolution": resolution,
                "from": _date(from_date, "from_date"),
                "to": _date(to_date, "to_date"),
            },
        )
        bars = body.get("data") or []
        return bars[-limit:] if limit else bars

    def search_tickers(
        self,
        query: str,
        asset_class: Optional[str] = None,
        exchange: Optional[str] = None,
        limit: Optional[int] = 10,
    ) -> List[Dict[str, Any]]:
        """Instrument search by name or symbol (``GET /v1/reference/tickers``).

        ``asset_class`` is equity, etf, fx, crypto or index; ``exchange`` is a code such as
        NMS. Filters require Trader Pro or above.
        """
        if not str(query or "").strip():
            raise ValueError("query is required")
        limit = _positive_int(limit, "limit")
        body = self._get(
            "/v1/reference/tickers",
            {
                "query": str(query).strip(),
                "asset_class": asset_class.lower() if asset_class else None,
                "exchange": exchange.upper() if exchange else None,
            },
        )
        results = body.get("data") or []
        return results[:limit] if limit else results

    def technicals(self, symbol: str, indicators: Sequence[str] = DEFAULT_INDICATORS) -> Dict[str, Any]:
        """Pre-computed technical indicators (``GET /v1/analytics/indicators``, Trader Pro+).

        Returns ``{"symbol": ..., "indicators": {"rsi14": ..., "macd14": ..., "sma200": ...}}``.
        Supported indicators: sma20, sma50, sma200, rsi14, macd14, atr14, stoch_k14, volatility30.
        """
        names = [str(i).strip().lower() for i in indicators if str(i).strip()]
        if not names:
            raise ValueError("at least one indicator is required")
        return self._get("/v1/analytics/indicators", {"symbol": _symbol(symbol), "indicators": ",".join(names)})

    def fundamentals(self, symbol: str) -> Dict[str, Any]:
        """Valuation and financial metrics (``GET /v1/reference/financials/metrics``, Trader Pro+):
        market cap, P/E, P/B, P/S, TTM revenue and EPS, margins, ROE, dividend yield."""
        return self._get("/v1/reference/financials/metrics", {"symbol": _symbol(symbol)})

    # ------------------------------------------------------------------ options

    def options_chain(
        self,
        symbol: str,
        expiration: Optional[str] = None,
        contract_type: Optional[str] = None,
        limit: Optional[int] = 25,
    ) -> Dict[str, Any]:
        """Option chain with implied volatility and Black-Scholes Greeks (``GET /v1/options/chain``, Trader Pro+).

        ``contract_type`` is "call", "put" or None for both. ``limit`` keeps the first
        contracts of the chain; pass ``None`` for all of them.
        """
        limit = _positive_int(limit, "limit")
        chain = self._get(
            "/v1/options/chain",
            {
                "symbol": _symbol(symbol),
                "expiry": _date(expiration, "expiration"),
                "contract": _contract(contract_type, required=False),
            },
        )
        if limit and isinstance(chain.get("options"), list):
            chain = {**chain, "options": chain["options"][:limit]}
        return chain

    def options_history(
        self,
        symbol: str,
        expiration: Optional[str] = None,
        contract_type: Optional[str] = None,
        strike: Optional[float] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 90,
    ) -> Dict[str, Any]:
        """Daily bars for one active or expired option contract (``GET /v1/options/history``, Trader Pro+).

        Pass either an OCC contract as ``symbol`` (``"AAPL240621C00200000"`` or the padded
        ``"AAPL  240621C00200000"``), or an underlying with ``expiration``, ``contract_type``
        and ``strike``. Each bar has OHLC, bid/ask, volume, open interest, implied volatility
        and Greeks. ``limit`` (1-1000) keeps the most recent bars. Trader Pro covers the
        trailing 90 days; longer history needs Quant & Community or above.
        """
        params: Dict[str, Any] = {
            "from": _date(from_date, "from_date"),
            "to": _date(to_date, "to_date"),
            "limit": _positive_int(limit, "limit", maximum=1000),
        }
        occ = str(symbol or "").strip().upper()
        if _OCC_RE.match(occ):
            params["occ_symbol"] = occ
        else:
            if expiration is None or strike is None:
                raise ValueError(
                    "pass an OCC contract symbol, or an underlying symbol with expiration, contract_type and strike"
                )
            params.update(
                symbol=_symbol(symbol),
                expiry=_date(expiration, "expiration"),
                contract=_contract(contract_type, required=True),
                strike=_strike(strike),
            )
        return self._get("/v1/options/history", params)


class Ticker:
    """One symbol, for quick migration from per-ticker scripts.

    >>> nvda = Ticker("NVDA")
    >>> nvda.quote()["price"]
    >>> nvda.history(resolution="1d", limit=90)
    """

    def __init__(self, symbol: str, client: Optional[ApexTickClient] = None) -> None:
        self.symbol = _symbol(symbol)
        self.client = client or ApexTickClient()

    def __repr__(self) -> str:
        return f"Ticker({self.symbol!r})"

    def quote(self) -> Dict[str, Any]:
        rows = self.client.quote(self.symbol)
        if not rows:
            raise ApexTickAPIError(404, f"No quote available for {self.symbol}")
        return rows[0]

    def history(
        self,
        resolution: str = "1d",
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: Optional[int] = 30,
    ) -> List[Dict[str, Any]]:
        return self.client.candles(self.symbol, resolution, from_date, to_date, limit)

    def technicals(self, indicators: Sequence[str] = DEFAULT_INDICATORS) -> Dict[str, Any]:
        return self.client.technicals(self.symbol, indicators)

    def fundamentals(self) -> Dict[str, Any]:
        return self.client.fundamentals(self.symbol)

    def options_chain(
        self, expiration: Optional[str] = None, contract_type: Optional[str] = None, limit: Optional[int] = 25
    ) -> Dict[str, Any]:
        return self.client.options_chain(self.symbol, expiration, contract_type, limit)

    def options_history(
        self,
        expiration: str,
        contract_type: str,
        strike: float,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 90,
    ) -> Dict[str, Any]:
        return self.client.options_history(self.symbol, expiration, contract_type, strike, from_date, to_date, limit)


def to_dataframe(records: Union[List[Dict[str, Any]], Dict[str, Any]], key: Optional[str] = None) -> Any:
    """A pandas DataFrame from a list of records, flattening nested fields such as
    ``greeks.delta``. For a response dict, pass the list's key, e.g.
    ``to_dataframe(chain, "options")`` or ``to_dataframe(history, "bars")``.
    Requires ``pip install "apextick[pandas]"``."""
    try:
        import pandas as pd
    except ImportError:
        raise ImportError('to_dataframe needs pandas: pip install "apextick[pandas]"') from None
    rows = records.get(key or "", []) if isinstance(records, dict) else records
    return pd.json_normalize(rows)
