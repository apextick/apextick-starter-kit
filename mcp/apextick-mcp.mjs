#!/usr/bin/env node
/**
 * ApexTick Market Data & Options MCP Server (Stdio & Streamable HTTP Bridge)
 *
 * - Supports full local MCP introspection (`initialize`, `tools/list`, `ping`,
 *   `resources/list`, `prompts/list`) even before `APEXTICK_API_KEY` is set so
 *   automated container/registry scanners (Glama, Smithery, MCP Inspector) can
 *   verify all 5 tool schemas out of the box.
 * - Forwards authenticated `tools/call` (and `tools/list` when `APEXTICK_API_KEY`
 *   is set) to `https://api.apextick.com/mcp`.
 */
import readline from 'node:readline';

const API_URL = process.env.APEXTICK_MCP_URL || 'https://api.apextick.com/mcp';
const API_KEY = process.env.APEXTICK_API_KEY || '';

const TOOLS = [
  {
    name: 'get_quote',
    description:
      'Current quote for one ticker: price, change, % change, volume and timestamp. Returns compact JSON.',
    annotations: { title: 'Get quote', readOnlyHint: true, idempotentHint: true },
    inputSchema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        symbol: {
          type: 'string',
          description: 'Ticker in standard market notation, e.g. AAPL, BRK-B, BTC-USD, EURUSD=X',
        },
      },
      required: ['symbol'],
    },
  },
  {
    name: 'analyze_ticker',
    description:
      'Concise snapshot of one ticker: current session change and range, a session-based stance, and valuation multiples (market cap, P/E, P/B, EPS, ROE, dividend yield). Returns compact JSON.',
    annotations: { title: 'Analyze ticker', readOnlyHint: true, idempotentHint: true },
    inputSchema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        symbol: {
          type: 'string',
          description: 'Ticker in standard market notation, e.g. AAPL, BRK-B, BTC-USD, EURUSD=X',
        },
      },
      required: ['symbol'],
    },
  },
  {
    name: 'explain_price_move',
    description:
      'Structured context for explaining why a ticker is up or down today: session move (gap, range, move vs ATR), technical position (RSI, moving averages, MACD, volatility) and recent/upcoming earnings, plus pre-computed signals. Returns compact JSON for the model to reason over.',
    annotations: { title: 'Explain price move', readOnlyHint: true, idempotentHint: true },
    inputSchema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        symbol: {
          type: 'string',
          description: 'Ticker in standard market notation, e.g. AAPL, BRK-B, BTC-USD, EURUSD=X',
        },
      },
      required: ['symbol'],
    },
  },
  {
    name: 'get_watchlist_brief',
    description:
      'One-call brief for up to 20 tickers as a compact Markdown table (price, change, % change, day range, volume) with a breadth summary. Uses a single batched quote request.',
    annotations: { title: 'Watchlist brief', readOnlyHint: true, idempotentHint: true },
    inputSchema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        symbols: {
          type: 'array',
          items: { type: 'string' },
          description: '1 to 20 tickers in standard market notation, e.g. ["AAPL","MSFT","BTC-USD"]',
        },
      },
      required: ['symbols'],
    },
  },
  {
    name: 'screen_market',
    description:
      'Market screen returning top gainers, top losers, volume leaders (with sector and market cap for equities) and/or the highest implied-volatility option underlyings. Supports optional sector (e.g. Technology, Healthcare, Financial Services) and min_market_cap filters for equities. Returns compact JSON lists.',
    annotations: { title: 'Screen market', readOnlyHint: true, idempotentHint: true },
    inputSchema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        asset_class: {
          type: 'string',
          description: 'Instrument universe: eq (equities, default), etf or fx',
        },
        metric: {
          type: 'string',
          description:
            'Screen: all (default: gainers, volume leaders and high implied volatility), gainers, losers, volume or high_iv',
        },
        sector: {
          type: 'string',
          description:
            'Optional GICS sector filter for equities (e.g. Technology, Healthcare, Financial Services, Consumer Cyclical, Consumer Defensive, Industrials, Energy, Basic Materials, Communication Services, Utilities, Real Estate)',
        },
        min_market_cap: {
          type: 'number',
          description:
            'Optional minimum market cap in USD for equities (e.g. 500000000000 or 500 for $500B; values under 1000000 are treated as billions)',
        },
        limit: {
          type: 'integer',
          description: 'Rows per list, 1-20 (default 5)',
        },
      },
    },
  },
];

function sendResult(id, result) {
  process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id, result }) + '\n');
}

function sendError(id, code, message) {
  process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id, error: { code, message } }) + '\n');
}

const rl = readline.createInterface({ input: process.stdin, terminal: false });

rl.on('line', async (line) => {
  const trimmed = line.trim();
  if (!trimmed) return;
  let msg;
  try {
    msg = JSON.parse(trimmed);
  } catch {
    return;
  }

  // Notifications have no id
  if (msg.id === undefined || msg.id === null) {
    return;
  }

  if (msg.method === 'initialize') {
    const protocolVersion = msg.params?.protocolVersion || '2024-11-05';
    sendResult(msg.id, {
      protocolVersion,
      capabilities: {
        tools: {},
        resources: {},
        prompts: {},
      },
      serverInfo: {
        name: 'apextick',
        title: 'ApexTick Market Data & Options MCP Server',
        version: '1.0.0',
      },
    });
    return;
  }

  if (msg.method === 'ping') {
    sendResult(msg.id, {});
    return;
  }

  if (msg.method === 'resources/list') {
    sendResult(msg.id, { resources: [] });
    return;
  }

  if (msg.method === 'resources/templates/list') {
    sendResult(msg.id, { resourceTemplates: [] });
    return;
  }

  if (msg.method === 'prompts/list') {
    sendResult(msg.id, { prompts: [] });
    return;
  }

  if (msg.method === 'tools/list' && !API_KEY) {
    sendResult(msg.id, { tools: TOOLS });
    return;
  }

  if (!API_KEY) {
    sendError(
      msg.id,
      -32001,
      'APEXTICK_API_KEY is required to invoke tools. Get a free API key at https://dash.apextick.com/register'
    );
    return;
  }

  try {
    const res = await fetch(API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json, text/event-stream',
        apikey: API_KEY,
      },
      body: JSON.stringify(msg),
    });
    const text = await res.text();
    if (text.trim()) {
      process.stdout.write(text.trim() + '\n');
    } else {
      sendError(msg.id, -32603, `Upstream returned HTTP ${res.status}`);
    }
  } catch (err) {
    sendError(msg.id, -32603, String(err.message || err));
  }
});
