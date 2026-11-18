# Installing the ApexTick MCP Server (for AI agents such as Cline)

ApexTick provides market data tools (quotes, ticker search, price history, watchlist briefs, technical and fundamental snapshots, option chains with Greeks, and a market screener) over the Model Context Protocol.

## 1. Get an API key

The user needs a free ApexTick API key (Hobbyist plan: $0, 500 requests/day, no credit card):

1. Ask the user to sign up at https://dash.apextick.com/register (email, or "Continue with GitHub").
2. The key starts with `dk_` and is shown on the dashboard. Ask the user to paste it; never invent one.

## 2. Add the server (pick one)

### Option A: hosted endpoint (recommended, nothing to install)

Add this entry to `cline_mcp_settings.json`, replacing the key:

```json
{
  "mcpServers": {
    "apextick": {
      "type": "streamableHttp",
      "url": "https://api.apextick.com/mcp",
      "headers": {
        "apikey": "dk_your_key_here"
      },
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

`"type": "streamableHttp"` is required; without it Cline uses the legacy SSE transport.

### Option B: local stdio server (Node.js 20+ and git)

```json
{
  "mcpServers": {
    "apextick": {
      "command": "npx",
      "args": ["-y", "github:apextick/apextick-starter-kit"],
      "env": {
        "APEXTICK_API_KEY": "dk_your_key_here"
      },
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

`npx -y github:apextick/apextick-starter-kit --help` prints usage and confirms Node can fetch and run the server.

## 3. Verify

Call the `get_quote` tool with `{"symbol": "AAPL"}`. A price, change and 52-week range means the setup works.

- `401`: the key is missing or mistyped (check the `apikey` header or `APEXTICK_API_KEY`).
- A tool missing from the list (hosted endpoint) or a `403` plan error (local server): that tool needs a higher plan. The free plan includes `get_quote`, `search_tickers`, `get_watchlist_brief` and `get_price_history`; `analyze_ticker`, `explain_price_move` and `get_options_chain` need Trader Pro, and `screen_market` needs Quant & Community.
- `429`: the daily or per-minute request limit was reached.

Docs: https://docs.apextick.com/mcp · Support: support@apextick.com
