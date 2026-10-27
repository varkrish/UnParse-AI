# OPL Agent Swarm Platform

## What this project is

An AI-powered software development factory that uses Google ADK agents communicating via A2A protocol, with tools exposed through MCP servers, running on Kubernetes with Agent Sandbox for isolated code execution and MemMachine for cross-job learning memory.

This project wraps 33K+ lines of existing domain logic from `opl-ai-software-team` — parsers, validators, memory plane, tools — without rewriting them. Only ~1,800 lines of LlamaIndex framework glue get replaced by ADK equivalents.

## Architecture

```
Orchestrator (ADK workflow graph + job API)
    │
    ├── A2A dispatch ──► Meta Agent (ADK + A2A)
    ├── A2A dispatch ──► PO Agent (ADK + A2A)
    ├── A2A dispatch ──► Architect Agent (ADK + A2A)
    ├── A2A dispatch ──► Dev Agent (ADK + A2A, HPA 1-5)
    ├── A2A dispatch ──► Frontend Agent (ADK + A2A)
    ├── A2A dispatch ──► DevOps Agent (ADK + A2A)
    └── A2A dispatch ──► QA Agent (ADK + A2A)
            │
            └── MCP tools ──► MCP Gateway (Magg)
                                ├── Workspace MCP (file_tools + git_tools)
                                ├── Sandbox MCP (K8s Agent Sandbox)
                                ├── Memory MCP (MemMachine)
                                └── Skills MCP (existing)
```

## Tech stack (mandatory)

| Layer | Technology | Version |
|---|---|---|
| Agent framework | Google ADK | >= 2.13.0 |
| Agent-to-agent | A2A Protocol | v1.0 |
| Agent-to-tool | MCP (Model Context Protocol) | 2026-07-28 spec |
| MCP servers | fastmcp | latest |
| MCP gateway | Magg (MCP Aggregator) | latest |
| K8s sandbox | K8s Agent Sandbox | >= 1.0.8 |
| Memory plane | MemMachine | >= 0.3.9 |
| LLM routing | LiteLLM | latest |
| Container base | registry.access.redhat.com/ubi9/python-311 | latest |
| Orchestration | Helm + Skaffold | latest |

## Code conventions

- Python 3.11, type hints on all public functions
- Pydantic v2 for data models
- FastAPI for HTTP services
- ruff for linting (line length 120)
- All containers run as non-root (USER 1001, OpenShift compatible)
- All services expose GET /health returning {"status": "ok"}
- All agents serve A2A Agent Card at GET /.well-known/agent.json
- Fail-open pattern for memory plane (memory down = jobs still run)
- Apache-2.0 license

## Existing code — DO NOT REWRITE

The `opl-ai-software-team` repo is cloned alongside this project. The following modules contain domain logic that must be imported and used as-is:

```
agent/src/llamaindex_crew/
├── utils/                      # 11,392 lines
│   ├── wiring_contract.py      # file/manifest validation
│   ├── output_parser.py        # LLM output → files
│   ├── vision_stack_analysis.py # stack inference
│   ├── manifest_repair.py      # broken manifest recovery
│   ├── contract_coherence.py   # inter-file consistency
│   ├── prompt_budget.py        # token budget management
│   └── ... 20 more modules
├── orchestrator/               # 6,734 lines
│   ├── task_manager.py         # per-file task tracking
│   ├── code_validator.py       # language-specific validation
│   ├── error_recovery.py       # retry strategies
│   ├── state_machine.py        # state transitions
│   └── language_strategies.py  # Python/Java/JS/Go validators
├── memory/                     # 2,534 lines
│   ├── context_memory.py       # MemMachine wrapper (fail-open)
│   ├── postgres_context_store.py # pgvector store
│   ├── corrections.py          # reviewer correction tracking
│   ├── summaries.py            # job outcome summaries
│   ├── recall.py               # solutioning recall
│   ├── scope.py                # org/project/domain scoping
│   └── artifact_seeder.py      # artifact seeding
├── tools/                      # 4,344 lines (logic kept, wrappers change)
│   ├── file_tools.py           # safe file I/O → wrap as MCP @mcp.tool
│   ├── test_tools.py           # test execution
│   ├── git_tools.py            # git operations → wrap as MCP @mcp.tool
│   ├── sandbox_tools.py        # sandbox execution → wrap as MCP @mcp.tool
│   └── skill_tools.py          # skill search
├── agents/                     # 3,661 lines (prompts + phase logic kept)
│   ├── meta_agent.py           # vision analysis, backstories
│   ├── tech_architect_agent.py # stack design
│   ├── product_owner_agent.py  # user stories, BDD
│   ├── dev_agent.py            # backend code gen
│   ├── frontend_agent.py       # UI code gen
│   ├── devops_agent.py         # Containerfile, CI/CD
│   └── refinement_agent.py     # brownfield refinement
└── workflows/                  # 8,307 lines (dispatch rebuilt as ADK graph)
    ├── software_dev_workflow.py # main pipeline → ADK graph replaces dispatch
    ├── solutioning_loop.py     # research/architect/critique
    ├── epic_story_loop.py      # epic decomposition
    └── workflow_resolver.py    # pipeline resolution (full/fast/edit/refactor)
```

### What DOES get replaced (~1,800 lines)

| File | Change |
|---|---|
| `base_agent.py` (407L) | `BaseLlamaIndexAgent` → ADK `Agent` with `McpToolset` |
| `llm_config.py` (1,337L) | `GenericLlamaLLM(FunctionCallingLLM)` → ADK `LiteLlm` model connector |
| `tool_loader.py` (87L) | `FunctionTool` wrapping → MCP server registration |

## K8s deployment rules

- Vanilla K8s cluster with internal container registry
- One agent per pod (Deployment + ClusterIP Service on port 9000)
- Single container image (`crew-agent`), `AGENT_ROLE` env selects behavior
- Workspace shared via MCP server (RWO PVC on workspace-mcp pod only)
- Agents access tools ONLY through MCP Gateway — no direct PVC mounts
- K8s Agent Sandbox operator for code execution (SandboxTemplate + SandboxWarmPool CRDs)
- RBAC: only sandbox-mcp pod has permissions to create Sandbox CRDs
- NetworkPolicies: agents → MCP gateway only, orchestrator → agents only
- LLM API keys in K8s Secrets, shared across agent pods via envFrom
- Skaffold with file-sync for development iteration (no image rebuild per code change)
- HPA on Dev Agent (1-5 replicas, CPU 60% target)

## Eval system

Every completed job gets a scorecard (grade 0-100) computed from:
- Validation pass rate (30% weight)
- First-pass rate (20%)
- Stub-free rate (15%)
- Correction count (15%)
- Cost efficiency (10%)
- Memory recall utilization (10%)

Trend analysis tracks improvement over time, scoped by framework/domain.
Benchmark suite runs fixed visions periodically to measure controlled improvement.

## Quality bar for this build

After each phase, critique your own work:
- No hardcoded values that should be configurable (use env vars or config)
- No missing error handling (every external call must handle failure)
- No placeholder/stub code left behind
- No security issues (no exposed secrets, proper RBAC)
- All tests must actually test meaningful behavior
- ruff must pass on the entire codebase
- Every service must respond to /health
- Every agent must serve /.well-known/agent.json
