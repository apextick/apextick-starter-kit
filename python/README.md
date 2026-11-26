# ApexTick Python Client (`apextick`)

Official Python client for the [ApexTick](https://apextick.com) market data API. It uses only the standard library, so it runs anywhere Python 3.9+ does, including Google Colab.

```bash
pip install apextick
# Optional DataFrame helper:
pip install "apextick[pandas]"
```

Set `APEXTICK_API_KEY` (get a free key at [dash.apextick.com/register](https://dash.apextick.com/register)), then:

```python
from apextick import ApexTickClient, Ticker

client = ApexTickClient()  # reads APEXTICK_API_KEY

# One request for up to 50 symbols, instead of one request per ticker
for q in client.quote(["AAPL", "MSFT", "NVDA", "BTC-USD", "EURUSD=X"]):
    print(q["symbol"], q["price"], q["change_percent"])

bars = client.candles("AAPL", resolution="1d", limit=90)          # OHLCV, oldest first
nvda = Ticker("NVDA", client)                                      # per-symbol facade
nvda.technicals()["indicators"]["rsi14"]                           # Trader Pro+
chain = client.options_chain("SPY", contract_type="call")          # Trader Pro+
history = client.options_history("AAPL240621C00200000")            # one contract's daily bars
```

| Method | Endpoint | Plan |
|---|---|---|
| `quote(symbols)` | `GET /v1/market/quote` (50 symbols per request; longer lists are batched) | Hobbyist ($0)+ |
| `candles(symbol, resolution, from_date, to_date, limit)` | `GET /v1/market/candles` | Hobbyist ($0)+ |
| `search_tickers(query, asset_class, exchange, limit)` | `GET /v1/reference/tickers` | Hobbyist ($0)+ (filters on Trader Pro+) |
| `technicals(symbol, indicators)` | `GET /v1/analytics/indicators` | Trader Pro+ |
| `fundamentals(symbol)` | `GET /v1/reference/financials/metrics` | Trader Pro+ |
| `options_chain(symbol, expiration, contract_type, limit)` | `GET /v1/options/chain` | Trader Pro+ |
| `options_history(symbol, expiration, contract_type, strike, from_date, to_date, limit)` | `GET /v1/options/history` | Trader Pro+ (90 days); longer history on Quant & Community+ |

Errors raise `ApexTickAPIError` with `status_code` (401 invalid key, 403 plan upgrade required, 429 rate limit, with `retry_after` when given) and `message`. Network failures raise `ApexTickConnectionError` (`status_code` 0).

`to_dataframe(records)` turns results into a pandas DataFrame, flattening nested fields such as `greeks.delta`: `to_dataframe(chain, "options")`.

Run the tests (standard library only): `python -m unittest discover -s tests -v`
