"""D-BUG MCP Server — expose debugging tools to any MCP-compatible AI IDE."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from dbug import __version__

logger = logging.getLogger(__name__)

server = Server("dbug")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all D-BUG tools available via MCP."""
    return [
        Tool(
            name="dbug_scan",
            description="Scan a codebase for bugs using AI-powered adversarial testing and RAG-based analysis",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to scan", "default": "."},
                    "max_bugs": {"type": "integer", "description": "Max bugs to analyze", "default": 10},
                },
            },
        ),
        Tool(
            name="dbug_analyze_file",
            description="Analyze a single file for potential bugs",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the file to analyze"},
                },
                "required": ["file_path"],
            },
        ),
        Tool(
            name="dbug_generate_tests",
            description="Generate adversarial edge-case tests for a code file",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the file"},
                    "max_tests": {"type": "integer", "description": "Max tests to generate", "default": 10},
                },
                "required": ["file_path"],
            },
        ),
        Tool(
            name="dbug_find_root_cause",
            description="Diagnose why a bug occurs using RAG-based root cause analysis",
            inputSchema={
                "type": "object",
                "properties": {
                    "error_message": {"type": "string", "description": "The error message or bug description"},
                    "file_path": {"type": "string", "description": "File where the bug occurs"},
                    "code": {"type": "string", "description": "The relevant code snippet"},
                },
                "required": ["error_message", "file_path", "code"],
            },
        ),
        Tool(
            name="dbug_suggest_fix",
            description="Generate a minimal code fix for a diagnosed bug",
            inputSchema={
                "type": "object",
                "properties": {
                    "root_cause": {"type": "string", "description": "The diagnosed root cause"},
                    "file_path": {"type": "string", "description": "File to fix"},
                    "code": {"type": "string", "description": "The buggy code"},
                },
                "required": ["root_cause", "file_path", "code"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name == "dbug_scan":
            return await _handle_scan(arguments)
        elif name == "dbug_analyze_file":
            return await _handle_analyze(arguments)
        elif name == "dbug_generate_tests":
            return await _handle_gen_tests(arguments)
        elif name == "dbug_find_root_cause":
            return await _handle_rca(arguments)
        elif name == "dbug_suggest_fix":
            return await _handle_fix(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        logger.error(f"Tool {name} failed: {e}")
        return [TextContent(type="text", text=f"Error: {e}")]


async def _handle_scan(args: dict) -> list[TextContent]:
    from dbug.orchestrator.graph import DebugPipeline

    pipeline = DebugPipeline()
    state = await pipeline.run(args.get("path", "."), max_bugs=args.get("max_bugs", 10))

    result = {
        "status": state.stage.value,
        "files_scanned": state.total_files,
        "bugs_found": state.bugs_found,
        "bugs_fixed": state.bugs_fixed,
        "bugs": [b.model_dump() for b in state.bugs],
    }
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def _handle_analyze(args: dict) -> list[TextContent]:
    file_path = args["file_path"]
    from dbug.orchestrator.graph import DebugPipeline

    pipeline = DebugPipeline()
    state = await pipeline.run(str(Path(file_path).parent), max_bugs=5)

    result = {"file": file_path, "bugs": [b.model_dump() for b in state.bugs if b.file_path == file_path]}
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def _handle_gen_tests(args: dict) -> list[TextContent]:
    from dbug.agents.adversarial import AdversarialAgent
    from dbug.rag.parser import CodeParser

    file_path = args["file_path"]
    parser = CodeParser()
    language = parser.detect_language(Path(file_path))
    code = Path(file_path).read_text()

    agent = AdversarialAgent()
    result = await agent.run(
        code=code, file_path=file_path, language=language or "python",
        max_tests=args.get("max_tests", 10),
    )
    return [TextContent(type="text", text=json.dumps(result.model_dump(), indent=2))]


async def _handle_rca(args: dict) -> list[TextContent]:
    from dbug.agents.root_cause import RootCauseAgent

    agent = RootCauseAgent()
    result = await agent.run(
        error_message=args["error_message"],
        code=args["code"],
        file_path=args["file_path"],
    )
    return [TextContent(type="text", text=json.dumps(result.model_dump(), indent=2))]


async def _handle_fix(args: dict) -> list[TextContent]:
    from dbug.agents.fix_generator import FixGeneratorAgent

    agent = FixGeneratorAgent()
    result = await agent.run(
        root_cause=args["root_cause"],
        code=args["code"],
        file_path=args["file_path"],
    )
    return [TextContent(type="text", text=json.dumps(result.model_dump(), indent=2))]


async def main() -> None:
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
