"""
java_unparser.py — Reads the SAME Kùzu AST graph and generates Java source code.

The graph holds language-agnostic logic. This unparser targets Java instead of Python.
Same nodes, same edges — different target language.

Mapping decisions:
  Module              → public class {ClassName}   (one .java file per module)
  Function            → public static {ReturnType} {name}({args})
  Python type hints   → Java types (float→double, int→int, str→String, None→void)
  ImportFrom          → import {package}.{ClassName};   (regular import, not static)
  Call                → ClassName.method(args)  (qualified with source class)
  BinOp / Compare     → same operators
  If/else             → standard Java if/else with braces
  Assign              → var {target} = ...;  (Java 10+ local type inference)
  Return None         → return;   (void method — cannot return a value)

v0.2.0 — Unified Statement/Expression tables. Dispatch on kind column.
"""

from __future__ import annotations

import os

import kuzu

from schema import SCHEMA_VERSION
from src.ast_agent.graph_validator import validate_graph, GraphValidationError


# ── Helpers ───────────────────────────────────────────────────────────────────

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


# ── Type mapping ─────────────────────────────────────────────────────────────

PYTHON_TO_JAVA_TYPE = {
    "float":  "double",
    "int":    "int",
    "str":    "String",
    "bool":   "boolean",
    "list":   "List<Object>",
    "None":   "void",
    "none":   "void",
    None:     "Object",
    "":       "Object",
}

def _java_type(python_type: str | None) -> str:
    if not python_type:
        return "Object"
    # Allow Java types (like String[], void, or custom class types) to pass through
    if python_type == "void" or python_type[0].isupper() or "[]" in python_type:
        return python_type
    return PYTHON_TO_JAVA_TYPE.get(python_type, "Object")


# ── Expression code generation ────────────────────────────────────────────────

def _expr(
    conn: kuzu.Connection,
    node_id: str,
    kind: str,
    import_map: dict[str, str],   # function_name → ClassName
) -> str:
    """Recursively generate a Java expression string from the graph."""

    if kind == "Name":
        rows = _q(conn, "MATCH (n:Expression {id: $id}) RETURN n.value", {"id": node_id})
        val = rows[0]["n.value"]
        import re
        return re.sub(r'(\w+)\[(.*?)]', r'\1.get(\2)', val)

    if kind == "Constant":
        rows = _q(conn, "MATCH (n:Expression {id: $id}) RETURN n.value, n.kind_lit", {"id": node_id})
        val, kind_lit = rows[0]["n.value"], rows[0]["n.kind_lit"]
        if kind_lit == "str":
            return f'"{val}"'
        if kind_lit in ("none", "None"):
            return "__NONE__"   # sentinel; handled in Return
        if kind_lit == "bool":
            return val.lower()
        # Cast float literals to double when they contain a decimal point
        if kind_lit == "float" and "." not in val:
            return val + ".0"
        return val

    if kind == "BinOp":
        rows = _q(conn, "MATCH (n:Expression {id: $id}) RETURN n.op", {"id": node_id})
        op = rows[0]["n.op"]
        left  = _get_child_expr(conn, node_id, "Expression", "left", import_map)
        right = _get_child_expr(conn, node_id, "Expression", "right", import_map)
        return f"({left} {op} {right})"

    if kind == "UnaryOp":
        rows = _q(conn, "MATCH (n:Expression {id: $id}) RETURN n.op", {"id": node_id})
        op_map = {"not": "!", "-": "-", "+": "+"}
        op = op_map.get(rows[0]["n.op"], rows[0]["n.op"])
        operand = _get_child_expr(conn, node_id, "Expression", "operand", import_map)
        return f"{op}{operand}"

    if kind == "Compare":
        rows = _q(conn, "MATCH (n:Expression {id: $id}) RETURN n.ops, n.op", {"id": node_id})
        ops_str_raw = rows[0].get("n.ops") or rows[0].get("n.op") or ""
        ops_str = ops_str_raw.split(",") if ops_str_raw else []
        sym_map = {
            "==": "==", "!=": "!=", "<": "<", "<=": "<=", ">": ">", ">=": ">=",
            "Eq": "==", "NotEq": "!=", "Lt": "<", "LtE": "<=", "Gt": ">", "GtE": ">=",
        }
        left = _get_child_expr(conn, node_id, "Expression", "left", import_map)
        rights = _get_ordered_child_exprs(conn, node_id, "Expression", "comparator", import_map)
        if not rights:
            rights = _get_ordered_child_exprs(conn, node_id, "Expression", "right", import_map)
        parts = [left]
        for op, right in zip(ops_str, rights):
            parts.append(sym_map.get(op.strip(), op.strip()))
            parts.append(right)
        return " ".join(parts)

    if kind == "Call":
        rows = _q(conn, "MATCH (n:Expression {id: $id}) RETURN n.func", {"id": node_id})
        func = rows[0].get("n.func")
        if not func:
            func = _get_child_expr(conn, node_id, "Expression", "func", import_map)
        args = _get_ordered_child_exprs(conn, node_id, "Expression", "arg", import_map)

        # Qualify the function name with its source class if it came from an import
        if func in import_map:
            qualified = f"{import_map[func]}.{func}"
        else:
            qualified = func
        return f"{qualified}({', '.join(args)})"

    if kind == "BoolOp":
        rows = _q(conn, "MATCH (n:Expression {id: $id}) RETURN n.op", {"id": node_id})
        op = "&&" if rows[0]["n.op"] == "and" else "||"
        values = _get_ordered_child_exprs(conn, node_id, "Expression", "value", import_map)
        return f" {op} ".join(values)

    if kind == "ListExpr":
        elts = _get_ordered_child_exprs(conn, node_id, "Expression", "element", import_map)
        return f"List.of({', '.join(elts)})"

    if kind == "IfExp":
        raise NotImplementedError("IfExp (ternary) not yet supported in Java unparser")

    if kind == "DictExpr":
        raise NotImplementedError("DictExpr not yet supported in Java unparser")

    raise ValueError(f"Unsupported expression kind for Java: {kind}")


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


def _get_child_expr(conn, parent_id, parent_table, role, import_map) -> str:
    children = _get_expr_children(conn, parent_id, parent_table)
    matches = [c for c in children if c["role"] == role]
    if not matches:
        raise ValueError(f"No HAS_EXPR child with role='{role}' for {parent_table}:{parent_id}")
    r = matches[0]
    return _expr(conn, r["cid"], r["ctype"], import_map)


def _get_ordered_child_exprs(conn, parent_id, parent_table, role, import_map) -> list[str]:
    children = _get_expr_children(conn, parent_id, parent_table)
    matches = sorted([c for c in children if c["role"] == role], key=lambda r: r.get("ord") or 0)
    return [_expr(conn, r["cid"], r["ctype"], import_map) for r in matches]


# ── Statement code generation ─────────────────────────────────────────────────

def _stmt(
    conn: kuzu.Connection,
    node_id: str,
    kind: str,
    import_map: dict[str, str],
    return_type: str = "Object",  # Java return type of the enclosing method
    indent: int = 8,
) -> list[str]:
    """Generate Java statement lines. Returns list of indented strings."""
    pad = " " * indent

    if kind == "Return":
        children = _get_expr_children(conn, node_id, "Statement")
        values = [c for c in children if c["role"] == "value"]
        if values:
            val = _expr(conn, values[0]["cid"], values[0]["ctype"], import_map)
            # void method cannot return a value — Python's `return None` → Java `return;`
            if val == "__NONE__" or return_type == "void":
                return [f"{pad}return;"]
            return [f"{pad}return {val};"]
        return [f"{pad}return;"]

    if kind == "Assign":
        rows = _q(conn, "MATCH (n:Statement {id: $id}) RETURN n.targets", {"id": node_id})
        targets = rows[0]["n.targets"].split(",")[0].strip()
        val_children = _get_expr_children(conn, node_id, "Statement")
        val_nodes = [c for c in val_children if c["role"] == "value"]
        value = _expr(conn, val_nodes[0]["cid"], val_nodes[0]["ctype"], import_map) if val_nodes else "null"
        return [f"{pad}var {targets} = {value};"]

    if kind == "IfStmt":
        test = _get_child_expr(conn, node_id, "Statement", "test", import_map)
        then_stmts = _get_block_stmts(conn, node_id, "IfStmt", import_map, return_type,
                                       role="body", indent=indent + 4)
        else_stmts = _get_block_stmts(conn, node_id, "IfStmt", import_map, return_type,
                                       role="orelse", indent=indent + 4)
        lines = [f"{pad}if ({test}) {{"]
        lines.extend(then_stmts)
        if else_stmts:
            lines.append(f"{pad}}} else {{")
            lines.extend(else_stmts)
        lines.append(f"{pad}}}")
        return lines

    if kind == "ForLoop":
        raise NotImplementedError("ForLoop not yet supported in Java unparser")

    if kind == "WhileLoop":
        raise NotImplementedError("WhileLoop not yet supported in Java unparser")

    if kind == "ExprStmt":
        children = _get_expr_children(conn, node_id, "Statement")
        val = _expr(conn, children[0]["cid"], children[0]["ctype"], import_map) if children else ""
        return [f"{pad}{val};"]

    if kind == "Pass":
        return [f"{pad}// pass"]
    if kind == "Break":
        return [f"{pad}break;"]
    if kind == "Continue":
        return [f"{pad}continue;"]

    return [f"{pad}// TODO: {kind}"]


def _get_block_stmts(
    conn, parent_id, parent_kind, import_map, return_type="Object",
    role=None, indent=8
) -> list[str]:
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

    lines = []
    for r in children:
        lines.extend(_stmt(conn, r["cid"], r["ctype"], import_map, return_type, indent))
    return lines


# ── Method / Class generation ─────────────────────────────────────────────────

def _module_to_class_name(module_name: str) -> str:
    """'calculator/operations' → 'Operations'"""
    base = module_name.split("/")[-1]
    return base[0].upper() + base[1:]


def _java_package(module_name: str) -> str | None:
    """'calculator/operations' → 'calculator'"""
    parts = module_name.split("/")
    return ".".join(parts[:-1]) if len(parts) > 1 else None


def _build_method(
    conn: kuzu.Connection,
    func_id: str,
    import_map: dict[str, str],
    indent: int = 4,
    is_static: bool = True,
) -> list[str]:
    rows = _q(conn, "MATCH (f:Function {id: $id}) RETURN f.name, f.return_type, f.decorators", {"id": func_id})
    name        = rows[0]["f.name"]
    java_ret    = _java_type(rows[0]["f.return_type"])
    decorators  = rows[0].get("f.decorators") or ""

    arg_rows = _q(
        conn,
        "MATCH (f:Function {id: $id})-[e:HAS_ARG]->(a:Argument) "
        "RETURN a.name, a.type_annotation, e.position ORDER BY e.position",
        {"id": func_id},
    )
    args = ", ".join(
        f"{_java_type(ar['a.type_annotation'])} {ar['a.name']}"
        for ar in arg_rows
    )

    body_lines = _get_block_stmts(
        conn, func_id, "Function", import_map,
        return_type=java_ret, indent=indent + 4
    )
    if not body_lines:
        body_lines = [" " * (indent + 4) + "// empty"]

    pad = " " * indent
    lines = []
    if decorators:
        for dec in decorators.split("\n"):
            lines.append(f"{pad}{dec.strip()}")

    static_keyword = " static" if (is_static or name == "main") else ""
    lines.append(f"{pad}public{static_keyword} {java_ret} {name}({args}) {{")
    lines.extend(body_lines)
    lines.append(f"{pad}}}")
    return lines


# ── Module (file) generation ──────────────────────────────────────────────────

def build_java_file(conn: kuzu.Connection, module_id: str) -> str:
    """Reads a Module node and returns Java source code string."""
    _check_schema_version(conn)
    validate_graph(conn)

    rows = _q(conn, "MATCH (m:Module {id: $id}) RETURN m.name, m.decorators", {"id": module_id})
    module_name = rows[0]["m.name"]
    class_decorators = rows[0].get("m.decorators") or ""

    class_name  = _module_to_class_name(module_name)
    pkg_name    = _java_package(module_name)
    is_static = "RestController" not in class_decorators

    lines: list[str] = []

    # Package declaration
    if pkg_name:
        lines.append(f"package {pkg_name};")
        lines.append("")

    # Collect ImportFrom nodes → build import map and import statements
    from_rows = _q(
        conn,
        "MATCH (m:Module {id: $id})-[e:HAS_IMPORT_ImportFrom]->(i:ImportFrom) "
        "RETURN i.module AS module, i.names AS names, e.ord AS ord ORDER BY e.ord",
        {"id": module_id},
    )

    # import_map: function_name → SourceClassName  (e.g. "add" → "Operations")
    # Also track which source classes need to be imported
    import_map: dict[str, str] = {}   # func_name → ClassName
    class_imports: dict[str, str] = {}  # ClassName → full.package.ClassName

    for r in from_rows:
        module_path = r["module"]
        names = r["names"].split(",")

        is_external = any(module_path.startswith(prefix) for prefix in ("org.", "java.", "javax.", "com.", "spring."))

        if is_external:
            for name in names:
                name = name.strip()
                if name:
                    class_imports[name] = f"{module_path}.{name}"
        else:
            src_parts   = module_path.split(".")           # ['calculator', 'operations']
            src_class   = _module_to_class_name(src_parts[-1])   # 'Operations'
            src_pkg     = ".".join(src_parts[:-1])                 # 'calculator'
            full_import = f"{src_pkg}.{src_class}" if src_pkg else src_class

            class_imports[src_class] = full_import
            for name in names:
                import_map[name.strip()] = src_class

    # Emit regular Java imports (not static)
    for src_class, full_import in sorted(class_imports.items()):
        lines.append(f"import {full_import};")
    if class_imports:
        lines.append("")

    # Regular imports (import X)
    import_rows = _q(
        conn,
        "MATCH (m:Module {id: $id})-[e:HAS_IMPORT_Import]->(i:Import) "
        "RETURN i.names AS names, e.ord AS ord ORDER BY e.ord",
        {"id": module_id},
    )
    for r in import_rows:
        for name in r["names"].split(","):
            lines.append(f"import {name.strip()};")
    if import_rows:
        lines.append("")

    # Class wrapper
    if class_decorators:
        for dec in class_decorators.split("\n"):
            lines.append(dec.strip())

    lines.append(f"public class {class_name} {{")
    lines.append("")

    # Top-level functions → static methods
    func_rows = _q(
        conn,
        "MATCH (m:Module {id: $id})-[e:HAS_FUNCTION_Module]->(f:Function) "
        "RETURN f.id ORDER BY e.ord",
        {"id": module_id},
    )
    for r in func_rows:
        lines.extend(_build_method(conn, r["f.id"], import_map, indent=4, is_static=is_static))
        lines.append("")

    lines.append("}")
    return "\n".join(lines) + "\n"


# ── Project unparser ──────────────────────────────────────────────────────────

def unparse_pom(conn: kuzu.Connection, output_dir: str = "") -> str:
    """Discover all Dependency nodes and generate a basic Maven pom.xml."""
    result = _q(conn, "MATCH (d:Dependency) RETURN DISTINCT d.name, d.version")
    if not result:
        return ""

    dep_xml_blocks = []
    for row in result:
        name = row["d.name"]
        ver = row["d.version"] or "1.0.0"

        # Strip semver caret/tilde if present (e.g. ^2.31.0 -> 2.31.0)
        ver_clean = ver.lstrip("^~=>\"")

        groupId = "org.example"
        artifactId = name
        if ":" in name:
            groupId, artifactId = name.split(":", 1)

        dep_xml_blocks.append(f"""        <dependency>
            <groupId>{groupId}</groupId>
            <artifactId>{artifactId}</artifactId>
            <version>{ver_clean}</version>
        </dependency>""")

    dependencies_section = "\n".join(dep_xml_blocks)

    pom_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <groupId>com.unparse</groupId>
    <artifactId>generated-project</artifactId>
    <version>1.0.0</version>

    <properties>
        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>
    </properties>

    <dependencies>
{dependencies_section}
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
                <version>3.2.0</version>
            </plugin>
        </plugins>
    </build>
</project>
"""
    return pom_content


def unparse_java_project(conn: kuzu.Connection, output_dir: str) -> dict[str, str]:
    """
    Discover all Module nodes and write one .java file per module.

    Module.name controls the output path:
      'calculator/operations' → output_dir/calculator/Operations.java
      'main'                  → output_dir/Main.java
    """
    _check_schema_version(conn)
    validate_graph(conn)

    result = _q(conn, "MATCH (m:Module) RETURN m.id, m.name")
    if not result:
        raise RuntimeError("No Module nodes found in the graph.")

    generated: dict[str, str] = {}
    for row in result:
        module_id   = row["m.id"]
        module_name = row["m.name"]
        class_name  = _module_to_class_name(module_name)

        parts    = module_name.split("/")
        package_path = _java_package(module_name).replace(".", "/")

        source = build_java_file(conn, module_id)
        java_path = os.path.join(output_dir, "src/main/java", package_path, f"{class_name}.java")

        os.makedirs(os.path.dirname(java_path), exist_ok=True)
        with open(java_path, "w") as f:
            f.write(source)
        generated[java_path] = source

    app_code = f"""package com.unparse.generated;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.ComponentScan;

@SpringBootApplication
@ComponentScan(basePackages = {{"controller"}})
public class Application {{
    public static void main(String[] args) {{
        SpringApplication.run(Application.class, args);
    }}
}}
"""
    app_path = os.path.join(output_dir, "src/main/java/com/unparse/generated/Application.java")
    os.makedirs(os.path.dirname(app_path), exist_ok=True)
    with open(app_path, "w") as f:
        f.write(app_code)
    generated[app_path] = app_code

    pom = unparse_pom(conn, output_dir)
    with open(os.path.join(output_dir, "pom.xml"), "w") as f:
        f.write(pom)

    return generated
