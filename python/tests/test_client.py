"""Tests for the apextick client against a local HTTP server (standard library only).

Run from python/:  python -m unittest discover -s tests -v
"""

import importlib.util
import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlsplit

# Import the package from this checkout, and keep the source tree free of bytecode caches.
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apextick import (  # noqa: E402
    MAX_QUOTE_SYMBOLS,
    ApexTickAPIError,
    ApexTickClient,
    ApexTickConnectionError,
    Ticker,
    __version__,
    to_dataframe,
)

KEY = "dk_test_key"


def tearDownModule():
    # Importing this module wrote its own bytecode before dont_write_bytecode took effect.
    cache = Path(__file__).resolve().parent / "__pycache__"
    for pyc in cache.glob(Path(__file__).stem + ".*.pyc"):
        pyc.unlink()
    if cache.is_dir() and not any(cache.iterdir()):
        cache.rmdir()


class FakeAPI:
    """Records every request and answers from a per-path table of (status, body, headers)."""

    def __init__(self):
        self.requests = []
        self.routes = {}
        api = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                url = urlsplit(self.path)
                api.requests.append(
                    {
                        "path": url.path,
                        "raw_query": url.query,
                        "query": {k: v[0] for k, v in parse_qs(url.query, keep_blank_values=True).items()},
                        "headers": dict(self.headers),
                    }
                )
                status, body, headers = api.routes.get(url.path, (404, {"error": "Not found"}, {}))
                payload = body if isinstance(body, bytes) else json.dumps(body(api.requests[-1]) if callable(body) else body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                for name, value in headers.items():
                    self.send_header(name, value)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        self.thread.start()

    def route(self, path, body, status=200, headers=None):
        self.routes[path] = (status, body, headers or {})

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def quote_echo(request):
    """Returns one quote per requested symbol, like the API."""
    return {"data": [{"symbol": s, "price": 100.0 + i, "change_percent": 0.5} for i, s in enumerate(request["query"]["symbol"].split(","))]}


BAR = {"date": "2024-06-20", "open": 11.2, "high": 12.5, "low": 10.8, "close": 12.1, "implied_volatility": 0.31,
       "greeks": {"delta": 0.78, "gamma": 0.04, "theta": -0.21, "vega": 0.09}}


class ClientTestCase(unittest.TestCase):
    def setUp(self):
        self.api = FakeAPI()
        self.addCleanup(self.api.close)
        self.client = ApexTickClient(api_key=KEY, base_url=self.api.url + "/", timeout=5)

    @property
    def last(self):
        return self.api.requests[-1]


class TestConfiguration(ClientTestCase):
    def test_sends_api_key_and_json_headers(self):
        self.api.route("/v1/market/quote", quote_echo)
        self.client.quote("AAPL")
        headers = {k.lower(): v for k, v in self.last["headers"].items()}
        self.assertEqual(headers["apikey"], KEY)
        self.assertEqual(headers["accept"], "application/json")
        self.assertEqual(headers["user-agent"], f"apextick-python/{__version__}")

    def test_reads_the_key_from_the_environment(self):
        with mock.patch.dict(os.environ, {"APEXTICK_API_KEY": " dk_from_env "}):
            self.assertEqual(ApexTickClient().api_key, "dk_from_env")

    def test_missing_key_is_a_clear_error(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "APEXTICK_API_KEY"):
                ApexTickClient()
        with self.assertRaises(ValueError):
            ApexTickClient(api_key="  ")

    def test_repr_never_shows_the_key(self):
        self.assertNotIn(KEY, repr(self.client))
        self.assertEqual(self.client.base_url, self.api.url)  # trailing slash removed


class TestQuote(ClientTestCase):
    def setUp(self):
        super().setUp()
        self.api.route("/v1/market/quote", quote_echo)

    def test_normalizes_and_deduplicates_symbols(self):
        rows = self.client.quote(" aapl, MSFT ,aapl,,nvda")
        self.assertEqual(self.last["query"]["symbol"], "AAPL,MSFT,NVDA")
        self.assertEqual([r["symbol"] for r in rows], ["AAPL", "MSFT", "NVDA"])

    def test_query_string_encoding(self):
        self.client.quote(["EURUSD=X", "^GSPC", "BRK-B", "BTC-USD"])
        self.assertEqual(self.last["raw_query"], "symbol=EURUSD%3DX,%5EGSPC,BRK-B,BTC-USD")
        self.assertEqual(self.last["query"]["symbol"], "EURUSD=X,^GSPC,BRK-B,BTC-USD")

    def test_fifty_symbols_use_one_request(self):
        symbols = [f"T{i:02d}" for i in range(MAX_QUOTE_SYMBOLS)]
        rows = self.client.quote(symbols)
        self.assertEqual(len(self.api.requests), 1)
        self.assertEqual(len(rows), 50)
        self.assertEqual(self.last["query"]["symbol"].split(","), symbols)

    def test_longer_lists_are_split_into_batches_of_fifty(self):
        symbols = [f"S{i:03d}" for i in range(120)]
        rows = self.client.quote(symbols)
        sizes = [len(r["query"]["symbol"].split(",")) for r in self.api.requests]
        self.assertEqual(sizes, [50, 50, 20])
        self.assertEqual([r["symbol"] for r in rows], symbols)

    def test_rejects_empty_and_malformed_symbols(self):
        for bad in ("", " , ", ["AAPL", "BAD SYMBOL"], ["AA,PL"]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.client.quote(bad)
        self.assertEqual(self.api.requests, [])


class TestMarketData(ClientTestCase):
    def test_candles_parameters_and_most_recent_limit(self):
        bars = [{"time": f"2024-01-{d:02d}", "close": d} for d in range(1, 31)]
        self.api.route("/v1/market/candles", {"symbol": "AAPL", "resolution": "1d", "data": bars})
        result = self.client.candles("aapl", resolution="1wk", from_date="2024-01-01", to_date="2024-01-31", limit=5)
        self.assertEqual(self.last["query"], {"symbol": "AAPL", "resolution": "1wk", "from": "2024-01-01", "to": "2024-01-31"})
        self.assertEqual([b["close"] for b in result], [26, 27, 28, 29, 30])
        self.assertEqual(len(self.client.candles("AAPL", limit=None)), 30)
        self.assertEqual(self.last["query"], {"symbol": "AAPL", "resolution": "1d"})

    def test_candles_validates_dates_and_limit(self):
        for kwargs in ({"from_date": "01/02/2024"}, {"limit": 0}, {"limit": True}):
            with self.subTest(**kwargs), self.assertRaises(ValueError):
                self.client.candles("AAPL", **kwargs)

    def test_search_tickers_filters_and_limit(self):
        self.api.route("/v1/reference/tickers", {"data": [{"symbol": f"A{i}"} for i in range(20)]})
        results = self.client.search_tickers(" Apple Inc ", asset_class="Equity", exchange="nms", limit=3)
        self.assertEqual(self.last["query"], {"query": "Apple Inc", "asset_class": "equity", "exchange": "NMS"})
        self.assertEqual(self.last["raw_query"], "query=Apple%20Inc&asset_class=equity&exchange=NMS")
        self.assertEqual(len(results), 3)
        with self.assertRaises(ValueError):
            self.client.search_tickers("  ")

    def test_technicals_requests_the_default_indicator_set(self):
        self.api.route("/v1/analytics/indicators", {"symbol": "NVDA", "indicators": {"rsi14": 61.2, "macd14": 1.4, "sma200": 120.5}})
        body = self.client.technicals("nvda")
        self.assertEqual(self.last["path"], "/v1/analytics/indicators")
        self.assertEqual(self.last["query"]["indicators"], "sma20,sma50,sma200,rsi14,macd14,atr14,stoch_k14,volatility30")
        self.assertEqual(body["indicators"]["rsi14"], 61.2)
        self.client.technicals("NVDA", indicators=["RSI14", " sma200 "])
        self.assertEqual(self.last["query"]["indicators"], "rsi14,sma200")

    def test_fundamentals(self):
        self.api.route("/v1/reference/financials/metrics", {"symbol": "MSFT", "pe_ratio": 35.1})
        self.assertEqual(self.client.fundamentals("msft")["pe_ratio"], 35.1)
        self.assertEqual(self.last["query"], {"symbol": "MSFT"})


class TestOptions(ClientTestCase):
    def test_chain_maps_contract_types_and_limits_contracts(self):
        options = [{"occ_symbol": f"SPY   261218C00{500 + i}000", "type": "call"} for i in range(40)]
        self.api.route("/v1/options/chain", {"underlying_symbol": "SPY", "options": options})
        chain = self.client.options_chain("spy", expiration="2026-12-18", contract_type="Call", limit=10)
        self.assertEqual(self.last["query"], {"symbol": "SPY", "expiry": "2026-12-18", "contract": "c"})
        self.assertEqual(len(chain["options"]), 10)
        self.assertEqual(chain["underlying_symbol"], "SPY")
        self.client.options_chain("SPY", contract_type="put")
        self.assertEqual(self.last["query"]["contract"], "p")
        self.assertEqual(len(self.client.options_chain("SPY", contract_type="all", limit=None)["options"]), 40)
        self.assertNotIn("contract", self.last["query"])

    def test_chain_rejects_unknown_contract_types(self):
        with self.assertRaises(ValueError):
            self.client.options_chain("SPY", contract_type="straddle")
        self.assertEqual(self.api.requests, [])

    def test_history_by_occ_contract(self):
        self.api.route("/v1/options/history", {"occ_symbol": "AAPL  240621C00200000", "bars": [BAR]})
        for occ, raw in (
            ("AAPL240621C00200000", "occ_symbol=AAPL240621C00200000"),
            ("aapl  240621c00200000", "occ_symbol=AAPL%20%20240621C00200000"),
            ("F     250117P00012500", "occ_symbol=F%20%20%20%20%20250117P00012500"),
        ):
            with self.subTest(occ=occ):
                result = self.client.options_history(occ, from_date="2024-01-02", to_date="2024-06-21", limit=30)
                self.assertEqual(self.last["raw_query"], f"from=2024-01-02&to=2024-06-21&limit=30&{raw}")
                self.assertNotIn("strike", self.last["query"])
                self.assertEqual(result["bars"][0]["greeks"]["delta"], 0.78)

    def test_history_by_underlying_expiration_type_and_strike(self):
        self.api.route("/v1/options/history", {"bars": [BAR]})
        self.client.options_history("aapl", expiration="2024-06-21", contract_type="put", strike=200)
        self.assertEqual(
            self.last["query"],
            {"limit": "90", "symbol": "AAPL", "expiry": "2024-06-21", "contract": "p", "strike": "200"},
        )
        self.client.options_history("AAPL", expiration="2024-06-21", contract_type="c", strike=202.5)
        self.assertEqual(self.last["query"]["strike"], "202.5")

    def test_history_argument_errors(self):
        cases = [
            {"symbol": "AAPL"},  # no contract terms
            {"symbol": "AAPL", "expiration": "2024-06-21", "strike": 200},  # no type
            {"symbol": "AAPL", "expiration": "2024-06-21", "contract_type": "all", "strike": 200},
            {"symbol": "AAPL", "expiration": "2024-6-21", "contract_type": "call", "strike": 200},
            {"symbol": "AAPL", "expiration": "2024-06-21", "contract_type": "call", "strike": -5},
            {"symbol": "AAPL240621C00200000", "limit": 1001},
            {"symbol": "AAPL      240621C00200000"},  # over-padded: not an OCC contract
        ]
        for kwargs in cases:
            with self.subTest(**kwargs), self.assertRaises(ValueError):
                self.client.options_history(**kwargs)
        self.assertEqual(self.api.requests, [])


class TestTicker(ClientTestCase):
    def test_facade_delegates_with_its_symbol(self):
        self.api.route("/v1/market/quote", quote_echo)
        self.api.route("/v1/market/candles", {"data": [{"close": 1}, {"close": 2}, {"close": 3}]})
        self.api.route("/v1/analytics/indicators", {"indicators": {"rsi14": 55}})
        self.api.route("/v1/reference/financials/metrics", {"pe_ratio": 20})
        self.api.route("/v1/options/chain", {"options": [{"type": "call"}]})
        self.api.route("/v1/options/history", {"bars": [BAR]})

        nvda = Ticker("nvda", self.client)
        self.assertEqual(repr(nvda), "Ticker('NVDA')")
        self.assertEqual(nvda.quote()["symbol"], "NVDA")
        self.assertEqual([b["close"] for b in nvda.history(limit=2)], [2, 3])
        self.assertEqual(nvda.technicals()["indicators"]["rsi14"], 55)
        self.assertEqual(nvda.fundamentals()["pe_ratio"], 20)
        self.assertEqual(nvda.options_chain(contract_type="call")["options"][0]["type"], "call")
        nvda.options_history("2026-12-18", "call", 150)

        calls = [(r["path"], r["query"].get("symbol")) for r in self.api.requests]
        self.assertEqual(
            calls,
            [
                ("/v1/market/quote", "NVDA"),
                ("/v1/market/candles", "NVDA"),
                ("/v1/analytics/indicators", "NVDA"),
                ("/v1/reference/financials/metrics", "NVDA"),
                ("/v1/options/chain", "NVDA"),
                ("/v1/options/history", "NVDA"),
            ],
        )
        self.assertEqual(self.last["query"]["strike"], "150")

    def test_facade_uses_the_environment_key_by_default(self):
        with mock.patch.dict(os.environ, {"APEXTICK_API_KEY": "dk_env"}):
            self.assertEqual(Ticker("AAPL").client.api_key, "dk_env")

    def test_quote_without_data_is_an_error(self):
        self.api.route("/v1/market/quote", {"data": []})
        with self.assertRaises(ApexTickAPIError) as ctx:
            Ticker("ZZZZ", self.client).quote()
        self.assertEqual(ctx.exception.status_code, 404)


class TestErrors(ClientTestCase):
    def test_http_errors_carry_status_and_message(self):
        cases = [
            (401, {"message": "Invalid API key in request"}, {}, "Invalid API key in request", None),
            (403, {"error": "Plan upgrade required for historical options data"}, {}, "Plan upgrade required for historical options data", None),
            (429, {"error": "Daily quota exceeded"}, {"Retry-After": "30"}, "Daily quota exceeded", 30.0),
            (500, b"<html>Bad gateway</html>", {}, "Internal Server Error", None),
        ]
        for status, body, headers, message, retry_after in cases:
            with self.subTest(status=status):
                self.api.route("/v1/market/quote", body, status=status, headers=headers)
                with self.assertRaises(ApexTickAPIError) as ctx:
                    self.client.quote("AAPL")
                err = ctx.exception
                self.assertEqual(err.status_code, status)
                self.assertEqual(err.message, message)
                self.assertEqual(err.retry_after, retry_after)
                self.assertEqual(str(err), f"HTTP {status}: {message}")
                self.assertNotIsInstance(err, ApexTickConnectionError)

    def test_invalid_json_success_body(self):
        self.api.route("/v1/market/quote", b"not json")
        with self.assertRaises(ApexTickAPIError) as ctx:
            self.client.quote("AAPL")
        self.assertEqual(ctx.exception.status_code, 200)

    def test_unreachable_api_is_a_connection_error(self):
        url = self.api.url
        self.api.close()
        client = ApexTickClient(api_key=KEY, base_url=url, timeout=2)
        with self.assertRaises(ApexTickConnectionError) as ctx:
            client.quote("AAPL")
        self.assertEqual(ctx.exception.status_code, 0)
        self.assertIsInstance(ctx.exception, ApexTickAPIError)


class TestDataFrame(unittest.TestCase):
    def test_to_dataframe_without_pandas_explains_the_extra(self):
        with mock.patch.dict(sys.modules, {"pandas": None}):
            with self.assertRaisesRegex(ImportError, r"apextick\[pandas\]"):
                to_dataframe([{"a": 1}])

    @unittest.skipUnless(importlib.util.find_spec("pandas"), "pandas not installed")
    def test_to_dataframe_flattens_greeks(self):
        frame = to_dataframe({"bars": [BAR]}, "bars")
        self.assertEqual(frame.loc[0, "greeks.delta"], 0.78)


if __name__ == "__main__":
    unittest.main()
