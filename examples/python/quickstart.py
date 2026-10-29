#!/usr/bin/env python3
"""ApexTick REST & Options Chain Quickstart (Python 3)."""
import os
import urllib.request
import json

API_KEY = os.environ.get("APEXTICK_API_KEY", "dk_your_key_here")
BASE_URL = "https://api.apextick.com"

def get_json(path: str) -> dict:
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        headers={"apikey": API_KEY, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))

if __name__ == "__main__":
    quotes = get_json("/v1/market/quote?symbol=AAPL,MSFT,NVDA,BTC-USD")
    for q in quotes.get("data", []):
        print(f"{q['symbol']:8s}  ${q['price']:10.2f}  ({q['change_percent']:+.2f}%)  52w: {q.get('low_52w')} - {q.get('high_52w')}")
