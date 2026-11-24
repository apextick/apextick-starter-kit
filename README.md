# ApexTick MCP Server (`@apextick/mcp-server`)

[![apextick/apextick-starter-kit MCP server](https://glama.ai/mcp/servers/apextick/apextick-starter-kit/badges/score.svg)](https://glama.ai/mcp/servers/apextick/apextick-starter-kit)
[![ApexTick MCP connector](https://glama.ai/mcp/connectors/com.apextick.api/apex-tick-market-data-and-options-mcp/badges/score.svg)](https://glama.ai/mcp/connectors/com.apextick.api/apex-tick-market-data-and-options-mcp)
[![mcptry](https://mcptry.com/badge/com.apextick/mcp)](https://mcptry.com/servers/com.apextick/mcp)
[![ApexTick Market Data & Options MCP on mcprush](https://mcprush.com/badge/apextick-market-data-options-mcp/score.svg)](https://mcprush.com/to/apextick-market-data-options-mcp?ref=badge)

Official Model Context Protocol (MCP) server for **[ApexTick](https://apextick.com)** (`https://docs.apextick.com/mcp`), built on `@modelcontextprotocol/sdk`.
- **Live NYSE Market Pulse & Alerts Showcase (Telegram):** [`https://t.me/apextick_pulse`](https://t.me/apextick_pulse) (`08:30 ET` Pre-Market & `16:30 ET` Closing Bell briefings + intraday `RVOL20` / `RSI-14` / `MACD` triggers).

Provides AI agents (Claude Desktop, Claude Code, Cursor, Windsurf, OpenCode) with low-latency access to **66,400+ global equities, ETFs, FX pairs, and cryptocurrencies**, valuation multiples, technical indicators (`RSI14`, `MACD`, `SMA20/50/200`, `ATR14`, `volatility30`), earnings surprise context, GICS sector movers, and options implied volatility screening.

![ApexTick MCP Server in Claude Desktop](./assets/demos/demo-claude-mcp.gif)

## Tools Implemented (`src/index.mjs`)

1. **`get_quote`** *(Hobbyist $0+)*: Consolidated quote for one ticker (price, change, % change, 52-week range, abbreviated volume, and timestamp).
2. **`search_tickers`** *(Hobbyist $0+)*: Symbol and instrument directory search across 66,400+ global equities, ETFs, FX pairs, indices, and cryptocurrencies.
3. **`get_watchlist_brief`** *(Hobbyist $0+)*: Batched quote table for up to 20 symbols in a single request.
4. **`get_price_history`** *(Hobbyist $0+)*: Historical OHLCV bars (`1m` to `1mo`) and optional corporate event calendar (earnings surprises, dividend ex-dates, and stock splits on Trader Pro+).
5. **`analyze_ticker`** *(Trader Pro+)*: Concurrent quote + fundamentals snapshot (session range position, gap %, distance from 52-week high, and P/E, P/B, P/S, TTM Revenue, EPS, ROE, dividend yield).
6. **`explain_price_move`** *(Trader Pro+)*: Correlates session price move with technical indicators (`RSI14`, `SMA20/50/200`, `MACD`, `ATR14`) and recent/upcoming earnings surprises.
7. **`get_options_chain`** *(Trader Pro+)*: Option chain, expiration dates, historical option contract daily OHLCV + IV + Greeks (for both active and expired contracts when `strike` is specified), and Black-Scholes Greeks (`delta`, `gamma`, `theta`, `vega`, `rho`) lookup for an underlying ticker.
8. **`screen_market`** *(Quant & Community+)*: Cross-market discovery screener returning top gainers, losers, volume leaders (with optional GICS `sector` and `min_market_cap` filters), and liquid high-IV options underlyings.

## Usage

### Option 1: `npx` straight from this repository (no clone needed)

```json
{
  "mcpServers": {
    "apextick": {
      "command": "npx",
      "args": ["-y", "github:apextick/apextick-starter-kit"],
      "env": {
        "APEXTICK_API_KEY": "dk_your_key_here"
      }
    }
  }
}
```

Check your setup with `npx -y github:apextick/apextick-starter-kit --help` (also `--version`). Requires Node.js 20+ and `git`.

### Option 2: Local Stdio Server (`src/index.mjs` or Docker)

```json
{
  "mcpServers": {
    "apextick": {
      "command": "node",
      "args": ["/path/to/apextick-starter-kit/src/index.mjs"],
      "env": {
        "APEXTICK_API_KEY": "dk_your_key_here"
      }
    }
  }
}
```

### Option 3: Hosted Streamable HTTP Endpoint (`https://api.apextick.com/mcp`)

```json
{
  "mcpServers": {
    "apextick": {
      "url": "https://api.apextick.com/mcp",
      "headers": {
        "apikey": "dk_your_key_here"
      }
    }
  }
}
```

## Python Client (`python/`)

The official `apextick` package for Python 3.9+ uses only the standard library, so it runs anywhere, including Google Colab. Optional pandas helpers come with the `[pandas]` extra.

```bash
pip install "git+https://github.com/apextick/apextick-starter-kit.git#subdirectory=python"
```

```python
from apextick import ApexTickClient, Ticker

client = ApexTickClient()                                   # reads APEXTICK_API_KEY
client.quote(["AAPL", "MSFT", "NVDA", "BTC-USD", "EURUSD=X"])  # up to 50 symbols in one request
client.candles("AAPL", resolution="1d", limit=90)           # OHLCV bars, oldest first
Ticker("SPY", client).options_chain(contract_type="call")   # chain with IV & Greeks (Trader Pro+)
client.options_history("AAPL240621C00200000")               # one contract's daily bars (Trader Pro+)
```

Covers quotes, candles, ticker search, technical indicators, fundamentals, option chains and option contract history, with a `Ticker` facade for quick migration from per-ticker scripts and `ApexTickAPIError` for 401/403/429 responses. See [`python/README.md`](./python/README.md).

## Google Colab Notebooks (`notebooks/`)

| Notebook | What it shows | |
|---|---|---|
| [`01_batched_quotes_and_ohlcv_quickstart.ipynb`](./notebooks/01_batched_quotes_and_ohlcv_quickstart.ipynb) | One 50-symbol quote request instead of a per-ticker loop, daily OHLCV bars, and pre-computed `RSI-14`, `MACD` and `SMA-200` | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/apextick/apextick-starter-kit/blob/main/notebooks/01_batched_quotes_and_ohlcv_quickstart.ipynb) |
| [`02_historical_options_greeks_backtest.ipynb`](./notebooks/02_historical_options_greeks_backtest.ipynb) | Live option chain with IV and Black-Scholes Greeks, contract selection by delta, and a contract's daily OHLCV + IV + delta history for a short-call analysis | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/apextick/apextick-starter-kit/blob/main/notebooks/02_historical_options_greeks_backtest.ipynb) |

Add your key as the Colab secret `APEXTICK_API_KEY` (key icon in the sidebar). Notebook 01 runs on the free Hobbyist plan; option chains and contract history need Trader Pro or above.

## Ready-to-Use Excel Workbooks (`excel/`) & REST Quickstarts

![ApexTick Excel Options Chains & Greeks](./assets/demos/demo-excel-greeks.gif)

All 4 workbooks work natively in both **ApexTick Excel Lite** (`excel.office.com`, Mac, Windows) and **ApexTick Excel Native** (Windows desktop):

* **[`excel/ApexTick-Starter-and-Test-Suite.xlsx`](./excel/ApexTick-Starter-and-Test-Suite.xlsx)** — Complete 6-tab dynamic-array test suite covering all 17 `=APEXTICK.*` worksheet functions (`=APEXTICK.QUOTE`, `=APEXTICK.STREAM`, `=APEXTICK.OPTIONS.CHAIN`, `=APEXTICK.FINANCIALS`, `=APEXTICK.ECO`).
* **[`excel/Covered-Call-Wheel-Tracker.xlsx`](./excel/Covered-Call-Wheel-Tracker.xlsx)** — Covered call & cash-secured put wheel tracker with 50ms batched quotes, technical regime indicators (`RSI14`, `volatility30`, `ATR14`), and liquid options screener (`=APEXTICK.OPTIONS.SCREENER`).
* **[`excel/Options-IV-Greeks-Calculator.xlsx`](./excel/Options-IV-Greeks-Calculator.xlsx)** — Side-by-side Call & Put options chain analyzer (`=APEXTICK.OPTIONS.CHAIN`) with analytical Black-Scholes Greeks (`Delta`, `Gamma`, `Theta`, `Vega`, `Implied Volatility`), plus daily bars for active and expired contracts.
* **[`excel/SP500-Tech-Watchlist-Valuation.xlsx`](./excel/SP500-Tech-Watchlist-Valuation.xlsx)** — 20-symbol S&P 500 & Nasdaq-100 valuation and momentum watchlist (`P/E`, `Sector`, `RSI14`, `SMA200`, `=APEXTICK.FINANCIALS`, `=APEXTICK.ETF.HOLDINGS`).
* `examples/python/quickstart.py` & `examples/javascript/quickstart.mjs` — Direct REST API examples.

## API Key

Get a free Hobbyist API key (500 requests/day, no credit card required) at **[https://dash.apextick.com/register](https://dash.apextick.com/register)**.
