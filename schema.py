"""
schema.py — Creates the Kùzu database and defines all node/edge tables.

This is the SOLE SOURCE OF TRUTH for the AST schema.
The LLM agent never receives this file as text — it introspects the
live database using CALL show_tables() and CALL table_info().

Kùzu 0.11 DDL rule: each CREATE REL TABLE must have exactly ONE
FROM/TO pair. Properties follow the FROM/TO clause.

v0.2.0 — Unified Statement/Expression tables with kind discriminator.
         Cross-product edge tables collapsed to one-per-block-parent.
"""

import kuzu
import os
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "ast_db")

SCHEMA_VERSION = "0.2.0"

# Valid statement kinds (for validation, not for generating tables)
STMT_KINDS = [
    "Assign", "Return", "IfStmt", "ForLoop", "WhileLoop",
    "ExprStmt", "Pass", "Break", "Continue",
]

# Valid expression kinds
EXPR_KINDS = [
    "Name", "Constant", "BinOp", "UnaryOp", "Compare",
    "Call", "Attribute", "BoolOp", "IfExp", "ListExpr", "DictExpr",
    "CmpOp",  # normalized comparison operator node
]

# Block parents that can contain child statements
BLOCK_PARENTS = ["Function", "IfStmt", "ForLoop", "WhileLoop"]


def get_db() -> kuzu.Database:
    """Return (and if needed create) the Kùzu database."""
    return kuzu.Database(DB_PATH)


def create_schema(conn: kuzu.Connection) -> None:
    """
    Define all node and edge tables.
    Uses IF NOT EXISTS so it is safe to call multiple times.
    """

    # ── Node tables ───────────────────────────────────────────────────────────
    node_ddls = [
        # Schema metadata (versioning)
        "CREATE NODE TABLE IF NOT EXISTS SchemaMetadata("
        "version STRING PRIMARY KEY, created_at STRING)",

        # Structural
        "CREATE NODE TABLE IF NOT EXISTS Module("
        "id STRING PRIMARY KEY, name STRING, decorators STRING)",

        "CREATE NODE TABLE IF NOT EXISTS Function("
        "id STRING PRIMARY KEY, name STRING, return_type STRING, decorators STRING)",

        "CREATE NODE TABLE IF NOT EXISTS Class("
        "id STRING PRIMARY KEY, name STRING)",

        "CREATE NODE TABLE IF NOT EXISTS Argument("
        "id STRING PRIMARY KEY, name STRING, type_annotation STRING)",

        # Imports and Dependencies
        "CREATE NODE TABLE IF NOT EXISTS Import("
        "id STRING PRIMARY KEY, names STRING)",

        "CREATE NODE TABLE IF NOT EXISTS ImportFrom("
        "id STRING PRIMARY KEY, module STRING, names STRING)",

        "CREATE NODE TABLE IF NOT EXISTS Dependency("
        "id STRING PRIMARY KEY, name STRING, version STRING)",

        # Unified Statement table (kind discriminator + nullable union columns)
        "CREATE NODE TABLE IF NOT EXISTS Statement("
        "id STRING PRIMARY KEY, "
        "kind STRING, "        # "Assign", "Return", "IfStmt", etc.
        "targets STRING, "     # Assign (kept for backward compat until fully migrated)
        "target STRING"        # ForLoop
        ")",

        # Unified Expression table (kind discriminator + nullable union columns)
        "CREATE NODE TABLE IF NOT EXISTS Expression("
        "id STRING PRIMARY KEY, "
        "kind STRING, "        # "Name", "Constant", "BinOp", etc.
        "value STRING, "       # Name.value, Constant.value
        "op STRING, "          # BinOp.op, UnaryOp.op, BoolOp.op, CmpOp.op
        "ops STRING, "         # Compare.ops (kept for backward compat)
        "func STRING, "        # Call.func
        "attr STRING, "        # Attribute.attr
        "kind_lit STRING"      # Constant.kind ("int", "str", etc.)
        ")",
    ]

    for ddl in node_ddls:
        conn.execute(ddl)

    # ── Edge tables ───────────────────────────────────────────────────────────

    edge_ddls: list[str] = [
        # HAS_IMPORT: Module → Import, Module → ImportFrom
        "CREATE REL TABLE IF NOT EXISTS HAS_IMPORT_Import("
        "FROM Module TO Import, ord INT64)",

        "CREATE REL TABLE IF NOT EXISTS HAS_IMPORT_ImportFrom("
        "FROM Module TO ImportFrom, ord INT64)",

        # HAS_DEPENDENCY: Module → Dependency
        "CREATE REL TABLE IF NOT EXISTS HAS_DEPENDENCY("
        "FROM Module TO Dependency, ord INT64)",

        # HAS_FUNCTION: Module → Function, Class → Function
        "CREATE REL TABLE IF NOT EXISTS HAS_FUNCTION_Module("
        "FROM Module TO Function, ord INT64)",

        "CREATE REL TABLE IF NOT EXISTS HAS_FUNCTION_Class("
        "FROM Class TO Function, ord INT64)",

        # HAS_CLASS: Module → Class
        "CREATE REL TABLE IF NOT EXISTS HAS_CLASS("
        "FROM Module TO Class, ord INT64)",

        # HAS_ARG: Function → Argument
        "CREATE REL TABLE IF NOT EXISTS HAS_ARG("
        "FROM Function TO Argument, position INT64)",

        # ── Collapsed statement edges (one per block-parent type) ────────────
        # Function → Statement
        "CREATE REL TABLE IF NOT EXISTS HAS_STMT_Function("
        "FROM Function TO Statement, ord INT64, role STRING)",

        # Statement → Statement (IfStmt body/orelse)
        "CREATE REL TABLE IF NOT EXISTS HAS_STMT_IfStmt("
        "FROM Statement TO Statement, ord INT64, role STRING)",

        # Statement → Statement (ForLoop body)
        "CREATE REL TABLE IF NOT EXISTS HAS_STMT_ForLoop("
        "FROM Statement TO Statement, ord INT64, role STRING)",

        # Statement → Statement (WhileLoop body)
        "CREATE REL TABLE IF NOT EXISTS HAS_STMT_WhileLoop("
        "FROM Statement TO Statement, ord INT64, role STRING)",

        # ── Collapsed expression edges (one per parent category) ─────────────
        # Statement → Expression
        "CREATE REL TABLE IF NOT EXISTS HAS_EXPR_Statement("
        "FROM Statement TO Expression, role STRING, ord INT64)",

        # Expression → Expression
        "CREATE REL TABLE IF NOT EXISTS HAS_EXPR_Expression("
        "FROM Expression TO Expression, role STRING, ord INT64)",

        # Function → Expression (for future use: default values, decorators)
        "CREATE REL TABLE IF NOT EXISTS HAS_EXPR_Function("
        "FROM Function TO Expression, role STRING, ord INT64)",

        # CALLS_API: cross-stack link between UI function and Controller function
        "CREATE REL TABLE IF NOT EXISTS CALLS_API("
        "FROM Function TO Function, path STRING, method STRING)",
    ]

    for ddl in edge_ddls:
        conn.execute(ddl)

    # ── Indexes ───────────────────────────────────────────────────────────────
    index_ddls = [
        "CREATE INDEX IF NOT EXISTS idx_function_name ON Function(name)",
        "CREATE INDEX IF NOT EXISTS idx_class_name ON Class(name)",
        "CREATE INDEX IF NOT EXISTS idx_module_name ON Module(name)",
        "CREATE INDEX IF NOT EXISTS idx_statement_kind ON Statement(kind)",
        "CREATE INDEX IF NOT EXISTS idx_expression_kind ON Expression(kind)",
    ]
    for ddl in index_ddls:
        try:
            conn.execute(ddl)
        except Exception:
            # Some Kùzu versions may not support CREATE INDEX IF NOT EXISTS
            pass

    # ── Schema version ────────────────────────────────────────────────────────
    now = datetime.now(timezone.utc).isoformat()
    try:
        conn.execute(
            "MERGE (m:SchemaMetadata {version: $ver}) "
            "SET m.created_at = $ts",
            {"ver": SCHEMA_VERSION, "ts": now},
        )
    except Exception:
        pass

    print(f"✅ Schema v{SCHEMA_VERSION} created: "
          f"{len(node_ddls)} node tables, {len(edge_ddls)} edge tables.")


def init_db() -> tuple[kuzu.Database, kuzu.Connection]:
    """Initialise DB and schema. Returns (db, conn)."""
    db = get_db()
    conn = kuzu.Connection(db)
    create_schema(conn)
    return db, conn


if __name__ == "__main__":
    import shutil
    # Fresh DB for testing
    if os.path.exists(DB_PATH):
        if os.path.isdir(DB_PATH):
            shutil.rmtree(DB_PATH)
        else:
            os.remove(DB_PATH)

    db, conn = init_db()
    result = conn.execute("CALL show_tables() RETURN *")
    node_names, rel_names = [], []
    while result.has_next():
        row = result.get_next()
        # row: [id, name, type, database_name, comment]
        if row[2] == "NODE":
            node_names.append(row[1])
        else:
            rel_names.append(row[1])
    print(f"\n📊 Registered: {len(node_names)} node tables, {len(rel_names)} rel tables")
    print("\nNode tables:", sorted(node_names))
    print("Rel tables:", sorted(rel_names))
