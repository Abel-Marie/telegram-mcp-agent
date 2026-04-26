# Telegram MCP Agent

> A Telegram bot powered by an LLM that can use **Model Context Protocol (MCP)** tools. Pluggable — point it at any MCP server (filesystem, GitHub, Brave Search, Postgres, Slack, custom) and the bot can use those tools mid-conversation.

## What this does

```
Telegram user
     │  text message
     ▼
┌──────────────────────┐
│  python-telegram-bot │
└──────────────────────┘
     │
     ▼
┌──────────────────────┐    chat.completions(tools=...)
│  TelegramMCPAgent    │  ─────────────────────────────►  OpenAI
│  (history per chat)  │  ◄──────  reply / tool_calls
└──────────────────────┘
     │  if tool_calls:
     ▼
┌──────────────────────┐    stdio JSON-RPC
│   MCP Client         │  ─────────────────────────►  MCP Server (filesystem / GitHub / ...)
└──────────────────────┘  ◄──────  tool result
```

- **`tgbot/main.py`** — Telegram bot entry point. `/start`, `/tools`, plus a free-text handler that routes every message into the agent.
- **`tgbot/agent.py`** — `TelegramMCPAgent`. Holds a long-lived MCP session, exposes the MCP tools to OpenAI as function-calling tools, runs a tool-call loop, and keeps per-chat history.
- **`tgbot/prompt.py`** — System prompt.

## Why MCP?

MCP is an open standard for connecting LLMs to tools. Once your bot speaks MCP, you can swap in *any* MCP server (filesystem, web search, GitHub, Postgres, Slack, custom in-house tools) without changing the bot code. Just point `MCP_COMMAND` / `MCP_ARGS` at a different server.

## Install

```bash
git clone https://github.com/Abel-Marie/telegram-mcp-agent.git
cd telegram-mcp-agent/tgbot
pip install -r requirements.txt
```

You also need **Node.js** installed if you want to use any of the official `@modelcontextprotocol/server-*` MCP servers (they're distributed via `npx`).

## Configure

```bash
cp .env.example .env
# then edit .env and fill in TELEGRAM_BOT_TOKEN + OPENAI_API_KEY
```

| Variable | Required? | Notes |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | **Yes** | Get from [@BotFather](https://t.me/BotFather) on Telegram. |
| `OPENAI_API_KEY` | **Yes** | https://platform.openai.com/api-keys |
| `MCP_COMMAND` | No | Default: `npx`. |
| `MCP_ARGS` | No | Default: filesystem MCP server bound to `/tmp`. |

## Run

```bash
cd tgbot
python main.py
```

Open your bot in Telegram and:
- `/start` — greeting
- `/tools` — list the MCP tools the agent currently has
- *anything else* — chat freely. The model will call MCP tools when relevant.

## Swapping MCP servers

Set `MCP_ARGS` in `.env` to attach a different server:

```bash
# Filesystem (default — read/write files under /tmp)
MCP_ARGS=-y @modelcontextprotocol/server-filesystem /tmp

# Brave web search
MCP_ARGS=-y @modelcontextprotocol/server-brave-search
# (also set BRAVE_API_KEY in your shell env)

# GitHub
MCP_ARGS=-y @modelcontextprotocol/server-github
# (also set GITHUB_PERSONAL_ACCESS_TOKEN)

# Postgres
MCP_ARGS=-y @modelcontextprotocol/server-postgres "postgres://user:pass@host/db"
```

A directory of official servers: https://github.com/modelcontextprotocol/servers

## Project structure

```
.
├── README.md
├── LICENSE
└── tgbot/
    ├── main.py              # Telegram bot wiring
    ├── agent.py             # OpenAI + MCP tool-loop bridge
    ├── prompt.py            # System prompt
    ├── requirements.txt
    ├── .env.example
    └── .gitignore
```

## What's next

- Persist per-chat conversation history (SQLite or Redis) instead of in-memory.
- Connect multiple MCP servers simultaneously and merge their tool catalogs.
- Add streaming replies (Telegram supports edited messages — stream tokens in).
- Add `/reset` command to clear conversation memory for the current chat.
- Switch from polling to webhooks for production deployment.

## License

[MIT](LICENSE) © 2025 Abel Marie Shiferaw
