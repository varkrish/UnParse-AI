"""
tools.py — High-level tool functions for AST graph mutation.

This file provides Python functions that the LLM can call as "tools".
Each function maps to deterministic Cypher CREATE/MATCH statements in Kùzu,
preventing Cartesian products and invalid edges.
"""

from __future__ import annotations
import kuzu
import json

# Global reference to connection, will be set by agent.py
_conn: kuzu.Connection | None = None

def set_connection(conn: kuzu.Connection):
    global _conn
    _conn = conn

def _execute(cypher: str, params: dict | None = None):
    if _conn is None:
        raise RuntimeError("Kuzu connection not set in tools.py")
    _conn.execute(cypher, params or {})

# ── AST Tools ─────────────────────────────────────────────────────────────────

def create_module(module_id: str, name: str, decorators: str = "") -> str:
    """Create a new Python file/module."""
    _execute(
        "MERGE (m:Module {id: $id}) SET m.name = $name, m.decorators = $decorators",
        {"id": module_id, "name": name, "decorators": decorators}
    )
    return f"Created Module {module_id} ({name})"

def create_function(module_id: str, func_id: str, name: str, return_type: str, ord: int, decorators: str = "") -> str:
    """Create a new function inside a module."""
    _execute(
        "MERGE (f:Function {id: $id}) SET f.name = $name, f.return_type = $rt, f.decorators = $decorators",
        {"id": func_id, "name": name, "rt": return_type, "decorators": decorators}
    )
    _execute(
        "MATCH (m:Module {id: $mid}), (f:Function {id: $fid}) "
        "MERGE (m)-[:HAS_FUNCTION_Module {ord: $ord}]->(f)",
        {"mid": module_id, "fid": func_id, "ord": ord}
    )
    return f"Created Function {func_id} ({name}) in Module {module_id}"

def add_function_argument(func_id: str, arg_id: str, name: str, type_annotation: str, position: int) -> str:
    """Add an argument to a function."""
    _execute(
        "MERGE (a:Argument {id: $id, name: $name, type_annotation: $ta})",
        {"id": arg_id, "name": name, "ta": type_annotation}
    )
    _execute(
        "MATCH (f:Function {id: $fid}), (a:Argument {id: $aid}) "
        "MERGE (f)-[:HAS_ARG {position: $pos}]->(a)",
        {"fid": func_id, "aid": arg_id, "pos": position}
    )
    return f"Added Argument {arg_id} ({name}) to Function {func_id}"

def create_import(module_id: str, import_id: str, source_module: str, names: str, ord: int) -> str:
    """Create an ImportFrom node in a module (e.g., from tasks.priority import priority_label)."""
    _execute(
        "MERGE (i:ImportFrom {id: $id, module: $module, names: $names})",
        {"id": import_id, "module": source_module, "names": names}
    )
    _execute(
        "MATCH (m:Module {id: $mid}), (i:ImportFrom {id: $iid}) "
        "MERGE (m)-[:HAS_IMPORT_ImportFrom {ord: $ord}]->(i)",
        {"mid": module_id, "iid": import_id, "ord": ord}
    )
    return f"Created ImportFrom {import_id} in Module {module_id}"

def add_dependency(module_id: str, dep_id: str, name: str, version: str, ord: int) -> str:
    """Add a generic package dependency to a module."""
    _execute(
        "MERGE (d:Dependency {id: $id, name: $name, version: $version})",
        {"id": dep_id, "name": name, "version": version}
    )
    _execute(
        "MATCH (m:Module {id: $mid}), (d:Dependency {id: $did}) "
        "MERGE (m)-[:HAS_DEPENDENCY {ord: $ord}]->(d)",
        {"mid": module_id, "did": dep_id, "ord": ord}
    )
    return f"Added Dependency {dep_id} ({name} {version}) to Module {module_id}"

def add_statement(parent_id: str, parent_type: str, stmt_id: str, stmt_type: str, ord: int, branch: str = "") -> str:
    """
    Add a statement node to a block parent (Function, IfStmt, ForLoop, WhileLoop).
    For IfStmt parents, branch must be 'then' or 'else'.
    Example: add_statement('func_main', 'Function', 'ret_main', 'Return', 0)
    """
    # Create the node (basic structure)
    _execute(f"MERGE (s:{stmt_type} {{id: $id}})", {"id": stmt_id})
    
    # Create the edge
    rel_type = f"HAS_STMT_{parent_type}_{stmt_type}"
    _execute(
        f"MATCH (p:{parent_type} {{id: $pid}}), (s:{stmt_type} {{id: $sid}}) "
        f"MERGE (p)-[:{rel_type} {{ord: $ord, branch: $branch}}]->(s)",
        {"pid": parent_id, "sid": stmt_id, "ord": ord, "branch": branch}
    )
    return f"Added Statement {stmt_id} ({stmt_type}) to {parent_type} {parent_id}"

def set_assign_targets(stmt_id: str, targets: str) -> str:
    """Set the targets property for an Assign statement (e.g. 'x, y')."""
    _execute("MATCH (s:Assign {id: $id}) SET s.targets = $targets", {"id": stmt_id, "targets": targets})
    return f"Set targets for {stmt_id} to '{targets}'"

def add_expression(parent_id: str, parent_type: str, expr_id: str, expr_type: str, role: str, ord: int = 0, value: str = "", kind: str = "", func: str = "", op: str = "", ops: str = "") -> str:
    """
    Add an expression node to a parent (Statement or Expression).
    """
    if expr_type == "Compare" and op and not ops:
        ops = op
        op = ""
        
    props = {"id": expr_id, "value": value, "kind": kind, "func": func, "op": op, "ops": ops}
    
    # Filter empty properties so we don't set a bunch of empty strings in Kuzu
    props_filtered = {k: v for k, v in props.items() if v != ""}
    
    # Do not set 'id' in the SET clause as it is the primary key
    set_props = {k: v for k, v in props_filtered.items() if k != "id"}
    set_clause = ", ".join(f"e.{k} = ${k}" for k in set_props.keys())
    
    if set_clause:
        _execute(f"MERGE (e:{expr_type} {{id: $id}}) SET {set_clause}", props_filtered)
    else:
        _execute(f"MERGE (e:{expr_type} {{id: $id}})", props_filtered)
        
    # Create the edge
    rel_type = f"HAS_EXPR_{parent_type}_{expr_type}"
    _execute(
        f"MATCH (p:{parent_type} {{id: $pid}}), (e:{expr_type} {{id: $eid}}) "
        f"MERGE (p)-[:{rel_type} {{role: $role, ord: $ord}}]->(e)",
        {"pid": parent_id, "eid": expr_id, "role": role, "ord": ord}
    )
    return f"Added Expression {expr_id} ({expr_type}) to {parent_type} {parent_id}"

def get_tool_functions():
    return [
        create_module,
        create_function,
        add_function_argument,
        create_import,
        add_dependency,
        add_statement,
        set_assign_targets,
        add_expression,
    ]
