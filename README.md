# ApexTick MCP Server (`@apextick/mcp-server`)

[![apextick/apextick-starter-kit MCP server](https://glama.ai/mcp/servers/apextick/apextick-starter-kit/badges/score.svg)](https://glama.ai/mcp/servers/apextick/apextick-starter-kit)

Official Model Context Protocol (MCP) server for **[ApexTick](https://apextick.com)** (`https://docs.apextick.com/mcp`), built on `@modelcontextprotocol/sdk`.

Provides AI agents (Claude Desktop, Claude Code, Cursor, Windsurf, OpenCode) with low-latency access to **66,400+ global equities, ETFs, FX pairs, and cryptocurrencies**, valuation multiples, technical indicators (`RSI14`, `MACD`, `SMA20/50/200`, `ATR14`, `volatility30`), earnings surprise context, GICS sector movers, and options implied volatility screening.

## Tools Implemented (`src/index.mjs`)

1. **`get_quote`**: Consolidated quote for one ticker (price, change, % change, 52-week range, abbreviated volume, and timestamp).
2. **`analyze_ticker`**: Concurrent quote + fundamentals snapshot (session range position, gap %, distance from 52-week high, and P/E, P/B, P/S, TTM Revenue, EPS, ROE, dividend yield).
3. **`explain_price_move`**: Correlates session price move with technical indicators (`RSI14`, `SMA20/50/200`, `MACD`, `ATR14`) and recent/upcoming earnings surprises.
4. **`get_watchlist_brief`**: Batched quote table for up to 20 symbols in a single request.
5. **`screen_market`**: Cross-market discovery screener returning top gainers, losers, volume leaders (with optional GICS `sector` and `min_market_cap` filters), and liquid high-IV options underlyings.
6. **`get_options_chain`**: Option chain, expiration dates, and Black-Scholes Greeks (`delta`, `gamma`, `theta`, `vega`, `rho`) lookup for an underlying ticker.

## Usage

### Option 1: Local Stdio Server (`src/index.mjs` or Docker)

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

### Option 2: Hosted Streamable HTTP Endpoint (`https://api.apextick.com/mcp`)

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

## Additional Resources in This Repository

* `excel/ApexTick-Starter-and-Test-Suite.xlsx` — 6-tab Excel dynamic-array starter workbook (`=APEXTICK.QUOTE`, `=APEXTICK.STREAM`, `=APEXTICK.OPTIONS.CHAIN`).
* `examples/python/quickstart.py` & `examples/javascript/quickstart.mjs` — Direct REST API examples.

## API Key

Get a free Hobbyist API key (500 requests/day, no credit card required) at **[https://dash.apextick.com/register](https://dash.apextick.com/register)**.
