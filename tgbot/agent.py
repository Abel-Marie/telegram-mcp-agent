"""Bridges Telegram, OpenAI, and an MCP server.

The OpenAI model is given the tools exposed by the MCP server (over stdio).
When the model calls a tool, we route it through the MCP client, get the
result, and feed it back to the model — looping until the model produces a
final reply.
"""
import json
import logging
import os
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import AsyncOpenAI

from prompt import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def _mcp_tool_to_openai(tool) -> dict[str, Any]:
    """Convert an MCP Tool definition to an OpenAI tool schema."""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema or {"type": "object", "properties": {}},
        },
    }


class TelegramMCPAgent:
    """Long-lived agent: keeps an MCP session open, talks to OpenAI per message."""

    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        self.openai = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self._stdio_ctx = None
        self._session: ClientSession | None = None
        self._tools: list = []
        self._tool_schemas: list[dict] = []
        # In-memory per-chat history. Replace with persistent store for production.
        self._history: dict[str, list[dict]] = {}

    async def connect(self) -> None:
        """Spawn the MCP server (default: filesystem) and list its tools."""
        server = StdioServerParameters(
            command=os.environ.get("MCP_COMMAND", "npx"),
            args=os.environ.get(
                "MCP_ARGS", "-y @modelcontextprotocol/server-filesystem /tmp"
            ).split(),
        )
        self._stdio_ctx = stdio_client(server)
        read, write = await self._stdio_ctx.__aenter__()
        self._session = ClientSession(read, write)
        await self._session.__aenter__()
        await self._session.initialize()

        tools_result = await self._session.list_tools()
        self._tools = tools_result.tools
        self._tool_schemas = [_mcp_tool_to_openai(t) for t in self._tools]
        logger.info(
            "MCP connected. %d tool(s): %s",
            len(self._tools),
            [t.name for t in self._tools],
        )

    async def disconnect(self) -> None:
        if self._session is not None:
            await self._session.__aexit__(None, None, None)
        if self._stdio_ctx is not None:
            await self._stdio_ctx.__aexit__(None, None, None)

    async def list_tools(self) -> list[str]:
        return [t.name for t in self._tools]

    async def chat(
        self, user_message: str, conversation_id: str = "default", max_iters: int = 5
    ) -> str:
        history = self._history.setdefault(
            conversation_id, [{"role": "system", "content": SYSTEM_PROMPT}]
        )
        history.append({"role": "user", "content": user_message})

        for _ in range(max_iters):
            resp = await self.openai.chat.completions.create(
                model=self.model,
                messages=history,
                tools=self._tool_schemas if self._tool_schemas else None,
            )
            msg = resp.choices[0].message
            history.append(msg.model_dump())

            if not msg.tool_calls:
                return msg.content or ""

            for call in msg.tool_calls:
                try:
                    args = json.loads(call.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                logger.info("Calling MCP tool %s with %s", call.function.name, args)

                try:
                    result = await self._session.call_tool(call.function.name, args)
                    content = (
                        "\n".join(c.text for c in result.content if hasattr(c, "text"))
                        or "(no text content)"
                    )
                except Exception as e:
                    logger.exception("MCP tool call failed")
                    content = f"Tool call failed: {e}"

                history.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "name": call.function.name,
                        "content": content,
                    }
                )

        return "(model exceeded max tool-call iterations)"
