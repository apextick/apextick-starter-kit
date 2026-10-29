#!/usr/bin/env bash
set -euo pipefail
: "${APEXTICK_API_KEY:?Set APEXTICK_API_KEY=dk_... first (get a free key at https://dash.apextick.com/register)}"

curl -sS -H "apikey: $APEXTICK_API_KEY" "https://api.apextick.com/v1/market/quote?symbol=AAPL,MSFT,BTC-USD" | jq .
curl -sS -H "apikey: $APEXTICK_API_KEY" "https://api.apextick.com/v1/market/movers?instrument=eq&trend=up&sector=Technology" | jq .
