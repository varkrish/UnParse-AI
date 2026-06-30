"""
schema.py — Creates the Kùzu database and defines all node/edge tables.

This is the SOLE SOURCE OF TRUTH for the AST schema.
The LLM agent never receives this file as text — it introspects the
live database using CALL show_tables() and CALL table_info().

Kùzu 0.11 DDL rule: each CREATE REL TABLE must have exactly ONE
FROM/TO pair. Properties follow the FROM/TO clause.
"""

import kuzu
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "ast_db")

# All statement-type node names (used to generate HAS_STMT and HAS_EXPR edges)
STMT_TYPES = [
    "Assign", "Return", "IfStmt", "ForLoop", "WhileLoop",
    "ExprStmt", "Pass", "Break", "Continue",
]

# All expression-type node names
EXPR_TYPES = [
    "Name", "Constant", "BinOp", "UnaryOp", "Compare",
    "Call", "Attribute", "BoolOp", "IfExp", "ListExpr", "DictExpr",
]

# Which nodes can contain statements (block parents)
BLOCK_PARENTS = ["Function", "IfStmt", "ForLoop", "WhileLoop"]

# Which nodes can have expression children via HAS_EXPR
EXPR_PARENTS = [
    "Return", "Assign", "IfStmt", "ForLoop", "WhileLoop", "ExprStmt",
    "BinOp", "UnaryOp", "Compare", "Call", "Attribute",
    "BoolOp", "IfExp", "ListExpr", "DictExpr",
]


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
        # Structural
        "CREATE NODE TABLE IF NOT EXISTS Module(id STRING PRIMARY KEY, name STRING, decorators STRING)",
        "CREATE NODE TABLE IF NOT EXISTS Function(id STRING PRIMARY KEY, name STRING, return_type STRING, decorators STRING)",
        "CREATE NODE TABLE IF NOT EXISTS Class(id STRING PRIMARY KEY, name STRING)",
        "CREATE NODE TABLE IF NOT EXISTS Argument(id STRING PRIMARY KEY, name STRING, type_annotation STRING)",
        # Imports and Dependencies
        "CREATE NODE TABLE IF NOT EXISTS Import(id STRING PRIMARY KEY, names STRING)",
        "CREATE NODE TABLE IF NOT EXISTS ImportFrom(id STRING PRIMARY KEY, module STRING, names STRING)",
        "CREATE NODE TABLE IF NOT EXISTS Dependency(id STRING PRIMARY KEY, name STRING, version STRING)",
        # Statements
        "CREATE NODE TABLE IF NOT EXISTS Assign(id STRING PRIMARY KEY, targets STRING)",
        "CREATE NODE TABLE IF NOT EXISTS Return(id STRING PRIMARY KEY)",
        "CREATE NODE TABLE IF NOT EXISTS IfStmt(id STRING PRIMARY KEY)",
        "CREATE NODE TABLE IF NOT EXISTS ForLoop(id STRING PRIMARY KEY, target STRING)",
        "CREATE NODE TABLE IF NOT EXISTS WhileLoop(id STRING PRIMARY KEY)",
        "CREATE NODE TABLE IF NOT EXISTS ExprStmt(id STRING PRIMARY KEY)",
        "CREATE NODE TABLE IF NOT EXISTS Pass(id STRING PRIMARY KEY)",
        "CREATE NODE TABLE IF NOT EXISTS Break(id STRING PRIMARY KEY)",
        "CREATE NODE TABLE IF NOT EXISTS Continue(id STRING PRIMARY KEY)",
        # Expressions
        "CREATE NODE TABLE IF NOT EXISTS Name(id STRING PRIMARY KEY, value STRING)",
        "CREATE NODE TABLE IF NOT EXISTS Constant(id STRING PRIMARY KEY, value STRING, kind STRING)",
        "CREATE NODE TABLE IF NOT EXISTS BinOp(id STRING PRIMARY KEY, op STRING)",
        "CREATE NODE TABLE IF NOT EXISTS UnaryOp(id STRING PRIMARY KEY, op STRING)",
        "CREATE NODE TABLE IF NOT EXISTS Compare(id STRING PRIMARY KEY, ops STRING)",
        "CREATE NODE TABLE IF NOT EXISTS Call(id STRING PRIMARY KEY, func STRING)",
        "CREATE NODE TABLE IF NOT EXISTS Attribute(id STRING PRIMARY KEY, attr STRING)",
        "CREATE NODE TABLE IF NOT EXISTS BoolOp(id STRING PRIMARY KEY, op STRING)",
        "CREATE NODE TABLE IF NOT EXISTS IfExp(id STRING PRIMARY KEY)",
        "CREATE NODE TABLE IF NOT EXISTS ListExpr(id STRING PRIMARY KEY)",
        "CREATE NODE TABLE IF NOT EXISTS DictExpr(id STRING PRIMARY KEY)",
    ]

    for ddl in node_ddls:
        conn.execute(ddl)

    # ── Edge tables ───────────────────────────────────────────────────────────
    # Kùzu 0.11: one FROM/TO pair per CREATE REL TABLE statement.
    # We programmatically generate all needed pairs.

    edge_ddls: list[str] = []

    # HAS_IMPORT: Module → Import, Module → ImportFrom
    for target in ["Import", "ImportFrom"]:
        edge_ddls.append(
            f"CREATE REL TABLE IF NOT EXISTS HAS_IMPORT_{target}("
            f"FROM Module TO {target}, ord INT)"
        )

    # HAS_DEPENDENCY: Module → Dependency
    edge_ddls.append(
        "CREATE REL TABLE IF NOT EXISTS HAS_DEPENDENCY("
        "FROM Module TO Dependency, ord INT)"
    )

    # HAS_FUNCTION: Module → Function, Class → Function
    for src in ["Module", "Class"]:
        edge_ddls.append(
            f"CREATE REL TABLE IF NOT EXISTS HAS_FUNCTION_{src}("
            f"FROM {src} TO Function, ord INT)"
        )

    # HAS_CLASS: Module → Class
    edge_ddls.append(
        "CREATE REL TABLE IF NOT EXISTS HAS_CLASS(FROM Module TO Class, ord INT)"
    )

    # HAS_ARG: Function → Argument
    edge_ddls.append(
        "CREATE REL TABLE IF NOT EXISTS HAS_ARG(FROM Function TO Argument, position INT)"
    )

    # HAS_STMT: BlockParent → StmtType  (all combinations)
    for parent in BLOCK_PARENTS:
        for child in STMT_TYPES:
            edge_ddls.append(
                f"CREATE REL TABLE IF NOT EXISTS HAS_STMT_{parent}_{child}("
                f"FROM {parent} TO {child}, ord INT, branch STRING)"
            )

    # HAS_EXPR: ExprParent → ExprType  (all combinations)
    for parent in EXPR_PARENTS:
        for child in EXPR_TYPES:
            edge_ddls.append(
                f"CREATE REL TABLE IF NOT EXISTS HAS_EXPR_{parent}_{child}("
                f"FROM {parent} TO {child}, role STRING, ord INT)"
            )

    for ddl in edge_ddls:
        conn.execute(ddl)

    print(f"✅ Schema created: {len(node_ddls)} node tables, {len(edge_ddls)} edge tables.")


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
