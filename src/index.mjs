#!/usr/bin/env node
/**
 * Official ApexTick Model Context Protocol (MCP) Server
 *
 * Implements the 5 ApexTick market intelligence tools over stdio using the
 * official `@modelcontextprotocol/sdk` and the ApexTick `/v1/*` REST API:
 *   1. `get_quote`
 *   2. `analyze_ticker`
 *   3. `explain_price_move`
 *   4. `get_watchlist_brief`
 *   5. `screen_market`
 */
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListPromptsRequestSchema,
  ListResourcesRequestSchema,
  ListResourceTemplatesRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';

const BASE_URL = (process.env.APEXTICK_API_URL || 'https://api.apextick.com').replace(/\/$/, '');
const API_KEY = process.env.APEXTICK_API_KEY || '';
const SYMBOL_RE = /^[A-Z0-9^][A-Z0-9.\-=^]{0,23}$/;

function normalizeSymbol(raw) {
  const s = String(raw || '').trim().toUpperCase();
  if (!SYMBOL_RE.test(s)) {
    throw new Error(`invalid symbol "${raw}": use standard market notation such as AAPL, BRK-B or BTC-USD`);
  }
  return s;
}

function round2(n) {
  return Math.round(Number(n) * 100) / 100;
}

function formatAbbrev(n) {
  const v = Number(n);
  if (!Number.isFinite(v) || v <= 0) return undefined;
  if (v >= 1e12) return `${round2(v / 1e12)}T`;
  if (v >= 1e9) return `${round2(v / 1e9)}B`;
  if (v >= 1e6) return `${round2(v / 1e6)}M`;
  if (v >= 1e3) return `${round2(v / 1e3)}K`;
  return String(Math.round(v));
}

async function apiGet(path, params = {}) {
  if (!API_KEY) {
    throw new Error('APEXTICK_API_KEY environment variable is required. Get a free key at https://dash.apextick.com/register');
  }
  const url = new URL(`${BASE_URL}${path}`);
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') {
      url.searchParams.set(k, String(v));
    }
  }
  const res = await fetch(url, {
    headers: {
      apikey: API_KEY,
      Accept: 'application/json',
    },
    signal: AbortSignal.timeout(15_000),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(`${body.error || res.statusText} (status ${res.status})`);
  }
  return body;
}

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

async function handleGetQuote(args) {
  const sym = normalizeSymbol(args?.symbol);
  const resp = await apiGet('/v1/market/quote', { symbol: sym });
  const q = resp?.data?.[0];
  if (!q) throw new Error(`no quote available for ${sym}`);
  return JSON.stringify({
    symbol: q.symbol,
    name: q.name || undefined,
    as_of: q.timestamp,
    price: round2(q.price),
    change: round2(q.change),
    change_pct: round2(q.change_percent),
    volume: formatAbbrev(q.volume),
    high_52w: q.high_52w ? round2(q.high_52w) : undefined,
    low_52w: q.low_52w ? round2(q.low_52w) : undefined,
  });
}

async function handleAnalyzeTicker(args) {
  const sym = normalizeSymbol(args?.symbol);
  const [quoteRes, finRes] = await Promise.allSettled([
    apiGet('/v1/market/quote', { symbol: sym }),
    apiGet('/v1/reference/financials/metrics', { symbol: sym }),
  ]);
  if (quoteRes.status === 'rejected') throw quoteRes.reason;
  const q = quoteRes.value?.data?.[0];
  if (!q) throw new Error(`no quote available for ${sym}`);

  const span = q.high - q.low;
  const rangePos = span > 0 ? round2((q.price - q.low) / span) : undefined;
  const gapPct = q.previous_close > 0 ? round2(((q.open - q.previous_close) / q.previous_close) * 100) : undefined;
  const pctFrom52wHigh = q.high_52w > 0 ? round2(((q.price - q.high_52w) / q.high_52w) * 100) : undefined;

  const out = {
    symbol: q.symbol,
    name: q.name || undefined,
    as_of: q.timestamp,
    session: {
      price: round2(q.price),
      change: round2(q.change),
      change_pct: round2(q.change_percent),
      open: round2(q.open),
      high: round2(q.high),
      low: round2(q.low),
      prev_close: round2(q.previous_close),
      volume: formatAbbrev(q.volume),
      gap_pct: gapPct,
      range_position: rangePos,
      high_52w: q.high_52w ? round2(q.high_52w) : undefined,
      low_52w: q.low_52w ? round2(q.low_52w) : undefined,
      pct_from_52w_high: pctFrom52wHigh,
    },
    session_stance: q.change_percent >= 1.5 ? 'strong_up' : q.change_percent <= -1.5 ? 'strong_down' : q.change_percent >= 0 ? 'up' : 'down',
  };

  if (finRes.status === 'fulfilled' && finRes.value?.metrics) {
    const m = finRes.value.metrics;
    out.valuation = {
      market_cap: formatAbbrev(m.market_cap),
      revenue_ttm: formatAbbrev(m.revenue_ttm),
      pe: m.pe_ratio ? round2(m.pe_ratio) : undefined,
      pb: m.pb_ratio ? round2(m.pb_ratio) : undefined,
      ps: m.ps_ratio ? round2(m.ps_ratio) : undefined,
      eps_ttm: m.eps_ttm ? round2(m.eps_ttm) : undefined,
      roe: m.roe ? round2(m.roe) : undefined,
      dividend_yield: m.dividend_yield ? round2(m.dividend_yield) : undefined,
    };
  }
  return JSON.stringify(out);
}

async function handleExplainPriceMove(args) {
  const sym = normalizeSymbol(args?.symbol);
  const [quoteRes, indRes, earnRes] = await Promise.allSettled([
    apiGet('/v1/market/quote', { symbol: sym }),
    apiGet('/v1/analytics/indicators', {
      symbol: sym,
      indicators: 'sma20,sma50,sma200,rsi14,macd14,atr14,volatility30',
    }),
    apiGet('/v1/reference/earnings', { symbol: sym }),
  ]);
  if (quoteRes.status === 'rejected') throw quoteRes.reason;
  const q = quoteRes.value?.data?.[0];
  if (!q) throw new Error(`no quote available for ${sym}`);

  const out = {
    symbol: q.symbol,
    name: q.name || undefined,
    as_of: q.timestamp,
    move: {
      direction: q.change > 0 ? 'up' : q.change < 0 ? 'down' : 'flat',
      price: round2(q.price),
      change: round2(q.change),
      change_pct: round2(q.change_percent),
      volume: formatAbbrev(q.volume),
    },
  };
  if (indRes.status === 'fulfilled' && indRes.value?.indicators) {
    out.technicals = indRes.value.indicators;
  }
  if (earnRes.status === 'fulfilled' && Array.isArray(earnRes.value?.earnings)) {
    out.earnings = earnRes.value.earnings.slice(0, 2);
  }
  return JSON.stringify(out);
}

async function handleWatchlistBrief(args) {
  const rawList = Array.isArray(args?.symbols) ? args.symbols : [];
  if (rawList.length === 0) throw new Error('symbols must contain at least one ticker');
  if (rawList.length > 20) throw new Error('at most 20 symbols are supported per brief');
  const syms = [...new Set(rawList.map(normalizeSymbol))];
  const resp = await apiGet('/v1/market/quote', { symbol: syms.join(',') });
  const rows = resp?.data || [];
  const lines = [
    '| Symbol | Price | Change | % Change | Day Range | Volume |',
    '|---|---:|---:|---:|---|---:|',
    ...rows.map(
      (q) =>
        `| ${q.symbol} | ${round2(q.price)} | ${round2(q.change)} | ${round2(q.change_percent)}% | ${round2(q.low)}-${round2(q.high)} | ${formatAbbrev(q.volume) || '-'} |`
    ),
  ];
  return lines.join('\n');
}

async function handleScreenMarket(args) {
  const assetClass = args?.asset_class || 'eq';
  const metric = args?.metric || 'all';
  const limit = Math.min(Math.max(Number(args?.limit || 5), 1), 20);
  const sector = args?.sector || '';
  const minMarketCap = args?.min_market_cap;

  const out = { asset_class: assetClass };
  if (metric === 'all' || metric === 'gainers') {
    const r = await apiGet('/v1/market/movers', {
      instrument: assetClass,
      trend: 'up',
      sector,
      min_market_cap: minMarketCap,
    });
    out.gainers = (r?.data || []).slice(0, limit);
  }
  if (metric === 'losers') {
    const r = await apiGet('/v1/market/movers', {
      instrument: assetClass,
      trend: 'down',
      sector,
      min_market_cap: minMarketCap,
    });
    out.losers = (r?.data || []).slice(0, limit);
  }
  if (metric === 'all' || metric === 'volume') {
    const r = await apiGet('/v1/market/movers', {
      instrument: assetClass,
      trend: 'active',
      sector,
      min_market_cap: minMarketCap,
    });
    out.volume_leaders = (r?.data || []).slice(0, limit);
  }
  if ((metric === 'all' || metric === 'high_iv') && assetClass !== 'fx' && !sector && !minMarketCap) {
    const r = await apiGet('/v1/options/screener', {
      type: 'high_iv',
      min_volume: 100,
      min_open_interest: 500,
      min_dte: 5,
      limit: 100,
    }).catch(() => null);
    if (r?.data) {
      out.high_iv_underlyings = r.data.slice(0, limit);
    }
  }
  return JSON.stringify(out);
}

const server = new Server(
  {
    name: 'apextick',
    version: '1.0.0',
  },
  {
    capabilities: {
      tools: {},
      resources: {},
      prompts: {},
    },
  }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: TOOLS,
}));

server.setRequestHandler(ListResourcesRequestSchema, async () => ({
  resources: [],
}));

server.setRequestHandler(ListResourceTemplatesRequestSchema, async () => ({
  resourceTemplates: [],
}));

server.setRequestHandler(ListPromptsRequestSchema, async () => ({
  prompts: [],
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  try {
    let text;
    switch (name) {
      case 'get_quote':
        text = await handleGetQuote(args);
        break;
      case 'analyze_ticker':
        text = await handleAnalyzeTicker(args);
        break;
      case 'explain_price_move':
        text = await handleExplainPriceMove(args);
        break;
      case 'get_watchlist_brief':
        text = await handleWatchlistBrief(args);
        break;
      case 'screen_market':
        text = await handleScreenMarket(args);
        break;
      default:
        return {
          isError: true,
          content: [{ type: 'text', text: `Unknown tool: ${name}` }],
        };
    }
    return {
      content: [{ type: 'text', text }],
    };
  } catch (err) {
    return {
      isError: true,
      content: [{ type: 'text', text: String(err?.message || err) }],
    };
  }
});

const transport = new StdioServerTransport();
await server.connect(transport);
