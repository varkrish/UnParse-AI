"""
react_unparser.py — Reads the Kùzu AST graph and generates React JSX source code.

v0.2.0 — Unified Statement/Expression tables. Dispatch on kind column.
"""

from __future__ import annotations
import kuzu
import textwrap

from schema import SCHEMA_VERSION


def _q(conn: kuzu.Connection, cypher: str, params: dict | None = None) -> list[dict]:
    result = conn.execute(cypher, params or {})
    col_names = result.get_column_names()
    rows = []
    while result.has_next():
        rows.append(dict(zip(col_names, result.get_next())))
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
                    f"unparser expects v{SCHEMA_VERSION}."
                )
    except Exception as e:
        if "SchemaMetadata" in str(e):
            raise RuntimeError(
                f"Database has no SchemaMetadata table. "
                f"Recreate with current schema.py."
            )
        raise


def _get_expr_children(conn, parent_id, parent_table):
    """Return all HAS_EXPR children. parent_table is 'Statement' or 'Expression'."""
    rel_table = f"HAS_EXPR_{parent_table}"
    cypher = (
        f"MATCH (p:{parent_table} {{id: $pid}})-[e:{rel_table}]->(c:Expression) "
        f"RETURN c.id AS cid, c.kind AS ctype, e.role AS role, e.ord AS ord"
    )
    children = _q(conn, cypher, {"pid": parent_id})
    children.sort(key=lambda r: (r.get("role") or "", r.get("ord") or 0))
    return children

def _get_child_expr(conn, parent_id, parent_table, role):
    matches = [c for c in _get_expr_children(conn, parent_id, parent_table) if c["role"] == role]
    if not matches:
        return None
    r = matches[0]
    return _build_expr(conn, r["cid"], r["ctype"])

def _get_ordered_child_exprs(conn, parent_id, parent_table, role):
    matches = sorted(
        [c for c in _get_expr_children(conn, parent_id, parent_table) if c["role"] == role],
        key=lambda r: r.get("ord") or 0,
    )
    return [_build_expr(conn, r["cid"], r["ctype"]) for r in matches]

def _build_expr(conn: kuzu.Connection, node_id: str, kind: str) -> str:
    """Recursively generate a React expression/JSX string from the graph."""
    if kind == "Name":
        rows = _q(conn, "MATCH (n:Expression {id: $id}) RETURN n.value", {"id": node_id})
        return rows[0]["n.value"]

    if kind == "Constant":
        rows = _q(conn, "MATCH (n:Expression {id: $id}) RETURN n.value, n.kind_lit", {"id": node_id})
        val, kind_lit = rows[0]["n.value"], rows[0]["n.kind_lit"]
        if kind_lit == "str":
            return f'"{val}"'
        if kind_lit in ("none", "None"):
            return "null"
        if kind_lit == "bool":
            return val.lower()
        return val

    if kind == "BinOp":
        rows = _q(conn, "MATCH (n:Expression {id: $id}) RETURN n.op", {"id": node_id})
        op = rows[0]["n.op"]
        left  = _get_child_expr(conn, node_id, "Expression", "left")
        right = _get_child_expr(conn, node_id, "Expression", "right")
        return f"({left} {op} {right})"

    if kind == "UnaryOp":
        rows = _q(conn, "MATCH (n:Expression {id: $id}) RETURN n.op", {"id": node_id})
        op_map = {"not": "!", "-": "-", "+": "+"}
        op = op_map.get(rows[0]["n.op"], rows[0]["n.op"])
        operand = _get_child_expr(conn, node_id, "Expression", "operand")
        return f"{op}{operand}"

    if kind == "Compare":
        rows = _q(conn, "MATCH (n:Expression {id: $id}) RETURN n.ops, n.op", {"id": node_id})
        ops_str_raw = rows[0].get("n.ops") or rows[0].get("n.op") or ""
        ops_str = ops_str_raw.split(",") if ops_str_raw else []
        sym_map = {
            "==": "===", "!=": "!==", "<": "<", "<=": "<=", ">": ">", ">=": ">=",
            "Eq": "===", "NotEq": "!==", "Lt": "<", "LtE": "<=", "Gt": ">", "GtE": ">=",
        }
        left = _get_child_expr(conn, node_id, "Expression", "left")
        rights = _get_ordered_child_exprs(conn, node_id, "Expression", "comparator")
        if not rights:
            rights = _get_ordered_child_exprs(conn, node_id, "Expression", "right")
        parts = [left]
        for op, right in zip(ops_str, rights):
            parts.append(sym_map.get(op.strip(), op.strip()))
            parts.append(right)
        return " ".join(parts)

    if kind == "Call":
        rows = _q(conn, "MATCH (n:Expression {id: $id}) RETURN n.func", {"id": node_id})
        func = rows[0].get("n.func")
        if not func:
            func = _get_child_expr(conn, node_id, "Expression", "func")

        args = _get_ordered_child_exprs(conn, node_id, "Expression", "arg")

        is_html = func in (
            "div", "span", "button", "input", "h1", "h2", "h3", "h4", "h5", "h6",
            "p", "a", "form", "label", "br", "ul", "li", "header", "footer", "main", "section"
        )
        is_react_comp = func[0].isupper() if func else False

        # Macros
        if func == "fetchAdd":
            a, b, set_result = args[0], args[1], args[2]
            return f"fetch(`http://localhost:8080/api/add?a=${{{a}}}&b=${{{b}}}`, {{method: 'POST'}}).then(res => res.json()).then(data => {set_result}(data))"
        if func == "fetchMultiply":
            a, b, set_result = args[0], args[1], args[2]
            return f"fetch(`http://localhost:8080/api/multiply?a=${{{a}}}&b=${{{b}}}`, {{method: 'POST'}}).then(res => res.json()).then(data => {set_result}(data))"
        if func == "NumberInput":
            label, val, set_val = args[0], args[1], args[2]
            clean_label = label[1:-1] if (label.startswith('"') or label.startswith("'")) else label
            return f'<div style={{{{marginBottom: "10px"}}}}><label style={{{{marginRight: "10px"}}}}>{clean_label}: </label><input type="number" value={{{val}}} onChange={{e => {set_val}(e.target.value)}} style={{{{padding: "5px", borderRadius: "4px", border: "1px solid #ccc"}}}} /></div>'
        if func == "Button":
            label, click_handler, a, b, set_result = args[0], args[1], args[2], args[3], args[4]
            clean_label = label[1:-1] if (label.startswith('"') or label.startswith("'")) else label
            return f'<button onClick={{() => {click_handler}({a}, {b}, {set_result})}} style={{{{padding: "8px 15px", marginRight: "10px", backgroundColor: "#007bff", color: "white", border: "none", borderRadius: "4px", cursor: "pointer"}}}}>{clean_label}</button>'
        if func == "ResultDisplay":
            val = args[0]
            return f'<h2 style={{{{marginTop: "20px", color: "#333"}}}} align="left">Result: {{{val}}}</h2>'

        if (is_html or is_react_comp) and "." not in func:
            props_str = ""
            children = args

            if args and args[0].startswith("{") and ":" in args[0]:
                props_str = f" {{...{args[0]}}}"
                children = args[1:]

            if not children:
                return f"<{func}{props_str} />"

            child_str = ""
            import re
            for c in children:
                if c.startswith('"') and c.endswith('"'):
                    child_str += c[1:-1]
                elif c.startswith("'") and c.endswith("'"):
                    child_str += c[1:-1]
                elif c.startswith('<'):
                    child_str += c
                elif re.match(r"^[a-zA-Z_$][a-zA-Z0-9_$.]*$", c) or c.isdigit() or c in ("true", "false", "null"):
                    child_str += f"{{{c}}}"
                else:
                    # Plain text
                    child_str += c

            return f"<{func}{props_str}>{child_str}</{func}>"

        return f"{func}({', '.join(args)})"

    if kind == "DictExpr":
        keys   = _get_ordered_child_exprs(conn, node_id, "Expression", "key")
        values = _get_ordered_child_exprs(conn, node_id, "Expression", "value")
        pairs = []
        for k, v in zip(keys, values):
            if k.startswith('"') and k.endswith('"') and k[1:-1].isidentifier():
                k = k[1:-1]
            pairs.append(f"{k}: {v}")
        return f"{{{', '.join(pairs)}}}"

    if kind == "ListExpr":
        elts = _get_ordered_child_exprs(conn, node_id, "Expression", "element")
        return f"[{', '.join(elts)}]"

    if kind == "IfExp":
        raise NotImplementedError("IfExp not yet supported in React unparser")

    raise ValueError(f"Unsupported expression kind for React: {kind}")

def _build_stmt(conn: kuzu.Connection, node_id: str, kind: str) -> str | None:
    if kind == "Return":
        val = _get_child_expr(conn, node_id, "Statement", "value")
        if val:
            if val.startswith("<"):
                return f"return (\n  {val}\n);"
            return f"return {val};"
        return "return;"

    if kind == "Assign":
        rows = _q(conn, "MATCH (n:Statement {id: $id}) RETURN n.targets", {"id": node_id})
        targets = rows[0]["n.targets"].split(",")
        val = _get_child_expr(conn, node_id, "Statement", "value")
        return f"const {', '.join(t.strip() for t in targets)} = {val};"

    if kind == "ExprStmt":
        val = _get_child_expr(conn, node_id, "Statement", "value")
        # In JSX, expr stmts might just be children. But let's assume standard JS
        return f"{val};"

    if kind == "Pass":
        return "// pass"

    if kind == "IfStmt":
        raise NotImplementedError("IfStmt not yet supported in React unparser")

    if kind == "ForLoop":
        raise NotImplementedError("ForLoop not yet supported in React unparser")

    if kind == "WhileLoop":
        raise NotImplementedError("WhileLoop not yet supported in React unparser")

    raise ValueError(f"Unsupported statement kind for React: {kind}")

def _get_block_stmts(conn, parent_id, parent_kind, role=None, indent=2):
    """Fetch child statements from a block parent."""
    rel_table = f"HAS_STMT_{parent_kind}"

    if parent_kind == "Function":
        parent_table = "Function"
    else:
        parent_table = "Statement"

    if role:
        cypher = (
            f"MATCH (p:{parent_table} {{id: $pid}})-[e:{rel_table}]->(c:Statement) "
            f"WHERE e.role = $role "
            f"RETURN c.id AS sid, c.kind AS stype, e.ord AS ord "
            f"ORDER BY e.ord"
        )
        stmts = _q(conn, cypher, {"pid": parent_id, "role": role})
    else:
        cypher = (
            f"MATCH (p:{parent_table} {{id: $pid}})-[e:{rel_table}]->(c:Statement) "
            f"RETURN c.id AS sid, c.kind AS stype, e.ord AS ord "
            f"ORDER BY e.ord"
        )
        stmts = _q(conn, cypher, {"pid": parent_id})

    lines = []
    for r in stmts:
        stmt_str = _build_stmt(conn, r["sid"], r["stype"])
        if stmt_str:
            lines.extend(stmt_str.split("\n"))

    pad = " " * indent
    return [f"{pad}{line}" for line in lines]

def _module_to_component_name(module_name: str) -> str:
    base = module_name.split("/")[-1]
    return base[0].upper() + base[1:]

def _build_method(conn, func_id, indent=2):
    rows = _q(conn, "MATCH (f:Function {id: $id}) RETURN f.name", {"id": func_id})
    name = rows[0]["f.name"]

    arg_rows = _q(
        conn,
        "MATCH (f:Function {id: $id})-[e:HAS_ARG]->(a:Argument) "
        "RETURN a.name, e.position ORDER BY e.position",
        {"id": func_id},
    )
    args = ", ".join(ar["a.name"] for ar in arg_rows)

    body_lines = _get_block_stmts(conn, func_id, "Function", indent=indent + 2)

    pad = " " * indent
    lines = [f"{pad}function {name}({args}) {{"]
    if body_lines:
        lines.extend(body_lines)
    else:
        lines.append(f"{pad}  // empty")
    lines.append(f"{pad}}}")
    return lines

def build_react_file(conn: kuzu.Connection, module_id: str) -> str:
    _check_schema_version(conn)

    rows = _q(conn, "MATCH (m:Module {id: $id}) RETURN m.name", {"id": module_id})
    module_name = rows[0]["m.name"]
    comp_name = _module_to_component_name(module_name)

    lines = ["import React, { useState, useEffect } from 'react';"]

    import_rows = _q(
        conn,
        "MATCH (m:Module {id: $id})-[e:HAS_IMPORT_Import]->(i:Import) "
        "RETURN i.names AS names, e.ord AS ord ORDER BY e.ord",
        {"id": module_id},
    )
    for r in import_rows:
        for name in r["names"].split(","):
            lines.append(f"import {name.strip()};")

    lines.append("")

    func_rows = _q(
        conn,
        "MATCH (m:Module {id: $id})-[e:HAS_FUNCTION_Module]->(f:Function) "
        "RETURN f.id ORDER BY e.ord",
        {"id": module_id},
    )

    for r in func_rows:
        func_lines = _build_method(conn, r["f.id"], indent=0)
        first_line = func_lines[0]
        if comp_name in first_line:
            func_lines[0] = "export default " + first_line

        lines.extend(func_lines)
        lines.append("")

    return "\n".join(lines) + "\n"
