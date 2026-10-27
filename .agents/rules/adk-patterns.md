---
name: adk-patterns
description: Google ADK agent implementation patterns
alwaysApply: true
---

When building ADK agents:

- Use `google.adk.agents.Agent` as the base class
- Use `google.adk.models.LiteLlm` for model access (not direct OpenAI/Anthropic clients)
- Use `google.adk.tools.McpToolset` with `SseServerParams` for MCP tool access
- Each agent gets its tools from the MCP Gateway (one connection), not individual MCP servers
- Agent instructions (system prompts) come from the existing agent modules — import them, do not copy/paste
- Use `adk api_server --a2a` to expose agents as A2A services
- Each agent pod must serve `/.well-known/agent.json` (A2A Agent Card)
- The Agent Card must include: name, description, url, version, capabilities, skills
- Use `RemoteA2aAgent` in the workflow graph to dispatch to agents by URL
