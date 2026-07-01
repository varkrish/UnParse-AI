"""
unparser.py — Reads the Kùzu AST graph and generates valid Python source code.

This is a DETERMINISTIC compiler: given a valid graph, it always produces
syntactically correct Python. It uses Python's own `ast` module internally
so that `ast.unparse()` handles all formatting concerns.

Flow:
  Kùzu graph → Python ast nodes → ast.fix_missing_locations → ast.unparse → str

v0.2.0 — Unified Statement/Expression tables. Dispatch on kind column.
         Single-query edge traversal (no cross-product loops).
"""

from __future__ import annotations

import ast
import textwrap
from typing import Any

import kuzu

from schema import SCHEMA_VERSION
from src.ast_agent.graph_validator import validate_graph, GraphValidationError


# ── helpers ──────────────────────────────────────────────────────────────────

def _q(conn: kuzu.Connection, cypher: str, params: dict | None = None) -> list[dict]:
    """Execute a Cypher query and return rows as a list of dicts."""
    result = conn.execute(cypher, params or {})
    # Use native iteration to avoid numpy/pandas dependency
    col_names = result.get_column_names()
    rows = []
    while result.has_next():
        row = result.get_next()
        rows.append(dict(zip(col_names, row)))
    return rows


def _check_schema_version(conn: kuzu.Connection) -> None:
    """Verify the DB schema version matches the unparser's expected version."""
    try:
        rows = _q(conn, "MATCH (m:SchemaMetadata) RETURN m.version")
        if rows:
            db_ver = rows[0]["m.version"]
            if db_ver != SCHEMA_VERSION:
                raise RuntimeError(
                    f"Schema version mismatch: DB has v{db_ver}, "
                    f"unparser expects v{SCHEMA_VERSION}. "
                    f"Recreate the database with the current schema.py."
                )
    except Exception as e:
        if "SchemaMetadata" in str(e):
            raise RuntimeError(
                f"Database has no SchemaMetadata table. "
                f"This database was created with schema < v0.2.0. "
                f"Recreate with current schema.py."
            )
        raise


# ── expression tree reconstruction ───────────────────────────────────────────

def _build_expr(conn: kuzu.Connection, node_id: str, kind: str) -> ast.expr:
    """Recursively reconstruct an ast.expr subtree from the graph."""

    if kind == "Name":
        rows = _q(conn, "MATCH (n:Expression {id: $id}) RETURN n.value", {"id": node_id})
        return ast.Name(id=rows[0]["n.value"], ctx=ast.Load())

    if kind == "Constant":
        rows = _q(conn, "MATCH (n:Expression {id: $id}) RETURN n.value, n.kind_lit", {"id": node_id})
        raw, kind_lit = rows[0]["n.value"], rows[0]["n.kind_lit"]
        if kind_lit == "int":
            val = int(raw)
        elif kind_lit == "float":
            val = float(raw)
        elif kind_lit == "bool":
            val = raw.lower() == "true"
        elif kind_lit == "none":
            val = None
        else:
            val = raw  # str
        return ast.Constant(value=val)

    if kind == "BinOp":
        rows = _q(conn, "MATCH (n:Expression {id: $id}) RETURN n.op", {"id": node_id})
        op_str = rows[0]["n.op"]
        op_map = {
            "+": ast.Add(), "-": ast.Sub(), "*": ast.Mult(), "/": ast.Div(),
            "//": ast.FloorDiv(), "%": ast.Mod(), "**": ast.Pow(),
            "&": ast.BitAnd(), "|": ast.BitOr(), "^": ast.BitXor(),
        }
        left  = _get_child_expr(conn, node_id, "Expression", "left")
        right = _get_child_expr(conn, node_id, "Expression", "right")
        return ast.BinOp(left=left, op=op_map[op_str], right=right)

    if kind == "UnaryOp":
        rows = _q(conn, "MATCH (n:Expression {id: $id}) RETURN n.op", {"id": node_id})
        op_str = rows[0]["n.op"]
        op_map = {"not": ast.Not(), "-": ast.USub(), "+": ast.UAdd(), "~": ast.Invert()}
        operand = _get_child_expr(conn, node_id, "Expression", "operand")
        return ast.UnaryOp(op=op_map[op_str], operand=operand)

    if kind == "Compare":
        rows = _q(conn, "MATCH (n:Expression {id: $id}) RETURN n.ops, n.op", {"id": node_id})
        ops_str_raw = rows[0].get("n.ops") or rows[0].get("n.op") or ""
        ops_str = ops_str_raw.split(",") if ops_str_raw else []
        op_map = {
            # Symbol form
            "==": ast.Eq(), "!=": ast.NotEq(), "<": ast.Lt(), "<=": ast.LtE(),
            ">": ast.Gt(), ">=": ast.GtE(), "in": ast.In(), "not in": ast.NotIn(),
            "is": ast.Is(), "is not": ast.IsNot(),
            # AST class name form (LLM may use either)
            "Eq": ast.Eq(), "NotEq": ast.NotEq(), "Lt": ast.Lt(), "LtE": ast.LtE(),
            "Gt": ast.Gt(), "GtE": ast.GtE(), "In": ast.In(), "NotIn": ast.NotIn(),
            "Is": ast.Is(), "IsNot": ast.IsNot(),
        }
        left = _get_child_expr(conn, node_id, "Expression", "left")
        # LLM may use 'comparator' or 'right' for the right-hand side(s)
        comparators = _get_ordered_child_exprs(conn, node_id, "Expression", "comparator")
        if not comparators:
            comparators = _get_ordered_child_exprs(conn, node_id, "Expression", "right")
        return ast.Compare(
            left=left,
            ops=[op_map[o.strip()] for o in ops_str],
            comparators=comparators,
        )

    if kind == "Call":
        rows = _q(conn, "MATCH (n:Expression {id: $id}) RETURN n.func", {"id": node_id})
        func_name = rows[0].get("n.func")

        if func_name:
            parts = func_name.split(".")
            if len(parts) == 1:
                func_node = ast.Name(id=parts[0], ctx=ast.Load())
            else:
                func_node = ast.Name(id=parts[0], ctx=ast.Load())
                for attr in parts[1:]:
                    func_node = ast.Attribute(value=func_node, attr=attr, ctx=ast.Load())
        else:
            func_node = _get_child_expr(conn, node_id, "Expression", "func")
        args = _get_ordered_child_exprs(conn, node_id, "Expression", "arg")
        return ast.Call(func=func_node, args=args, keywords=[])

    if kind == "BoolOp":
        rows = _q(conn, "MATCH (n:Expression {id: $id}) RETURN n.op", {"id": node_id})
        op = ast.And() if rows[0]["n.op"] == "and" else ast.Or()
        values = _get_ordered_child_exprs(conn, node_id, "Expression", "value")
        return ast.BoolOp(op=op, values=values)

    if kind == "ListExpr":
        elts = _get_ordered_child_exprs(conn, node_id, "Expression", "element")
        return ast.List(elts=elts, ctx=ast.Load())

    if kind == "DictExpr":
        keys   = _get_ordered_child_exprs(conn, node_id, "Expression", "key")
        values = _get_ordered_child_exprs(conn, node_id, "Expression", "value")
        return ast.Dict(keys=keys, values=values)

    if kind == "IfExp":
        test  = _get_child_expr(conn, node_id, "Expression", "test")
        body  = _get_child_expr(conn, node_id, "Expression", "body")
        orelse = _get_child_expr(conn, node_id, "Expression", "orelse")
        return ast.IfExp(test=test, body=body, orelse=orelse)

    raise ValueError(f"Unknown expression kind: {kind}")


def _get_expr_children(conn: kuzu.Connection, parent_id: str, parent_table: str) -> list[dict]:
    """Return all HAS_EXPR children of a node, with role and order.

    parent_table is "Statement", "Expression", or "Function".
    Uses a single query against the collapsed edge table.
    """
    rel_table = f"HAS_EXPR_{parent_table}"
    cypher = (
        f"MATCH (p:{parent_table} {{id: $pid}})-[e:{rel_table}]->(c:Expression) "
        f"RETURN c.id AS cid, c.kind AS ctype, e.role AS role, e.ord AS ord"
    )
    children = _q(conn, cypher, {"pid": parent_id})
    children.sort(key=lambda r: (r.get("role") or "", r.get("ord") or 0))
    return children


def _get_child_expr(
    conn: kuzu.Connection, parent_id: str, parent_table: str, role: str
) -> ast.expr:
    """Get the single expression child with the given role."""
    children = _get_expr_children(conn, parent_id, parent_table)
    matches = [c for c in children if c["role"] == role]
    if not matches:
        raise ValueError(f"No HAS_EXPR child with role='{role}' for {parent_table}:{parent_id}")
    r = matches[0]
    return _build_expr(conn, r["cid"], r["ctype"])


def _get_ordered_child_exprs(
    conn: kuzu.Connection, parent_id: str, parent_table: str, role: str
) -> list[ast.expr]:
    """Get ordered list of expression children with the given role."""
    children = _get_expr_children(conn, parent_id, parent_table)
    matches = sorted(
        [c for c in children if c["role"] == role],
        key=lambda r: r.get("ord") or 0,
    )
    return [_build_expr(conn, r["cid"], r["ctype"]) for r in matches]


# ── statement reconstruction ──────────────────────────────────────────────────

def _build_stmt(conn: kuzu.Connection, node_id: str, kind: str) -> ast.stmt:
    """Reconstruct a single ast.stmt from a graph node."""

    if kind == "Return":
        children = _get_expr_children(conn, node_id, "Statement")
        values = [c for c in children if c["role"] == "value"]
        if values:
            val = _build_expr(conn, values[0]["cid"], values[0]["ctype"])
        else:
            val = None
        return ast.Return(value=val)

    if kind == "Assign":
        rows = _q(conn, "MATCH (n:Statement {id: $id}) RETURN n.targets", {"id": node_id})
        target_names = rows[0]["n.targets"].split(",")
        targets = [ast.Name(id=t.strip(), ctx=ast.Store()) for t in target_names]
        value = _get_child_expr(conn, node_id, "Statement", "value")
        return ast.Assign(targets=targets, value=value, lineno=0)

    if kind == "IfStmt":
        test = _get_child_expr(conn, node_id, "Statement", "test")
        body   = _get_block_stmts(conn, node_id, "IfStmt", role="body")
        orelse = _get_block_stmts(conn, node_id, "IfStmt", role="orelse")
        return ast.If(test=test, body=body or [ast.Pass()], orelse=orelse)

    if kind == "ForLoop":
        rows = _q(conn, "MATCH (n:Statement {id: $id}) RETURN n.target", {"id": node_id})
        target = ast.Name(id=rows[0]["n.target"], ctx=ast.Store())
        iter_  = _get_child_expr(conn, node_id, "Statement", "iter")
        body   = _get_block_stmts(conn, node_id, "ForLoop")
        return ast.For(target=target, iter=iter_, body=body or [ast.Pass()], orelse=[])

    if kind == "WhileLoop":
        test = _get_child_expr(conn, node_id, "Statement", "test")
        body = _get_block_stmts(conn, node_id, "WhileLoop")
        return ast.While(test=test, body=body or [ast.Pass()], orelse=[])

    if kind == "ExprStmt":
        children = _get_expr_children(conn, node_id, "Statement")
        expr = _build_expr(conn, children[0]["cid"], children[0]["ctype"])
        return ast.Expr(value=expr)

    if kind == "Pass":
        return ast.Pass()
    if kind == "Break":
        return ast.Break()
    if kind == "Continue":
        return ast.Continue()

    raise ValueError(f"Unknown statement kind: {kind}")


def _get_block_stmts(
    conn: kuzu.Connection,
    parent_id: str,
    parent_kind: str,
    role: str | None = None,
) -> list[ast.stmt]:
    """
    Fetch all HAS_STMT children of a block node, ordered by `ord`.
    If role is given, filter to that role (e.g. "body", "orelse").

    parent_kind: "Function", "IfStmt", "ForLoop", or "WhileLoop"
    """
    rel_table = f"HAS_STMT_{parent_kind}"

    # Determine the parent table (Function or Statement)
    if parent_kind == "Function":
        parent_table = "Function"
    else:
        parent_table = "Statement"

    if role:
        cypher = (
            f"MATCH (p:{parent_table} {{id: $pid}})-[e:{rel_table}]->(c:Statement) "
            f"WHERE e.role = $role "
            f"RETURN c.id AS cid, c.kind AS ctype, e.ord AS ord "
            f"ORDER BY e.ord"
        )
        children = _q(conn, cypher, {"pid": parent_id, "role": role})
    else:
        cypher = (
            f"MATCH (p:{parent_table} {{id: $pid}})-[e:{rel_table}]->(c:Statement) "
            f"RETURN c.id AS cid, c.kind AS ctype, e.ord AS ord "
            f"ORDER BY e.ord"
        )
        children = _q(conn, cypher, {"pid": parent_id})

    return [_build_stmt(conn, r["cid"], r["ctype"]) for r in children]


# ── function & class reconstruction ──────────────────────────────────────────

def _build_function(conn: kuzu.Connection, func_id: str) -> ast.FunctionDef:
    rows = _q(conn, "MATCH (f:Function {id: $id}) RETURN f.name, f.return_type", {"id": func_id})
    name        = rows[0]["f.name"]
    return_type = rows[0]["f.return_type"]

    # Arguments
    arg_rows = _q(
        conn,
        "MATCH (f:Function {id: $id})-[e:HAS_ARG]->(a:Argument) "
        "RETURN a.name, a.type_annotation, e.position ORDER BY e.position",
        {"id": func_id},
    )
    args = []
    for ar in arg_rows:
        annotation = None
        if ar["a.type_annotation"]:
            annotation = ast.Name(id=ar["a.type_annotation"], ctx=ast.Load())
        args.append(ast.arg(arg=ar["a.name"], annotation=annotation))

    body = _get_block_stmts(conn, func_id, "Function")
    if not body:
        body = [ast.Pass()]

    returns = ast.Name(id=return_type, ctx=ast.Load()) if return_type else None

    return ast.FunctionDef(
        name=name,
        args=ast.arguments(
            posonlyargs=[], args=args, vararg=None,
            kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[],
        ),
        body=body,
        decorator_list=[],
        returns=returns,
    )


def _build_class(conn: kuzu.Connection, class_id: str) -> ast.ClassDef:
    rows = _q(conn, "MATCH (c:Class {id: $id}) RETURN c.name", {"id": class_id})
    name = rows[0]["c.name"]

    method_rows = _q(
        conn,
        "MATCH (c:Class {id: $id})-[e:HAS_FUNCTION_Class]->(f:Function) "
        "RETURN f.id ORDER BY e.ord",
        {"id": class_id},
    )
    methods = [_build_function(conn, r["f.id"]) for r in method_rows]
    if not methods:
        methods = [ast.Pass()]

    return ast.ClassDef(
        name=name, bases=[], keywords=[],
        body=methods, decorator_list=[],
    )


# ── module reconstruction (entry point) ──────────────────────────────────────

def build_module(conn: kuzu.Connection, module_id: str) -> ast.Module:
    """Reconstruct the full Python ast.Module from the Kùzu graph."""
    body: list[ast.stmt] = []

    # 1. Imports (ordered)
    import_rows = _q(
        conn,
        "MATCH (m:Module {id: $id})-[e:HAS_IMPORT_Import]->(i:Import) "
        "RETURN i.names AS names, e.ord AS ord ORDER BY e.ord",
        {"id": module_id},
    )
    from_rows = _q(
        conn,
        "MATCH (m:Module {id: $id})-[e:HAS_IMPORT_ImportFrom]->(i:ImportFrom) "
        "RETURN i.module AS module, i.names AS names, e.ord AS ord ORDER BY e.ord",
        {"id": module_id},
    )
    all_imports = []
    for r in import_rows:
        names = [ast.alias(name=n.strip()) for n in r["names"].split(",")]
        all_imports.append((r["ord"], ast.Import(names=names)))
    for r in from_rows:
        names = [ast.alias(name=n.strip()) for n in r["names"].split(",")]
        all_imports.append((r["ord"], ast.ImportFrom(module=r["module"], names=names, level=0)))
    all_imports.sort(key=lambda x: x[0])
    body.extend(stmt for _, stmt in all_imports)

    # 2. Classes (ordered)
    class_rows = _q(
        conn,
        "MATCH (m:Module {id: $id})-[e:HAS_CLASS]->(c:Class) "
        "RETURN c.id ORDER BY e.ord",
        {"id": module_id},
    )
    for r in class_rows:
        body.append(_build_class(conn, r["c.id"]))

    # 3. Functions (ordered)
    func_rows = _q(
        conn,
        "MATCH (m:Module {id: $id})-[e:HAS_FUNCTION_Module]->(f:Function) "
        "RETURN f.id ORDER BY e.ord",
        {"id": module_id},
    )
    for r in func_rows:
        body.append(_build_function(conn, r["f.id"]))

    if not body:
        body = [ast.Pass()]

    module = ast.Module(body=body, type_ignores=[])
    ast.fix_missing_locations(module)
    return module


def unparse_to_python(conn: kuzu.Connection, module_id: str) -> str:
    """Full pipeline: graph → ast.Module → Python source string."""
    _check_schema_version(conn)
    validate_graph(conn)
    module = build_module(conn, module_id)
    return ast.unparse(module)


def unparse_to_file(conn: kuzu.Connection, module_id: str, output_path: str) -> str:
    """Unparse and write to a .py file. Returns the generated source."""
    source = unparse_to_python(conn, module_id)
    import os
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w") as f:
        f.write(source + "\n")
    return source


def unparse_requirements(conn: kuzu.Connection, output_dir: str) -> None:
    """Discover all Dependency nodes in the graph and generate requirements.txt."""
    import os
    result = _q(conn, "MATCH (d:Dependency) RETURN DISTINCT d.name, d.version")
    if not result:
        return

    req_path = os.path.join(output_dir, "requirements.txt")
    print(f"  📄 Generating 'requirements.txt' → {req_path}")

    with open(req_path, "w") as f:
        for row in result:
            name = row["d.name"]
            # Skip Java-specific coordinates in python requirements
            if ":" in name:
                continue
            ver = row["d.version"]
            if ver:
                if ver.startswith("^"):
                    f.write(f"{name}>={ver[1:]}\n")
                elif not any(ver.startswith(op) for op in [">", "<", "=", "~"]):
                    f.write(f"{name}=={ver}\n")
                else:
                    f.write(f"{name}{ver}\n")
            else:
                f.write(f"{name}\n")


def unparse_project(conn: kuzu.Connection, output_dir: str) -> dict[str, str]:
    """
    Discover all Module nodes in the Kùzu graph and write one .py file per module.

    Module.name controls the output path:
      - "main"                  → output_dir/main.py
      - "calculator/operations" → output_dir/calculator/operations.py
      - "calculator/__init__"   → output_dir/calculator/__init__.py

    Returns a dict of {file_path: source_code}.
    """
    import os

    _check_schema_version(conn)
    validate_graph(conn)

    result = _q(conn, "MATCH (m:Module) RETURN m.id, m.name")
    if not result:
        raise RuntimeError("No Module nodes found in the graph.")

    generated: dict[str, str] = {}
    for row in result:
        module_id   = row["m.id"]
        module_name = row["m.name"]

        # Convert module name to file path
        rel_path   = module_name.replace(".", "/").replace("-", "_") + ".py"
        file_path  = os.path.join(output_dir, rel_path)

        print(f"  📄 Unparsing module '{module_name}' → {file_path}")
        source = unparse_to_file(conn, module_id, file_path)
        generated[file_path] = source

    unparse_requirements(conn, output_dir)

    return generated
