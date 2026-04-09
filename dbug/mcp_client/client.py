"""Universal MCP client — spawns and manages connections to external MCP servers."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class MCPServerConfig:
    """Configuration for an external MCP server."""

    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    enabled: bool = True


@dataclass
class ToolResult:
    """Result from calling an MCP tool."""

    success: bool
    data: Any = None
    error: Optional[str] = None


class MCPClient:
    """Manages connections to external MCP servers via stdio."""

    # Default server configurations
    SERVERS: dict[str, MCPServerConfig] = {
        "filesystem": MCPServerConfig(
            name="filesystem",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "."],
        ),
        "git": MCPServerConfig(
            name="git",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-git"],
        ),
        "github": MCPServerConfig(
            name="github",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-github"],
        ),
        "brave-search": MCPServerConfig(
            name="brave-search",
            command="npx",
            args=["-y", "@anthropic/mcp-server-brave-search"],
        ),
        "sqlite": MCPServerConfig(
            name="sqlite",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-sqlite"],
        ),
        "memory": MCPServerConfig(
            name="memory",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-memory"],
        ),
        "playwright": MCPServerConfig(
            name="playwright",
            command="npx",
            args=["-y", "@anthropic/mcp-server-playwright"],
        ),
        "sentry": MCPServerConfig(
            name="sentry",
            command="npx",
            args=["-y", "@sentry/mcp-server@latest"],
        ),
    }

    def __init__(self) -> None:
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._request_id = 0

    async def start_server(self, name: str, config: Optional[MCPServerConfig] = None) -> bool:
        """Start an MCP server process."""
        cfg = config or self.SERVERS.get(name)
        if not cfg or not cfg.enabled:
            return False

        try:
            process = await asyncio.create_subprocess_exec(
                cfg.command,
                *cfg.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**dict(__import__("os").environ), **cfg.env},
            )
            self._processes[name] = process

            # Send initialize request
            await self._send_request(name, "initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "dbug", "version": "0.1.0"},
            })
            logger.info(f"Started MCP server: {name}")
            return True
        except Exception as e:
            logger.warning(f"Failed to start MCP server {name}: {e}")
            return False

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        """Call a tool on an MCP server."""
        if server_name not in self._processes:
            started = await self.start_server(server_name)
            if not started:
                return ToolResult(success=False, error=f"Server {server_name} not available")

        try:
            response = await self._send_request(server_name, "tools/call", {
                "name": tool_name,
                "arguments": arguments,
            })
            if response and "result" in response:
                content = response["result"].get("content", [])
                text = "\n".join(c.get("text", "") for c in content if c.get("type") == "text")
                return ToolResult(success=True, data=text or content)
            return ToolResult(success=False, error="Empty response")
        except Exception as e:
            logger.error(f"MCP tool call failed [{server_name}/{tool_name}]: {e}")
            return ToolResult(success=False, error=str(e))

    async def _send_request(self, server_name: str, method: str, params: dict) -> Optional[dict]:
        """Send a JSON-RPC request to an MCP server."""
        process = self._processes.get(server_name)
        if not process or not process.stdin or not process.stdout:
            return None

        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }

        message = json.dumps(request)
        content = f"Content-Length: {len(message)}\r\n\r\n{message}"
        process.stdin.write(content.encode())
        await process.stdin.drain()

        # Read response
        try:
            header = await asyncio.wait_for(process.stdout.readline(), timeout=30)
            if not header:
                return None
            await process.stdout.readline()  # Empty line
            length = int(header.decode().split(":")[1].strip())
            body = await asyncio.wait_for(process.stdout.read(length), timeout=30)
            return json.loads(body.decode())
        except (asyncio.TimeoutError, Exception) as e:
            logger.warning(f"MCP response timeout/error [{server_name}]: {e}")
            return None

    async def stop_all(self) -> None:
        """Stop all running MCP servers."""
        for name, process in self._processes.items():
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=5)
            except Exception:
                process.kill()
            logger.debug(f"Stopped MCP server: {name}")
        self._processes.clear()

    def is_running(self, name: str) -> bool:
        process = self._processes.get(name)
        return process is not None and process.returncode is None


# Convenience wrappers
_client: Optional[MCPClient] = None


def get_mcp_client() -> MCPClient:
    global _client
    if _client is None:
        _client = MCPClient()
    return _client
