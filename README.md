# UnParse 🚀

**UnParse** is an innovative code-generation framework that flips the paradigm of traditional LLM coding agents. Instead of asking an AI to generate raw, error-prone text, UnParse forces the LLM to act as a **Graph Architect**.

By restricting the LLM to strict schema-based tool calls, UnParse constructs an **Abstract Syntax Tree (AST)** directly inside a Kùzu Graph Database. This graph is entirely language-agnostic and logically flawless. 

Once the logic is mapped in the Graph DB, UnParse transpiles the AST directly into perfectly valid source code across multiple languages—guaranteeing 100% syntactically correct code every single time.

## 🌟 The Innovation

When an LLM generates raw Python or Java text, it is prone to indentation errors, mismatched brackets, and hallucinations. 

**UnParse solves this by eliminating text generation completely:**
1. **Graph-First Architecture**: The LLM uses LangGraph to emit strict JSON tool calls (e.g., `add_statement`, `add_expression`) to build a graph of nodes and edges.
2. **Deterministic Syntactic Validity**: Because the code is built node-by-node according to a rigid AST schema, it is physically impossible to generate syntax errors. 
3. **Polyglot Transpilation**: The Kùzu database holds pure logic. You can point the Python unparser at the database and get perfect Python, or point the Java unparser at the exact same database and get perfect Java.
4. **Deep Cypher Querying**: Because the entire codebase lives in a Graph Database, you can run complex analytical Cypher queries over your application logic (e.g., *"Find all assignments that eventually call `days_remaining`"*).

## 🛠️ How It Works

1. **Schema Initialization**: `run.py` initializes a Kùzu graph database with 26 node tables (Functions, Classes, Assigns, Calls) and 207 edge tables.
2. **LLM Agent**: A LangGraph agent parses a multi-file software spec. The LLM (e.g. GPT-4o, Qwen 35B) recursively calls AST tools to populate the Kùzu graph.
3. **Unparsing**: Custom unparsers (`unparser.py` for Python, `java_unparser.py` for Java) traverse the Kùzu graph and transpile the logic into native source code.

## 🚀 Quick Start

Ensure you have your environment variables set up in `.env` (we recommend highly capable reasoning models like GPT-4o or Claude 3.5 Sonnet via OpenRouter):

```bash
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=openai/gpt-4o
LLM_API_KEY=your_api_key_here
```

### 1. Generating a Complete Full-Stack App
To run the full-stack generation pipeline on a single high-level vision prompt:
```bash
python3 run_fullstack.py
```
This script will:
- Run the AST agent on Kùzu to represent a full-stack calculator application in the AST graph.
- Scaffold a standard Maven Spring Boot application under `output/backend` and a Vite React application under `output/frontend`.
- Traverses the AST database to write clean code directly into their respective scaffold directories.

### 2. Running Python AST transpile
Run the agent to populate the Graph DB and unparse to Python:
```bash
python3 run.py
```

### 3. Run Java AST transpile manually
Run the Java unparser against the populated database:
```bash
python3 -c "import kuzu, java_unparser; conn = kuzu.Connection(kuzu.Database('ast_db')); java_unparser.unparse_java_project(conn, 'java_output')"
```

## 🧠 Architecture Overview

- `src/ast_agent/agent/graph.py`: The custom LangGraph state machine.
- `src/ast_agent/tools/ast_tools.py`: The rigid tool schema exposed to the LLM.
- `schema.py`: The strict Kùzu database definitions.
- `unparser.py`: Traverses the graph and generates Python.
- `java_unparser.py`: Traverses the same graph and generates Java.

## 📦 Multi-Language Dependency Identification

UnParse handles dependencies in a language-agnostic way. The LLM creates generic `Dependency` nodes in Kùzu containing the library `name` and `version` constraint (e.g. `^1.26.0`). The individual unparsers then identify, filter, and adapt these nodes into language-specific package manager files:

### Python (`requirements.txt`)
- The Python unparser filters out Maven coordinates containing colons (`:`).
- It translates semver caret constraints (`^1.26.0`) into standard pip boundaries (`>=1.26.0`).
- It outputs `requirements.txt`.

### Java (`pom.xml`)
- The Java unparser checks if the dependency name has a colon (`:`).
- If it does (e.g., `org.apache.commons:commons-math3`), it splits it into `<groupId>` and `<artifactId>`. 
- If not (e.g., `numpy`), it defaults the `groupId` to `org.example` and sets the `artifactId` to the package name.
- It lstrips semver modifiers (e.g. `^`, `~=`) so Maven receives clean, parsable version numbers.
- It wraps everything into a valid Maven `<project>` configuration.

---

## ⚡ Agent Skills & Execution Workflow

We optimized how the LLM interacts with the AST builder to ensure fast and reliable execution:

1. **Preamble-Free Mode**: The LangGraph state machine checks for tool blocks in the LLM's response. To prevent the state machine from exiting early on planning or chat turns, the system prompts instruct the LLM to **start emitting tool blocks immediately** without conversational preambles.
2. **Direct Function Property Mapping**: For `Call` expressions, the LLM maps the target function name directly using the `func` property on the `Call` node itself, rather than creating separate child `Name` nodes. This architectural optimization reduces LLM tool-calling overhead by **50%**, making it incredibly resilient over large, complex files.
3. **Structured Execution loop**: The state machine iterates back and forth between generating tool calls and executing them against the live Kùzu DB, providing instant feedback to the model before it proceeds to the next AST layer.
