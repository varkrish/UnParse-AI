---
name: Studio v2 mockup
overview: "Create a self-contained shadcn/ui + Tailwind + Vite prototype of \"OPL Studio v2\" with mock data (no backend required). The UI follows a Cursor/Devin-inspired IDE layout but renders all of OPL's unique capabilities beautifully: dynamic agent swarm visibility (A2A Agent Cards), DAG-based workflow timeline, MCP tool attribution, cross-job memory recall, plan-driven development with human-in-the-loop gates, and enterprise collaboration (Jira, teams)."
todos:
  - id: scaffold
    content: Scaffold Vite + React + TypeScript project in `opl-studio-v2/`, init shadcn/ui with nova preset, add Tailwind v4, Monaco, configure Red Hat fonts and color tokens
    status: pending
  - id: mock-data
    content: "Create mock data fixtures in `src/mock/` -- A2A Agent Cards, workflow DAG definition, MCP tool invocations, memory recall results, jobs, messages, file tree, timeline events, plan artifacts, validation issues"
    status: pending
  - id: home-screen
    content: "Build the Home screen: dark hero prompt, mode switcher, recent projects with status/cost/agent summary/memory badge, Jira quick-link"
    status: pending
  - id: workspace-shell
    content: "Build the Workspace shell: 3-panel resizable layout (file tree | editor tabs | crew chat) + collapsible bottom Crew Timeline (DAG)"
    status: pending
  - id: crew-chat
    content: "Build the Crew Chat panel: agent-attributed messages from dynamic agent roster, MCP tool call cards with server origin badges, user refinement input with scope selector"
    status: pending
  - id: crew-timeline
    content: "Build the Crew Timeline as a DAG: render workflow graph with conditional branches (fast/full solutioning), parallel swim lanes (dev+frontend+devops), HITL gate markers, phase durations, cost/token ticker"
    status: pending
  - id: agent-panel
    content: "Build the Agent Swarm panel: dynamic agent cards from A2A Agent Card metadata (name, description, skills, URL, status), instance count badges for scaled agents, health dots"
    status: pending
  - id: plan-review
    content: "Build the Plan Review experience: split view (plan markdown left, stories/feedback right), Memory Recall sidebar showing what the system remembered from past jobs, approve/refine buttons, feedback history, solution candidate comparison"
    status: pending
  - id: editor-tabs
    content: "Build the editor area: Monaco code editor tab, Plan markdown viewer tab, Terminal/logs tab, Validation report tab with mock output"
    status: pending
  - id: settings-sheet
    content: "Build Settings as a Sheet overlay with tabs: LLM config, GitHub, Jira, Workflow, MCP Servers (health + add/remove), Agent Registry (discovered A2A agents), Memory (connection status, recall stats, correction count)"
    status: pending
  - id: eval-scorecard-ui
    content: "Build per-job Scorecard tab in workspace: grade gauge, validation pass rate, first-pass rate, corrections count, cost/file, stub rate, memory utilization, side-by-side with previous job for same framework"
    status: pending
  - id: eval-dashboard
    content: "Build Factory Health dashboard page: trend charts (grade, pass rate, corrections, cost over time), scoped by framework/domain filter, benchmark run history with pass/fail badges, factory-wide KPI summary cards"
    status: pending
isProject: false
---

# OPL Studio v2 -- Mockup Prototype

## What makes this different from Devin / Cursor

The mockup renders **five differentiating capabilities** of OPL's agent swarm platform in a modern IDE shell:

### 1. Dynamic agent swarm visibility (A2A Agent Cards)
- **Agent presence bar**: Agents are **discovered dynamically** from A2A Agent Cards, not hardcoded. Each agent has a name, description, skills list, and URL. The roster adapts based on what agents are registered in the platform.
- **Instance count badges**: When the platform scales an agent (e.g., 3 Dev Agents for parallel file gen), the avatar shows an instance count badge ("x3")
- **Agent-attributed chat**: Every message in the chat panel is tagged with which agent produced it, using distinct colors and role badges. You see the *team conversation* -- the Architect proposing a stack, the PO challenging scope, the Developer asking clarifying questions
- **MCP tool call cards**: Inline in the chat, show when an agent invokes an MCP tool with **server origin badge** (e.g., "Developer > `workspace://write_file` src/app.py", "QA > `sandbox://execute` pytest") with duration and result status
- **Live cost/token burn**: Per-agent token counters updating in real-time; a budget gauge showing spend vs. limit

### 2. DAG workflow timeline (ADK graph)
- **Graph-based timeline**: Instead of a fixed linear pipeline, the timeline renders the **ADK workflow graph** as a DAG -- conditional branches (fast vs full solutioning path), parallel swim lanes (dev + frontend + devops running simultaneously), merge points
- **HITL gate markers**: Visible diamond markers where the human approved the plan, approved the solution, or requested changes
- **Phase durations**: Each node shows elapsed time; active nodes pulse
- **Dynamic shape**: The graph structure comes from the workflow definition (YAML / ADK graph), so different job types (build, refactor, migrate, import) show different pipeline shapes

### 3. Plan-driven development with human gates + memory recall
- **Plan review screen**: When a job hits `pending_review`, the workspace transforms into a split view: rendered plan markdown on the left, extracted user stories on the right, with Approve / Request Changes buttons
- **Memory Recall sidebar**: Shows what the cross-job memory plane recalled for this job -- "Last time on Frappe + MariaDB: reviewers rejected hardcoded currency, missing multi-tenant isolation, Containerfile used wrong base image." This makes the system's learning visible.
- **Feedback history**: Previous feedback rounds shown as a conversation thread -- your feedback, the AI's revision, your next feedback
- **Solution comparison**: When solutioning is enabled, show candidate solutions side-by-side with the critique agent's assessment

### 4. Factory health + eval (AI Factory metrics)
- **Per-job scorecard**: Every completed job gets a grade (0-100) computed from validation pass rate, first-pass rate, corrections needed, cost efficiency, and memory utilization. Shown as a tab in the workspace view alongside Code/Plan/Terminal/Validation.
- **Grade gauge**: Large circular gauge showing the job's composite grade with color (red < 50, amber 50-75, green > 75)
- **Metric cards**: Validation pass rate, first-pass rate, corrections count, cost/file, stub rate, recalls used — each with a delta arrow comparing to the average for that framework
- **Trend charts**: Line charts showing grade, pass rate, corrections, and cost/file over time, scoped by framework and domain. Answers "is the factory getting better?"
- **Benchmark dashboard**: Table of benchmark suites (Frappe CRM, FastAPI Todo, Quarkus REST...) with latest run grade, pass/fail badge, and delta vs baseline. Click a benchmark to see run history chart.
- **Factory KPI summary**: Top-level cards on the Home screen or a dedicated dashboard page — "92% avg pass rate this week", "Corrections down 40% vs last month", "32 jobs completed, $14.20 total cost"

### 5. Enterprise collaboration + observability
- **Jira badge on projects**: Projects linked to Jira issues show the issue key as a clickable badge throughout the UI
- **Team workspace selector**: Dropdown in the header to switch team context
- **Project source indicators**: Visual distinction between Build, MTA Migration, Refactor, and Import jobs
- **Validation report tab**: Inline validation results with severity badges and fix status
- **Memory health indicator**: Small dot in header showing MemMachine connection status (green = connected, amber = fail-open, gray = disabled). Memory is an accelerant, not a dependency -- the UI reflects this.
- **Correction count on completed jobs**: Badge showing "12 corrections learned" -- makes the flywheel visible

## Layout

### Screen 1: Home

```
+------------------------------------------------------------------+
|  [RH Logo] AI Crew Studio    [mem:*]    [team: platform] [gear]  |
+------------------------------------------------------------------+
|                                                                    |
|              What should your AI crew build?                       |
|                                                                    |
|         +----------------------------------------------+           |
|         |  Describe your application...          [->]  |           |
|         +----------------------------------------------+           |
|         [ Build ]  [ Migrate ]  [ Refactor ]  [ Import ]          |
|                                                                    |
|         [+ Attach files]  [+ GitHub repo]  [+ Jira issue]         |
|                                                                    |
|  ----------------------------------------------------------------  |
|                                                                    |
|  Recent Projects                                                   |
|  +--------------------+ +--------------------+ +----------------+  |
|  | Invoice API        | | MTA: EAP->Quarkus | | Frappe CRM     |  |
|  | completed  $0.42   | | running  72%       | | pending review |  |
|  | 5 agents   2h ago  | | 4 agents  live     | | plan ready     |  |
|  | 8 corrections      | | 2x Dev scaling     | | 3 recalls used |  |
|  | JIRA-123           | |                    | | JIRA-456       |  |
|  +--------------------+ +--------------------+ +----------------+  |
+------------------------------------------------------------------+
```

Notes vs original:
- `[mem:*]` = memory health indicator (green dot)
- Project cards show "8 corrections" (learned from this job) and "3 recalls used" (past knowledge applied)
- "2x Dev scaling" shows when multiple agent instances are running

### Screen 2: Workspace (active job)

```
+------------------------------------------------------------------+
| [<] Invoice API  [running 72%] [$0.38] [1.2M tok] [mem:*] [gear] |
+------------------------------------------------------------------+
| File     | Code | Plan | Terminal | Validation |   Crew Chat      |
| Explorer |------|------|----------|------------|                   |
|          | (Monaco editor or plan  | (val tbl)  | [PO] Scope...   |
| > src/   |  with active tab)      |            | [Arch] I propose |
|   app.py |                        |            |   FastAPI + ...  |
|   models/|                        |            |                  |
|   ...    |                        |            | [Dev] workspace  |
|          |                        |            |  ://write_file   |
|          |                        |            |  src/app.py  2.1s|
|          |                        |            |                  |
|          |                        |            | [QA] sandbox     |
|          |                        |            |  ://execute      |
|          |                        |            |  pytest  PASS 4s |
|          |                        |            |                  |
|          |                        |            | [You] __________ |
|          |                        |            | [file|impact|all]|
+----------+------------------------+------------+------------------+
| Crew Timeline (DAG)                                               |
|                                                                    |
| [Meta]-->[Stack?]--+--fast-->[PO]-->[Arch GATE]--+               |
|                    |                              |               |
|                    +--full-->[Solutioning GATE]---+               |
|                                                   |               |
|                                        +----------+---------+    |
|                                        |          |          |    |
|                                      [Dev x2] [Frontend] [DevOps]|
|                                        |          |          |    |
|                                        +----------+---------+    |
|                                                   |               |
|                                                 [QA]              |
|                                                                    |
| PO(done) Arch(done) Dev(working x2) Frontend(working) DevOps(q)  |
| 2m       5m         12m (live)       8m (live)                    |
+------------------------------------------------------------------+
```

Notes vs original:
- Timeline is a **DAG** with conditional branch (fast/full solutioning) and parallel fan-out (dev + frontend + devops)
- Tool call cards show MCP server origin: `workspace://write_file`, `sandbox://execute`
- Dev agent shows "x2" instance count when scaling
- Diamond markers for HITL gates

### Screen 2b: Plan Review with Memory Recall

```
+------------------------------------------------------------------+
| [<] Frappe CRM  [pending review]                     [team] [gear]|
+------------------------------------------------------------------+
| Plan                          | Stories & Feedback    | Recalled   |
|                               |                       |            |
| # Solution Spec              | User Stories           | From past  |
| ## Overview                  | [ ] As a user, I can  | jobs:      |
| This application will...     | [ ] As an admin, I can|            |
|                               | [ ] As a manager...   | ! Reviewers|
| # Tech Stack                 |                       |   rejected |
| - Backend: Frappe            | Feedback History      |   hardcoded|
| - Database: MariaDB         | Round 1: "Add multi-  |   currency |
| - Frontend: Frappe client   |   currency" -> revised |   (job #42)|
|                               | Round 2: (current)    |            |
| # Implementation Plan        |                       | ! Missing  |
| Phase 1: DocTypes...         | +------------------+  |   tenant   |
| Phase 2: Controllers...     | | Feedback... [->]  |  |   isolation|
|                               | +------------------+  |   (job #38)|
|                               | [Approve] [Changes]   |            |
+------------------------------------------------------------------+
| Crew Timeline (DAG)                                               |
| [Meta]-->[Stack]-->[PO]-->[WAITING FOR REVIEW]                   |
+------------------------------------------------------------------+
```

Notes vs original:
- New **Recalled** sidebar showing what the memory plane injected from past jobs
- Past corrections are surfaced with the job they came from
- This makes the cross-job learning flywheel visible to the user

### Screen 3: Agent Swarm (expanded view)

```
+------------------------------------------------------------------+
| [<] Agent Swarm                                      [team] [gear]|
+------------------------------------------------------------------+
|                                                                    |
|  Registered Agents (A2A)                      [Refresh Discovery] |
|                                                                    |
|  +---------------------+ +---------------------+ +--------------+ |
|  | Meta Agent      [*] | | Product Owner   [*] | | Designer [*] | |
|  | Orchestrator        | | Requirements        | | UX/UI        | |
|  | qwen3-14b           | | qwen3-14b           | | granite-8b   | |
|  | Skills: vision      | | Skills: stories,    | | Skills: UX,  | |
|  |   analysis, triage  | |   BDD, acceptance   | |   wireframes | |
|  | URL: meta:9001      | | URL: po:9002        | | URL: des:9003| |
|  | Instances: 1        | | Instances: 1        | | Instances: 1 | |
|  +---------------------+ +---------------------+ +--------------+ |
|                                                                    |
|  +---------------------+ +---------------------+ +--------------+ |
|  | Dev Agent       [*] | | Frontend Agent  [*] | | DevOps   [*] | |
|  | Implementation      | | UI Implementation   | | Containers   | |
|  | qwen3-14b           | | granite-8b          | | qwen3-14b    | |
|  | Skills: code gen,   | | Skills: React,      | | Skills: K8s, | |
|  |   wiring, tests     | |   PatternFly, a11y  | |   CI/CD, OCI | |
|  | URL: dev:9004       | | URL: fe:9005        | | URL: ops:9006| |
|  | Instances: 2 (auto) | | Instances: 1        | | Instances: 1 | |
|  +---------------------+ +---------------------+ +--------------+ |
|                                                                    |
|  MCP Tool Servers                                                  |
|  +-------------------+ +-------------------+ +------------------+ |
|  | workspace (local) | | sandbox (podman)  | | memory (memmach) | |
|  | 8 tools  healthy  | | 3 tools  healthy  | | 4 tools  healthy | |
|  +-------------------+ +-------------------+ +------------------+ |
|  +-------------------+ +-------------------+                      |
|  | skills (service)  | | external (user)   |                      |
|  | 2 tools  healthy  | | 0 tools  --       |                      |
|  +-------------------+ +-------------------+                      |
+------------------------------------------------------------------+
```

### Screen 4: Factory Health Dashboard

```
+------------------------------------------------------------------+
| [RH Logo] AI Crew Studio > Factory Health    [team] [mem:*] [gear]|
+------------------------------------------------------------------+
|                                                                    |
|  Factory KPIs (last 30 days)                                       |
|  +-------------+ +-------------+ +-----------+ +----------------+ |
|  | Avg Grade   | | Pass Rate   | | Corrects  | | Cost / File    | |
|  |   78 (+6)   | |  89% (+4%)  | | 1.8 (-40%)| | $0.035 (-12%) | |
|  |   [chart]   | |   [chart]   | |  [chart]  | |   [chart]      | |
|  +-------------+ +-------------+ +-----------+ +----------------+ |
|                                                                    |
|  Quality Trends           [Framework: Frappe v] [Domain: All v]    |
|  +--------------------------------------------------------------+ |
|  | Grade                                                         | |
|  | 80 |                                          ___-----        | |
|  | 70 |                              ___-----""""                | |
|  | 60 |                  ___-----""""                            | |
|  | 50 |      ___-----""""                                       | |
|  |    +--+----+----+----+----+----+----+----+----+----+----+    | |
|  |      W1   W2   W3   W4   W5   W6   W7   W8   W9  W10  W11  | |
|  +--------------------------------------------------------------+ |
|                                                                    |
|  Benchmarks                                          [Run All]     |
|  +------------------+-------+--------+--------+------------------+ |
|  | Benchmark        | Grade | Status | Delta  | Last Run         | |
|  +------------------+-------+--------+--------+------------------+ |
|  | Frappe CRM       |  82   |  PASS  |  +12   | 2026-10-25       | |
|  | FastAPI Todo     |  91   |  PASS  |  +8    | 2026-10-25       | |
|  | Quarkus REST     |  68   |  WARN  |  +3    | 2026-10-24       | |
|  | React Dashboard  |  74   |  PASS  |  +15   | 2026-10-25       | |
|  | Flask + Postgres |  85   |  PASS  |  +5    | 2026-10-23       | |
|  +------------------+-------+--------+--------+------------------+ |
|                                                                    |
|  Recent Jobs (with grades)                                         |
|  +------------------+-------+--------+-------+---+---+           | |
|  | Invoice API      |  87   |  $0.42 | 14/16 | 3 | 2 |           | |
|  | Frappe CRM       |  74   |  $0.58 | 12/16 | 5 | 3 |           | |
|  | MTA Migration    |  81   |  $0.31 |  9/10 | 1 | 4 |           | |
|  +------------------+-------+--------+-------+---+---+           | |
|  (columns: name, grade, cost, validation, corrections, recalls)    |
+------------------------------------------------------------------+
```

### Screen 2c: Job Scorecard tab (in workspace)

```
+------------------------------------------------------------------+
| [<] Invoice API  [completed]  [$0.42]  [grade: 87]  [mem:*] [gear]|
+------------------------------------------------------------------+
| File     | Code | Plan | Terminal | Validation | Scorecard |  Chat |
| Explorer |------|------|----------|------------|-----------|       |
|          |                                                 |       |
|          |  Grade: 87/100                  [vs avg: +9]    |       |
|          |  +--------+                                     |       |
|          |  |   87   |  (circular gauge, green)            |       |
|          |  +--------+                                     |       |
|          |                                                 |       |
|          |  Quality                    Efficiency           |       |
|          |  +-----------------------+  +------------------+ |       |
|          |  | Pass rate:  87.5%  +4 |  | Cost:     $0.42  | |       |
|          |  | 1st pass:   56.3%  +8 |  | Per file: $0.035 | |       |
|          |  | Stub rate:  0%     =  |  | Tokens:   1.2M   | |       |
|          |  | Corrects:   3     -2  |  | Time:     23 min | |       |
|          |  | Refines:    1     -1  |  | Files:    12      | |       |
|          |  +-----------------------+  +------------------+ |       |
|          |                                                 |       |
|          |  Memory                                          |       |
|          |  +-----------------------+                       |       |
|          |  | Recalls used: 2/4     |                       |       |
|          |  | Corrects written: 3   |                       |       |
|          |  | Knowledge reuse: 50%  |                       |       |
|          |  +-----------------------+                       |       |
|          |                                                 |       |
+----------+-------------------------------------------------+-------+
```

## Type definitions (updated for A2A + MCP)

```typescript
// A2A Agent Card -- replaces static Agent type
interface AgentCard {
  name: string;
  description: string;
  url: string;
  skills: string[];
  model: string;
  status: 'idle' | 'working' | 'completed' | 'error';
  instances: number;           // scaling count
  last_activity: string | null;
  last_activity_at: string | null;
}

// MCP tool invocation -- replaces generic tool call
interface McpToolCall {
  agent: string;               // which agent invoked it
  server: string;              // MCP server origin: "workspace", "sandbox", "memory", "skills"
  tool: string;                // tool name: "write_file", "execute", "recall"
  args: Record<string, unknown>;
  result_status: 'success' | 'error';
  duration_ms: number;
  timestamp: string;
}

// MCP server status
interface McpServer {
  name: string;
  transport: 'stdio' | 'sse';
  url?: string;
  tools: string[];
  status: 'healthy' | 'degraded' | 'down';
}

// Workflow DAG node -- replaces linear PHASE_ORDER
interface WorkflowNode {
  id: string;
  label: string;
  type: 'sequential' | 'parallel' | 'conditional' | 'gate';
  agent?: string;              // A2A agent name
  status: 'pending' | 'active' | 'completed' | 'skipped' | 'failed';
  duration_ms?: number;
  children?: WorkflowNode[];   // for parallel/conditional
  branches?: Record<string, WorkflowNode[]>;  // for conditional (fast/full)
  gate_approved?: boolean;     // for HITL gates
}

// Memory recall result -- surfaced in Plan Review
interface MemoryRecall {
  source_job_id: string;
  source_job_vision: string;
  content: string;             // what was recalled
  category: 'correction' | 'blueprint' | 'reference';
  relevance_score: number;
}

// Memory status
interface MemoryStatus {
  connected: boolean;
  mode: 'active' | 'fail-open' | 'disabled';
  corrections_count: number;   // total corrections stored
  recalls_this_job: number;    // how many recalls used for current job
}

// Per-job scorecard
interface JobScorecard {
  job_id: string;
  framework: string;
  domain: string;
  grade: number;               // 0-100 composite
  validation_pass_rate: number; // 0-1
  first_pass_rate: number;     // 0-1
  avg_iterations: number;
  stub_rate: number;           // 0-1
  corrections_count: number;
  refinement_rounds: number;
  total_cost: number;
  total_tokens: number;
  cost_per_file: number;
  wall_time_seconds: number;
  files_generated: number;
  recalls_used: number;
  recall_candidates: number;
  corrections_written: number;
  status: string;
  // Deltas vs framework average
  deltas: Record<string, number>;
}

// Trend data point
interface TrendPoint {
  period: string;              // "2026-W42", "2026-10"
  avg_grade: number;
  avg_pass_rate: number;
  avg_corrections: number;
  avg_cost_per_file: number;
  job_count: number;
}

// Benchmark definition + latest run
interface Benchmark {
  name: string;
  framework: string;
  domain: string;
  latest_grade: number | null;
  latest_status: 'pass' | 'warn' | 'fail' | 'never_run';
  delta_vs_baseline: number;
  last_run_at: string | null;
}

// Benchmark run history entry
interface BenchmarkRun {
  benchmark: string;
  job_id: string;
  grade: number;
  pass_rate: number;
  cost: number;
  met_expected: boolean;
  delta_vs_baseline: number;
  created_at: string;
}
```

## Tech stack

- **Vite + React 18 + TypeScript**
- **shadcn/ui** (nova preset) + **Tailwind CSS v4**
- **Monaco Editor** (`@monaco-editor/react`)
- **Lucide icons** (shadcn default) + Red Hat logo SVG inline
- **No backend required** -- all data from `src/mock/` fixtures
- **React Router** for Home vs Workspace vs Agent Swarm navigation
- **Resizable panels** via shadcn `Resizable` component
- **dagre** or **elkjs** for DAG layout in the Crew Timeline (lightweight graph layout)
- **recharts** for trend charts and gauge visualizations in the Factory Health dashboard

## Project structure

```
opl-studio-v2/
  src/
    components/
      layout/
        app-shell.tsx          # resizable 3-panel workspace shell
        header.tsx             # top bar: back, job name, status, cost, memory dot, settings
      chat/
        crew-chat.tsx          # agent-attributed chat panel
        message-bubble.tsx     # styled per agent role (dynamic from AgentCard)
        mcp-tool-card.tsx      # MCP tool invocation card with server origin badge
        scope-selector.tsx     # file / impact / project toggle group
        prompt-input.tsx       # chat input with attach + send
      crew/
        crew-timeline.tsx      # DAG pipeline visualization (dagre/elkjs layout)
        agent-avatar.tsx       # role-colored avatar with status dot + instance badge
        agent-presence-bar.tsx # row of agent avatars (dynamic from A2A discovery)
        dag-node.tsx           # workflow graph node (replaces phase-node)
        gate-marker.tsx        # HITL approval gate (diamond shape)
        branch-indicator.tsx   # conditional branch label (fast/full)
        cost-ticker.tsx        # live cost / token counter
      agents/
        agent-swarm-view.tsx   # full Agent Swarm page (A2A cards + MCP servers)
        agent-card.tsx         # single A2A agent card with skills, URL, instances
        mcp-server-card.tsx    # MCP server status card (tools count, health)
      editor/
        editor-tabs.tsx        # tab bar
        code-editor.tsx        # Monaco wrapper
        plan-viewer.tsx        # rendered markdown
        terminal-panel.tsx     # log output
        validation-tab.tsx     # validation issues table
      home/
        hero-prompt.tsx        # centered prompt input
        project-card.tsx       # recent project card (+ corrections/recalls badges)
        mode-switcher.tsx      # build/migrate/refactor/import
      plan-review/
        plan-review-view.tsx   # split plan + stories + feedback + recall sidebar
        story-list.tsx         # extracted user stories
        feedback-thread.tsx    # feedback history
        recall-sidebar.tsx     # memory recall results from past jobs
      eval/
        scorecard-tab.tsx      # per-job scorecard (grade gauge + metric cards + deltas)
        grade-gauge.tsx        # circular grade gauge (0-100, color-coded)
        metric-card.tsx        # single metric with value + delta arrow
        trend-chart.tsx        # line chart for a metric over time (recharts)
        factory-dashboard.tsx  # full Factory Health page (KPIs + trends + benchmarks)
        benchmark-table.tsx    # benchmark list with grade, status, delta, run history
        kpi-summary.tsx        # top-level KPI cards (avg grade, pass rate, corrections trend)
      settings/
        settings-sheet.tsx     # overlay with tabs
        llm-form.tsx           # LLM config
        github-form.tsx        # GitHub config
        jira-form.tsx          # Jira config
        workflow-form.tsx      # Workflow prefs
        mcp-servers-form.tsx   # MCP server management (add/remove/health)
        agent-registry.tsx     # Discovered A2A agents (read-only + refresh)
        memory-status.tsx      # Memory plane status + stats
    mock/
      agents.ts                # A2A Agent Cards (dynamic roster, skills, URLs)
      workflow.ts              # Workflow DAG definition (nodes, edges, branches)
      mcp-servers.ts           # MCP server definitions + tool lists
      mcp-tool-calls.ts       # Sample MCP tool invocations with server origins
      memory.ts                # Memory recall results + status + corrections
      jobs.ts                  # 3 sample jobs with memory badges
      files.ts                 # file tree + contents
      plan.ts                  # plan artifacts + stories
      validation.ts            # sample validation issues
      scorecards.ts            # mock scorecards for 3 sample jobs (with deltas)
      trends.ts                # mock trend data (12 weeks, 2 frameworks)
      benchmarks.ts            # mock benchmark definitions + run history
    lib/
      utils.ts                 # cn() helper
      dag-layout.ts            # DAG layout helpers (dagre/elkjs wrapper)
      agents.ts                # agent color/icon derivation from AgentCard metadata
      types.ts                 # TypeScript interfaces (AgentCard, McpToolCall, WorkflowNode, etc.)
    pages/
      home.tsx                 # Home screen
      workspace.tsx            # Workspace screen (job active, now with Scorecard tab)
      agent-swarm.tsx          # Agent Swarm page (A2A cards + MCP servers)
      factory-health.tsx       # Factory Health dashboard page
    App.tsx                    # Router: / -> Home, /job/:id -> Workspace, /agents -> AgentSwarm, /factory -> FactoryHealth
    main.tsx
    index.css                  # Tailwind + RH fonts + color tokens
```

## Red Hat theming

Override shadcn CSS variables in `index.css` to match Red Hat brand:

- `--primary`: `#ee0000` (red-50) -- brand accent
- `--primary-foreground`: `#ffffff`
- `--background`: `#151515` (gray-95) -- dark mode
- `--foreground`: `#f2f2f2` (gray-10)
- `--card`: `#1e1e1e`
- `--muted`: `#292929` (gray-80)
- `--muted-foreground`: `#a3a3a3`
- `--accent`: `#292929`
- `--accent-foreground`: `#f2f2f2`
- `--border`: `#333333`
- `--ring`: `#ee0000`
- `--destructive`: `#f0561d` (danger orange, not red-50)
- Fonts: Red Hat Display (headings), Red Hat Text (body), Red Hat Mono (code)

## What is deferred (not in mockup)

- Real backend API calls (A2A, MCP gateway, memory plane)
- Authentication / OIDC
- Full Migration / Refactor / Import flows
- Skills browser page
- Granular task kanban board
- Push to Git / Download ZIP
- Jira issue search typeahead
- A2A SSE real-time streaming (mockup uses static data; production wires to A2A SSE)
- Agent auto-scaling controls (viewing scale is in, controlling scale is deferred)
- MCP tool schema browser (viewing tool names is in, browsing full schemas is deferred)
