"""
tools.py — High-level tool functions for AST graph mutation.

This file provides Python functions that the LLM can call as "tools".
Each function maps to deterministic Cypher CREATE/MATCH statements in Kùzu,
preventing Cartesian products and invalid edges.

v0.2.0 — All statements write to unified Statement table with kind discriminator.
         All expressions write to unified Expression table with kind discriminator.
         Edge tables are collapsed: one per block-parent type.
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


# ── Parent-type classification ────────────────────────────────────────────────

# Statement kinds that can contain child statements
_STMT_BLOCK_PARENTS = {"IfStmt", "ForLoop", "WhileLoop"}

# Statement kinds (all live in the Statement table)
_STMT_KINDS = {
    "Assign", "Return", "IfStmt", "ForLoop", "WhileLoop",
    "ExprStmt", "Pass", "Break", "Continue",
}

# Expression kinds (all live in the Expression table)
_EXPR_KINDS = {
    "Name", "Constant", "BinOp", "UnaryOp", "Compare",
    "Call", "Attribute", "BoolOp", "IfExp", "ListExpr", "DictExpr",
    "CmpOp",
}

# Branch-to-role mapping for backward compatibility
_BRANCH_TO_ROLE = {
    "then": "body",
    "else": "orelse",
    "body": "body",
    "orelse": "orelse",
    "handlers": "handlers",
    "": "body",
}


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
    For IfStmt parents, branch must be 'then' or 'else' (mapped to role 'body'/'orelse').
    Example: add_statement('func_main', 'Function', 'ret_main', 'Return', 0)
    """
    # Create the Statement node with kind discriminator
    _execute(
        "MERGE (s:Statement {id: $id}) SET s.kind = $kind",
        {"id": stmt_id, "kind": stmt_type}
    )

    # Map branch to role
    role = _BRANCH_TO_ROLE.get(branch, branch if branch else "body")

    # Determine the correct edge table based on parent type
    if parent_type == "Function":
        rel_table = "HAS_STMT_Function"
        _execute(
            f"MATCH (p:Function {{id: $pid}}), (s:Statement {{id: $sid}}) "
            f"MERGE (p)-[:{rel_table} {{ord: $ord, role: $role}}]->(s)",
            {"pid": parent_id, "sid": stmt_id, "ord": ord, "role": role}
        )
    elif parent_type in _STMT_BLOCK_PARENTS:
        rel_table = f"HAS_STMT_{parent_type}"
        _execute(
            f"MATCH (p:Statement {{id: $pid}}), (s:Statement {{id: $sid}}) "
            f"MERGE (p)-[:{rel_table} {{ord: $ord, role: $role}}]->(s)",
            {"pid": parent_id, "sid": stmt_id, "ord": ord, "role": role}
        )
    else:
        raise ValueError(f"Unknown block parent type: {parent_type}")

    return f"Added Statement {stmt_id} ({stmt_type}) to {parent_type} {parent_id}"

def set_assign_targets(stmt_id: str, targets: str) -> str:
    """Set the targets property for an Assign statement (e.g. 'x, y')."""
    _execute(
        "MATCH (s:Statement {id: $id}) SET s.targets = $targets",
        {"id": stmt_id, "targets": targets}
    )
    return f"Set targets for {stmt_id} to '{targets}'"

def add_expression(parent_id: str, parent_type: str, expr_id: str, expr_type: str, role: str, ord: int = 0, value: str = "", kind: str = "", func: str = "", op: str = "", ops: str = "") -> str:
    """
    Add an expression node to a parent (Statement or Expression).
    """
    if expr_type == "Compare" and op and not ops:
        ops = op
        op = ""

    # Build the Expression node with kind discriminator
    props = {"id": expr_id, "kind_disc": expr_type}
    set_parts = ["e.kind = $kind_disc"]

    # Map properties to unified column names
    if value:
        props["value"] = value
        set_parts.append("e.value = $value")
    if kind:
        # Constant.kind → kind_lit (to avoid clash with discriminator)
        props["kind_lit"] = kind
        set_parts.append("e.kind_lit = $kind_lit")
    if func:
        props["func"] = func
        set_parts.append("e.func = $func")
    if op:
        props["op"] = op
        set_parts.append("e.op = $op")
    if ops:
        props["ops"] = ops
        set_parts.append("e.ops = $ops")

    set_clause = ", ".join(set_parts)
    _execute(f"MERGE (e:Expression {{id: $id}}) SET {set_clause}", props)

    # Determine the correct edge table based on parent type
    if parent_type == "Function":
        rel_table = "HAS_EXPR_Function"
        _execute(
            f"MATCH (p:Function {{id: $pid}}), (e:Expression {{id: $eid}}) "
            f"MERGE (p)-[:{rel_table} {{role: $role, ord: $ord}}]->(e)",
            {"pid": parent_id, "eid": expr_id, "role": role, "ord": ord}
        )
    elif parent_type in _STMT_KINDS:
        rel_table = "HAS_EXPR_Statement"
        _execute(
            f"MATCH (p:Statement {{id: $pid}}), (e:Expression {{id: $eid}}) "
            f"MERGE (p)-[:{rel_table} {{role: $role, ord: $ord}}]->(e)",
            {"pid": parent_id, "eid": expr_id, "role": role, "ord": ord}
        )
    elif parent_type in _EXPR_KINDS:
        rel_table = "HAS_EXPR_Expression"
        _execute(
            f"MATCH (p:Expression {{id: $pid}}), (e:Expression {{id: $eid}}) "
            f"MERGE (p)-[:{rel_table} {{role: $role, ord: $ord}}]->(e)",
            {"pid": parent_id, "eid": expr_id, "role": role, "ord": ord}
        )
    else:
        raise ValueError(f"Unknown expression parent type: {parent_type}")

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
