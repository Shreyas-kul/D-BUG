"""Convenience wrappers for all external MCP server tools."""

from __future__ import annotations

from typing import Any

from dbug.mcp_client.client import MCPClient, ToolResult, get_mcp_client


# ─── DuckDuckGo Search (100% free, no API key) ───────────────────────────────

async def search_web(query: str, max_results: int = 5) -> ToolResult:
    """Search the web via DuckDuckGo. Free, no API key needed."""
    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        formatted = "\n\n".join(
            f"**{r.get('title', '')}**\n{r.get('href', '')}\n{r.get('body', '')}"
            for r in results
        )
        return ToolResult(success=True, data=formatted)
    except Exception as e:
        return ToolResult(success=False, error=str(e))


async def search_stackoverflow(error_message: str) -> ToolResult:
    """Search StackOverflow for a specific error."""
    return await search_web(f"site:stackoverflow.com {error_message}")


# ─── GitHub ───────────────────────────────────────────────────────────────────

async def get_github_issues(owner: str, repo: str, query: str = "") -> ToolResult:
    """Search issues in a GitHub repo."""
    return await get_mcp_client().call_tool(
        "github", "search_issues", {"q": f"repo:{owner}/{repo} {query}"}
    )


async def get_pr_diff(owner: str, repo: str, pr_number: int) -> ToolResult:
    """Get a PR diff."""
    return await get_mcp_client().call_tool(
        "github", "get_pull_request", {"owner": owner, "repo": repo, "pull_number": pr_number}
    )


# ─── Git ──────────────────────────────────────────────────────────────────────

async def get_git_diff(path: str = ".") -> ToolResult:
    """Get current git diff."""
    return await get_mcp_client().call_tool("git", "git_diff", {"repo_path": path})


async def get_git_log(path: str = ".", count: int = 20) -> ToolResult:
    """Get recent git log."""
    return await get_mcp_client().call_tool(
        "git", "git_log", {"repo_path": path, "max_count": count}
    )


async def get_git_blame(path: str, file_path: str) -> ToolResult:
    """Get git blame for a file."""
    return await get_mcp_client().call_tool(
        "git", "git_blame", {"repo_path": path, "file_path": file_path}
    )


# ─── Filesystem ───────────────────────────────────────────────────────────────

async def read_file(path: str) -> ToolResult:
    """Read a file via Filesystem MCP."""
    return await get_mcp_client().call_tool("filesystem", "read_file", {"path": path})


async def write_file(path: str, content: str) -> ToolResult:
    """Write a file via Filesystem MCP."""
    return await get_mcp_client().call_tool(
        "filesystem", "write_file", {"path": path, "content": content}
    )


# ─── SQLite ───────────────────────────────────────────────────────────────────

async def query_db(db_path: str, sql: str) -> ToolResult:
    """Execute a SQL query."""
    return await get_mcp_client().call_tool(
        "sqlite", "read_query", {"db_path": db_path, "query": sql}
    )


async def write_db(db_path: str, sql: str) -> ToolResult:
    """Execute a write SQL query."""
    return await get_mcp_client().call_tool(
        "sqlite", "write_query", {"db_path": db_path, "query": sql}
    )


# ─── Memory ───────────────────────────────────────────────────────────────────

async def remember(key: str, value: str) -> ToolResult:
    """Store something in persistent memory."""
    return await get_mcp_client().call_tool(
        "memory", "create_entities", {"entities": [{"name": key, "observations": [value]}]}
    )


async def recall(query: str) -> ToolResult:
    """Recall from persistent memory."""
    return await get_mcp_client().call_tool("memory", "search_nodes", {"query": query})


# ─── Sentry ───────────────────────────────────────────────────────────────────

async def get_sentry_issues(project: str) -> ToolResult:
    """Get recent Sentry issues."""
    return await get_mcp_client().call_tool(
        "sentry", "search_issues", {"query": f"project:{project} is:unresolved"}
    )


# ─── Playwright ───────────────────────────────────────────────────────────────

async def run_browser_test(url: str) -> ToolResult:
    """Navigate to a URL and get page content."""
    return await get_mcp_client().call_tool(
        "playwright", "browser_navigate", {"url": url}
    )
