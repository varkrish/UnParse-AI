---
name: mcp-patterns
description: MCP server implementation patterns
alwaysApply: true
---

When building MCP servers with fastmcp:

- Every MCP server must have a health check (expose via a separate FastAPI app or a custom MCP resource)
- Use `@mcp.tool` decorator with clear docstrings (the docstring becomes the tool description for LLMs)
- Tool functions must be synchronous or async — match the pattern of the wrapped function
- Return strings (not dicts) from tools — LLMs consume string results
- Include parameter descriptions in type hints or docstrings
- Handle errors gracefully — return error messages as strings, do not raise exceptions that crash the server
- Log tool invocations at INFO level with duration
- Each server runs as its own process/pod, listening on its own port
