#!/usr/bin/env node
/**
 * ApexTick MCP Stdio-to-Streamable-HTTP Bridge
 *
 * Bridges local stdio MCP clients (Claude Desktop, Cursor, Windsurf) to the
 * hosted ApexTick Streamable HTTP MCP endpoint (`https://api.apextick.com/mcp`)
 * using `APEXTICK_API_KEY` from the environment.
 */
import readline from 'node:readline';

const API_URL = process.env.APEXTICK_MCP_URL || 'https://api.apextick.com/mcp';
const API_KEY = process.env.APEXTICK_API_KEY || '';

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
    }
  } catch (err) {
    if (msg && msg.id !== undefined) {
      process.stdout.write(
        JSON.stringify({
          jsonrpc: '2.0',
          id: msg.id,
          error: { code: -32603, message: String(err.message || err) },
        }) + '\n'
      );
    }
  }
});
