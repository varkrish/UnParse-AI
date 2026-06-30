"""
unparser.py — Reads the Kùzu AST graph and generates valid Python source code.

This is a DETERMINISTIC compiler: given a valid graph, it always produces
syntactically correct Python. It uses Python's own `ast` module internally
so that `ast.unparse()` handles all formatting concerns.

Flow:
  Kùzu graph → Python ast nodes → ast.fix_missing_locations → ast.unparse → str
"""

from __future__ import annotations

import ast
import textwrap
from typing import Any

import kuzu


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


# ── expression tree reconstruction ───────────────────────────────────────────

def _build_expr(conn: kuzu.Connection, node_id: str, node_type: str) -> ast.expr:
    """Recursively reconstruct an ast.expr subtree from the graph."""

    if node_type == "Name":
        rows = _q(conn, "MATCH (n:Name {id: $id}) RETURN n.value", {"id": node_id})
        return ast.Name(id=rows[0]["n.value"], ctx=ast.Load())

    if node_type == "Constant":
        rows = _q(conn, "MATCH (n:Constant {id: $id}) RETURN n.value, n.kind", {"id": node_id})
        raw, kind = rows[0]["n.value"], rows[0]["n.kind"]
        if kind == "int":
            val = int(raw)
        elif kind == "float":
            val = float(raw)
        elif kind == "bool":
            val = raw.lower() == "true"
        elif kind == "none":
            val = None
        else:
            val = raw  # str
        return ast.Constant(value=val)

    if node_type == "BinOp":
        rows = _q(conn, "MATCH (n:BinOp {id: $id}) RETURN n.op", {"id": node_id})
        op_str = rows[0]["n.op"]
        op_map = {
            "+": ast.Add(), "-": ast.Sub(), "*": ast.Mult(), "/": ast.Div(),
            "//": ast.FloorDiv(), "%": ast.Mod(), "**": ast.Pow(),
            "&": ast.BitAnd(), "|": ast.BitOr(), "^": ast.BitXor(),
        }
        left  = _get_child_expr(conn, node_id, "BinOp", "left")
        right = _get_child_expr(conn, node_id, "BinOp", "right")
        return ast.BinOp(left=left, op=op_map[op_str], right=right)

    if node_type == "UnaryOp":
        rows = _q(conn, "MATCH (n:UnaryOp {id: $id}) RETURN n.op", {"id": node_id})
        op_str = rows[0]["n.op"]
        op_map = {"not": ast.Not(), "-": ast.USub(), "+": ast.UAdd(), "~": ast.Invert()}
        operand = _get_child_expr(conn, node_id, "UnaryOp", "operand")
        return ast.UnaryOp(op=op_map[op_str], operand=operand)

    if node_type == "Compare":
        rows = _q(conn, "MATCH (n:Compare {id: $id}) RETURN n", {"id": node_id})
        n_props = rows[0]["n"]
        ops_str_raw = n_props.get("ops") or n_props.get("op") or ""
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
        left = _get_child_expr(conn, node_id, "Compare", "left")
        # LLM may use 'comparator' or 'right' for the right-hand side(s)
        comparators = _get_ordered_child_exprs(conn, node_id, "Compare", "comparator")
        if not comparators:
            comparators = _get_ordered_child_exprs(conn, node_id, "Compare", "right")
        return ast.Compare(
            left=left,
            ops=[op_map[o.strip()] for o in ops_str],
            comparators=comparators,
        )

    if node_type == "Call":
        rows = _q(conn, "MATCH (n:Call {id: $id}) RETURN n.func", {"id": node_id})
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
            func_node = _get_child_expr(conn, node_id, "Call", "func")
        args = _get_ordered_child_exprs(conn, node_id, "Call", "arg")
        return ast.Call(func=func_node, args=args, keywords=[])

    if node_type == "BoolOp":
        rows = _q(conn, "MATCH (n:BoolOp {id: $id}) RETURN n.op", {"id": node_id})
        op = ast.And() if rows[0]["n.op"] == "and" else ast.Or()
        values = _get_ordered_child_exprs(conn, node_id, "BoolOp", "value")
        return ast.BoolOp(op=op, values=values)

    if node_type == "ListExpr":
        elts = _get_ordered_child_exprs(conn, node_id, "ListExpr", "element")
        return ast.List(elts=elts, ctx=ast.Load())

    if node_type == "DictExpr":
        keys   = _get_ordered_child_exprs(conn, node_id, "DictExpr", "key")
        values = _get_ordered_child_exprs(conn, node_id, "DictExpr", "value")
        return ast.Dict(keys=keys, values=values)

    if node_type == "IfExp":
        test  = _get_child_expr(conn, node_id, "IfExp", "test")
        body  = _get_child_expr(conn, node_id, "IfExp", "body")
        orelse = _get_child_expr(conn, node_id, "IfExp", "orelse")
        return ast.IfExp(test=test, body=body, orelse=orelse)

    raise ValueError(f"Unknown expression node type: {node_type}")


def _get_expr_children(conn: kuzu.Connection, parent_id: str, parent_type: str):
    """Return all HAS_EXPR_* children of a node, with role and order.
    
    Since rel tables are named HAS_EXPR_{Parent}_{Child}, we iterate over
    all child expression types and query each specific rel table.
    """
    from schema import EXPR_TYPES
    children = []
    for child_type in EXPR_TYPES:
        rel_table = f"HAS_EXPR_{parent_type}_{child_type}"
        cypher = (
            f"MATCH (p:{parent_type} {{id: $pid}})-[e:{rel_table}]->(c:{child_type}) "
            f"RETURN c.id AS cid, '{child_type}' AS ctype, e.role AS role, e.ord AS ord"
        )
        try:
            rows = _q(conn, cypher, {"pid": parent_id})
            children.extend(rows)
        except Exception:
            # Rel table may not exist for this parent/child combination — skip
            pass
    children.sort(key=lambda r: (r.get("role") or "", r.get("ord") or 0))
    return children


def _get_child_expr(
    conn: kuzu.Connection, parent_id: str, parent_type: str, role: str
) -> ast.expr:
    """Get the single expression child with the given role."""
    children = _get_expr_children(conn, parent_id, parent_type)
    matches = [c for c in children if c["role"] == role]
    if not matches:
        raise ValueError(f"No HAS_EXPR child with role='{role}' for {parent_type}:{parent_id}")
    r = matches[0]
    return _build_expr(conn, r["cid"], r["ctype"])


def _get_ordered_child_exprs(
    conn: kuzu.Connection, parent_id: str, parent_type: str, role: str
) -> list[ast.expr]:
    """Get ordered list of expression children with the given role."""
    children = _get_expr_children(conn, parent_id, parent_type)
    matches = sorted(
        [c for c in children if c["role"] == role],
        key=lambda r: r.get("ord") or 0,
    )
    return [_build_expr(conn, r["cid"], r["ctype"]) for r in matches]


# ── statement reconstruction ──────────────────────────────────────────────────

def _build_stmt(conn: kuzu.Connection, node_id: str, node_type: str) -> ast.stmt:
    """Reconstruct a single ast.stmt from a graph node."""

    if node_type == "Return":
        children = _get_expr_children(conn, node_id, "Return")
        values = [c for c in children if c["role"] == "value"]
        if values:
            val = _build_expr(conn, values[0]["cid"], values[0]["ctype"])
        else:
            val = None
        return ast.Return(value=val)

    if node_type == "Assign":
        rows = _q(conn, "MATCH (n:Assign {id: $id}) RETURN n.targets", {"id": node_id})
        target_names = rows[0]["n.targets"].split(",")
        targets = [ast.Name(id=t.strip(), ctx=ast.Store()) for t in target_names]
        value = _get_child_expr(conn, node_id, "Assign", "value")
        return ast.Assign(targets=targets, value=value, lineno=0)

    if node_type == "IfStmt":
        test = _get_child_expr(conn, node_id, "IfStmt", "test")
        body   = _get_block_stmts(conn, node_id, "IfStmt", branch="then")
        orelse = _get_block_stmts(conn, node_id, "IfStmt", branch="else")
        return ast.If(test=test, body=body or [ast.Pass()], orelse=orelse)

    if node_type == "ForLoop":
        rows = _q(conn, "MATCH (n:ForLoop {id: $id}) RETURN n.target", {"id": node_id})
        target = ast.Name(id=rows[0]["n.target"], ctx=ast.Store())
        iter_  = _get_child_expr(conn, node_id, "ForLoop", "iter")
        body   = _get_block_stmts(conn, node_id, "ForLoop")
        return ast.For(target=target, iter=iter_, body=body or [ast.Pass()], orelse=[])

    if node_type == "WhileLoop":
        test = _get_child_expr(conn, node_id, "WhileLoop", "test")
        body = _get_block_stmts(conn, node_id, "WhileLoop")
        return ast.While(test=test, body=body or [ast.Pass()], orelse=[])

    if node_type == "ExprStmt":
        children = _get_expr_children(conn, node_id, "ExprStmt")
        expr = _build_expr(conn, children[0]["cid"], children[0]["ctype"])
        return ast.Expr(value=expr)

    if node_type == "Pass":
        return ast.Pass()
    if node_type == "Break":
        return ast.Break()
    if node_type == "Continue":
        return ast.Continue()

    raise ValueError(f"Unknown statement node type: {node_type}")


def _get_block_stmts(
    conn: kuzu.Connection,
    parent_id: str,
    parent_type: str,
    branch: str | None = None,
) -> list[ast.stmt]:
    """
    Fetch all HAS_STMT_* children of a block node, ordered by `ord`.
    If branch is given, filter to that branch (for IfStmt then/else).
    """
    from schema import STMT_TYPES
    children: list[dict] = []
    for child_type in STMT_TYPES:
        rel_table = f"HAS_STMT_{parent_type}_{child_type}"
        if branch:
            cypher = (
                f"MATCH (p:{parent_type} {{id: $pid}})-[e:{rel_table}]->(c:{child_type}) "
                f"WHERE e.branch = $branch "
                f"RETURN c.id AS cid, '{child_type}' AS ctype, e.ord AS ord"
            )
            rows = _q(conn, cypher, {"pid": parent_id, "branch": branch})
        else:
            cypher = (
                f"MATCH (p:{parent_type} {{id: $pid}})-[e:{rel_table}]->(c:{child_type}) "
                f"RETURN c.id AS cid, '{child_type}' AS ctype, e.ord AS ord"
            )
            rows = _q(conn, cypher, {"pid": parent_id})
        try:
            children.extend(rows)
        except Exception:
            pass
    children.sort(key=lambda r: r.get("ord") or 0)
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
