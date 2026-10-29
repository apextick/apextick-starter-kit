#!/usr/bin/env node
// ApexTick REST & Technical Indicators Quickstart (Node.js 20+)
const API_KEY = process.env.APEXTICK_API_KEY || 'dk_your_key_here';
const BASE_URL = 'https://api.apextick.com';

const res = await fetch(`${BASE_URL}/v1/market/quote?symbol=AAPL,NVDA,BTC-USD`, {
  headers: { apikey: API_KEY },
});
const payload = await res.json();
console.table(payload.data);
