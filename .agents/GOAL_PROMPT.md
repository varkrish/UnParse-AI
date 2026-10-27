# Master Goal Prompt for Google Antigravity CLI

## Setup (run once on the remote machine)

```bash
# 1. Install agy CLI
curl -fsSL https://antigravity.google/cli/install.sh | bash

# 2. Clone repos
cd /workspace  # or wherever you want to work
git clone <ast-agent-repo-url> ast-agent
git clone <opl-ai-software-team-repo-url> opl-ai-software-team

# 3. Verify cluster access
kubectl cluster-info
kubectl get nodes

# 4. Launch agy in the project
cd ast-agent
agy
```

## Auth over SSH

When agy detects SSH, it prints a URL. Open that URL in your local browser, sign in, paste the code back into the SSH terminal.

## The Goal Prompt

Paste this into `agy` after setup:

```
/goal Build the OPL Agent Swarm Platform end-to-end on this K8s cluster. The full architecture, tech stack, and existing code inventory are in AGENTS.md. Detailed plans are in .agents/plans/. The opl-ai-software-team repo is cloned alongside this repo — use its agent/src/llamaindex_crew/ modules as imports.

SEQUENCE — do these in order, verify each step before moving to next:

PHASE 1 — SCAFFOLD (verify: project installs, ruff passes)
1. Create src/ layout: crew_agent/ package with __init__.py, main.py
2. Create pyproject.toml with deps: google-adk>=2.13, a2a-sdk, fastmcp, litellm, httpx, pydantic, psycopg[binary], ruff
3. Set up PYTHONPATH to import from ../opl-ai-software-team/agent/src/
4. Create Containerfile.agent using UBI9 base, non-root USER 1001
5. Run: pip install -e . && ruff check src/

PHASE 2 — MCP SERVERS (verify: all 3 start, tools callable, tests pass)
6. Build src/crew_agent/mcp/workspace_server.py: wrap file_tools.py write_file/read_file/list_files + git_tools.py git_init/git_commit/git_diff as fastmcp @mcp.tool
7. Build src/crew_agent/mcp/sandbox_server.py: wrap sandbox_client.py create/upload/execute/delete as MCP tools, add K8s Agent Sandbox backend
8. Build src/crew_agent/mcp/memory_server.py: wrap context_memory.py recall/add/search + corrections as MCP tools
9. Write tests/test_workspace_mcp.py, tests/test_sandbox_mcp.py, tests/test_memory_mcp.py
10. Run: pytest tests/test_*_mcp.py -v

PHASE 3 — ADK AGENTS (verify: both start, serve Agent Cards at /.well-known/agent.json)
11. Build src/crew_agent/adapter.py: thin wrapper existing agent → ADK Agent with McpToolset + LiteLlm
12. Build src/crew_agent/agents/meta.py: wrap Meta Agent in ADK shell + A2A server
13. Build src/crew_agent/agents/dev.py: wrap Dev Agent in ADK shell + A2A server
14. Build src/crew_agent/main.py: AGENT_ROLE env selects agent, starts adk api_server --a2a on port 9000
15. Test: start meta agent, curl http://localhost:9000/.well-known/agent.json

PHASE 4 — WORKFLOW (verify: submit vision via API → meta runs → dev runs → files in workspace)
16. Build src/crew_agent/workflow/graph.py: ADK graph workflow meta → dev (2-node spike)
17. Build src/crew_agent/orchestrator/app.py: FastAPI with POST /api/jobs, GET /api/jobs/{id}, GET /health
18. Write tests/test_workflow.py: submit vision, assert files generated
19. Run: pytest tests/test_workflow.py -v

PHASE 5 — K8S DEPLOY (verify: all pods healthy, A2A discovery works, MCP gateway routes)
20. Deploy MemMachine: Postgres 16 + pgvector (StatefulSet), Neo4j Community (StatefulSet), MemMachine app (Deployment)
21. Install K8s Agent Sandbox operator: kubectl apply -f agent-sandbox install manifest
22. Write Helm subcharts: orchestrator, mcp-gateway, workspace-mcp, sandbox-mcp, memory-mcp, generic agent (aliased per role)
23. Write skaffold.yaml with file-sync for src/**/*.py
24. Deploy: skaffold dev --default-repo=<internal-registry>
25. Verify: kubectl get pods -l app.kubernetes.io/part-of=opl-crew — all Running
26. Verify: curl http://meta-agent:9000/.well-known/agent.json from inside cluster

PHASE 6 — FULL PIPELINE (verify: full pipeline runs, sandbox tests pass)
27. Wrap remaining agents: PO, Architect, Designer, Frontend, DevOps, QA
28. Build full ADK workflow graph: meta → stack_contract → PO → architect → [dev|frontend|devops] → QA with HITL gates
29. Write SandboxTemplate CRDs: python-runner, node-runner, java-runner
30. Deploy SandboxWarmPool (2 warm sandboxes)
31. NetworkPolicies: agents → gateway only, orchestrator → agents only
32. End-to-end: POST /api/jobs with "Build a FastAPI todo app" → wait → verify files + sandbox test pass

PHASE 7 — EVAL (verify: scorecard computes, grade > 0)
33. Create job_scorecards and eval_benchmark_runs tables in Postgres
34. Build src/crew_agent/eval/scorecard.py: SQL aggregation over job_outcomes + corrections
35. Build src/crew_agent/eval/trends.py: time-series over scorecards
36. Write 5 benchmark YAML files in eval/benchmarks/
37. Build src/crew_agent/eval/runner.py: submit visions, compare scores
38. Add eval endpoints to orchestrator: GET /api/jobs/{id}/scorecard, GET /api/eval/trends, GET /api/eval/benchmarks
39. Run a benchmark, verify scorecard appears

PHASE 8 — VALIDATION & CRITIQUE (verify: everything works, no stubs, no hardcodes)
40. Run 3 different visions through full pipeline: FastAPI app, Frappe app, React + Express app
41. Verify each produces working code (sandbox tests pass)
42. Verify memory plane records corrections and recall works on subsequent jobs
43. Verify eval scorecards compute and trends show data
44. Run ruff on entire codebase — zero errors
45. Audit: no hardcoded URLs/keys, no placeholder code, no missing error handling
46. Write SUMMARY.md: what works, what needs attention, known limitations

CRITIQUE AFTER EVERY PHASE: Review your own work before moving on. Check for hardcoded values, missing error handling, tests that don't test real behavior, placeholder code, security issues, and deviation from the architecture in AGENTS.md.
```

## Alternative: Phase-by-phase goals

If you prefer tighter control, run each phase as a separate `/goal`:

```
/goal PHASE 1: Scaffold the ast-agent project. See AGENTS.md for tech stack and .agents/plans/agent-swarm-platform.md for full plan. Create pyproject.toml, src/crew_agent/ layout, Containerfile.agent. Verify: pip install -e . && ruff check src/ passes.
```

Then after review:

```
/goal PHASE 2: Build 3 MCP servers (workspace, sandbox, memory) using fastmcp. Wrap existing functions from ../opl-ai-software-team/agent/src/llamaindex_crew/tools/. Write integration tests. Verify: pytest tests/test_*_mcp.py passes.
```

And so on. This gives you review gates between phases.

## Using /plan for complex phases

For phases with architectural decisions, use `/plan` first:

```
/plan How should we structure the ADK workflow graph for the full pipeline (phase 6)? Consider: conditional branches for fast/full solutioning, parallel fan-out for dev+frontend+devops, HITL gates for plan review.
```

Review the plan, then `/goal` to execute it.
