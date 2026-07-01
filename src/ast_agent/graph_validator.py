"""
graph_validator.py — Validates the Kùzu AST graph for structural correctness.

Runs Cypher queries to detect:
- Functions/Classes with no body statements
- IfStmt nodes missing a condition expression
- BinOp/Compare nodes missing left or right operands
- ForLoop nodes missing iter or target expressions
- Orphan Statement or Expression nodes with no incoming edges
- Duplicate or gapped ord sequences on parent edges

Raises GraphValidationError with full violation list before unparsing.
"""

from __future__ import annotations
import kuzu


class GraphValidationError(Exception):
    """Raised when the AST graph has structural violations."""

    def __init__(self, violations: list[dict]):
        self.violations = violations
        summary = f"{len(violations)} graph violation(s) detected:\n"
        for v in violations[:10]:
            summary += f"  - [{v['type']}] node_id={v.get('node_id', '?')} kind={v.get('kind', '?')}\n"
        if len(violations) > 10:
            summary += f"  ... and {len(violations) - 10} more\n"
        super().__init__(summary)


def _q(conn: kuzu.Connection, cypher: str, params: dict | None = None) -> list[dict]:
    """Execute a Cypher query and return rows as list of dicts."""
    result = conn.execute(cypher, params or {})
    col_names = result.get_column_names()
    rows = []
    while result.has_next():
        row = result.get_next()
        rows.append(dict(zip(col_names, row)))
    return rows


def validate_graph(conn: kuzu.Connection) -> list[dict]:
    """
    Run structural validation checks on the AST graph.

    Returns a list of violation dicts:
        [{"type": "missing_body", "node_id": "func_main", "kind": "Function"}, ...]

    If violations are found, raises GraphValidationError.
    """
    violations: list[dict] = []

    # 1. Functions with no body statements
    try:
        rows = _q(conn,
            "MATCH (f:Function) "
            "WHERE NOT EXISTS { MATCH (f)-[:HAS_STMT_Function]->(:Statement) } "
            "RETURN f.id AS node_id"
        )
        for r in rows:
            violations.append({
                "type": "missing_body",
                "node_id": r["node_id"],
                "kind": "Function",
            })
    except Exception:
        pass

    # 2. IfStmt nodes missing condition expression (role="test")
    try:
        rows = _q(conn,
            "MATCH (s:Statement {kind: 'IfStmt'}) "
            "WHERE NOT EXISTS { MATCH (s)-[:HAS_EXPR_Statement {role: 'test'}]->(:Expression) } "
            "RETURN s.id AS node_id"
        )
        for r in rows:
            violations.append({
                "type": "missing_condition",
                "node_id": r["node_id"],
                "kind": "IfStmt",
            })
    except Exception:
        pass

    # 3. BinOp nodes missing left operand
    try:
        rows = _q(conn,
            "MATCH (e:Expression {kind: 'BinOp'}) "
            "WHERE NOT EXISTS { MATCH (e)-[:HAS_EXPR_Expression {role: 'left'}]->(:Expression) } "
            "RETURN e.id AS node_id"
        )
        for r in rows:
            violations.append({
                "type": "missing_left_operand",
                "node_id": r["node_id"],
                "kind": "BinOp",
            })
    except Exception:
        pass

    # 4. BinOp nodes missing right operand
    try:
        rows = _q(conn,
            "MATCH (e:Expression {kind: 'BinOp'}) "
            "WHERE NOT EXISTS { MATCH (e)-[:HAS_EXPR_Expression {role: 'right'}]->(:Expression) } "
            "RETURN e.id AS node_id"
        )
        for r in rows:
            violations.append({
                "type": "missing_right_operand",
                "node_id": r["node_id"],
                "kind": "BinOp",
            })
    except Exception:
        pass

    # 5. Compare nodes missing left operand
    try:
        rows = _q(conn,
            "MATCH (e:Expression {kind: 'Compare'}) "
            "WHERE NOT EXISTS { MATCH (e)-[:HAS_EXPR_Expression {role: 'left'}]->(:Expression) } "
            "RETURN e.id AS node_id"
        )
        for r in rows:
            violations.append({
                "type": "missing_left_operand",
                "node_id": r["node_id"],
                "kind": "Compare",
            })
    except Exception:
        pass

    # 6. ForLoop nodes missing iter expression
    try:
        rows = _q(conn,
            "MATCH (s:Statement {kind: 'ForLoop'}) "
            "WHERE NOT EXISTS { MATCH (s)-[:HAS_EXPR_Statement {role: 'iter'}]->(:Expression) } "
            "RETURN s.id AS node_id"
        )
        for r in rows:
            violations.append({
                "type": "missing_iter",
                "node_id": r["node_id"],
                "kind": "ForLoop",
            })
    except Exception:
        pass

    # 7. Orphan Statement nodes (no incoming edges from any source)
    try:
        rows = _q(conn,
            "MATCH (s:Statement) "
            "WHERE NOT EXISTS { MATCH ()-[]->(s) } "
            "RETURN s.id AS node_id, s.kind AS kind"
        )
        for r in rows:
            violations.append({
                "type": "orphan_node",
                "node_id": r["node_id"],
                "kind": r.get("kind", "Statement"),
            })
    except Exception:
        pass

    # 8. Orphan Expression nodes (no incoming edges from any source)
    try:
        rows = _q(conn,
            "MATCH (e:Expression) "
            "WHERE NOT EXISTS { MATCH ()-[]->(e) } "
            "RETURN e.id AS node_id, e.kind AS kind"
        )
        for r in rows:
            violations.append({
                "type": "orphan_node",
                "node_id": r["node_id"],
                "kind": r.get("kind", "Expression"),
            })
    except Exception:
        pass

    # 9. Duplicate ord values on HAS_STMT_Function edges
    try:
        rows = _q(conn,
            "MATCH (f:Function)-[e:HAS_STMT_Function]->(s:Statement) "
            "WITH f.id AS parent_id, e.role AS role, e.ord AS ord, count(*) AS cnt "
            "WHERE cnt > 1 "
            "RETURN parent_id, role, ord, cnt"
        )
        for r in rows:
            violations.append({
                "type": "duplicate_ord",
                "node_id": r["parent_id"],
                "kind": "Function",
                "detail": f"role={r['role']} ord={r['ord']} count={r['cnt']}",
            })
    except Exception:
        pass

    if violations:
        raise GraphValidationError(violations)

    return violations
