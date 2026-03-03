"""MCP (Model Context Protocol) Client — connects to external MCP servers.

Supports the Streamable HTTP transport (the modern standard).
Reference: https://modelcontextprotocol.io/docs
"""

import httpx
import json


class MCPClient:
    """Client for connecting to MCP servers via HTTP+SSE transport."""

    def __init__(self, server_url: str):
        self.server_url = server_url.rstrip("/")

    async def list_tools(self) -> list[dict]:
        """Fetch available tools from the MCP server."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # MCP uses JSON-RPC 2.0 over HTTP
                resp = await client.post(
                    self.server_url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/list",
                    },
                    headers={"Content-Type": "application/json"},
                )
                data = resp.json()

                if "error" in data:
                    raise Exception(f"MCP error: {data['error'].get('message', str(data['error']))}")

                tools = data.get("result", {}).get("tools", [])
                return [
                    {
                        "name": t.get("name", ""),
                        "description": t.get("description", ""),
                        "inputSchema": t.get("inputSchema", {}),
                    }
                    for t in tools
                ]
        except httpx.HTTPError as e:
            raise Exception(f"Connection failed: {str(e)[:200]}")

    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        """Execute a tool on the MCP server."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    self.server_url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": tool_name,
                            "arguments": arguments,
                        },
                    },
                    headers={"Content-Type": "application/json"},
                )
                data = resp.json()

                if "error" in data:
                    return f"❌ MCP 工具执行错误: {data['error'].get('message', str(data['error']))[:200]}"

                result = data.get("result", {})
                # MCP returns content as list of content blocks
                content_blocks = result.get("content", [])
                texts = []
                for block in content_blocks:
                    if block.get("type") == "text":
                        texts.append(block.get("text", ""))
                    elif block.get("type") == "image":
                        texts.append(f"[图片: {block.get('mimeType', 'image')}]")
                    else:
                        texts.append(str(block))

                return "\n".join(texts) if texts else str(result)

        except httpx.HTTPError as e:
            return f"❌ MCP 连接失败: {str(e)[:200]}"
