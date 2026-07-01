# Changelog

## [v0.2.0] - Schema Architecture Refactor

### Changed
- **Collapsed Node Tables**: Unified 9 Statement tables (`Assign`, `Return`, etc.) into a single `Statement` node table with a `kind` discriminator column.
- **Collapsed Node Tables**: Unified 11 Expression tables (`Name`, `Constant`, etc.) into a single `Expression` node table with a `kind` discriminator column.
- **Collapsed Edge Tables**: Replaced 201 cross-product edge tables (`HAS_STMT_*` and `HAS_EXPR_*`) with just 7 semantic edge tables (one per block parent for statements, and generic expression edges). Adding a new statement or expression kind now requires **zero** new tables.
- **Tools API**: Upgraded `ast_tools.py` to transparently route `add_statement` and `add_expression` calls into the new unified tables without changing the LLM-facing API signatures. Maps `branch` to `role` internally.
- **Unparsers**: Upgraded `unparser.py`, `java_unparser.py`, and `react_unparser.py` to dispatch entirely on the `kind` column and traverse edges via single Cypher queries (eliminating the need for type-by-type iterative loop traversals).

### Added
- **Graph Validation**: Added `src/ast_agent/graph_validator.py` which executes a suite of Cypher queries to detect structural anomalies (missing function bodies, missing expression operands, orphan nodes, sequence gaps). Wired this check into all unparsers before transpilation.
- **Schema Versioning**: Introduced `SchemaMetadata` table and `SCHEMA_VERSION` constant to detect compatibility between the DB and unparser scripts.
- **Performance**: Added database indexes on `Function(name)`, `Class(name)`, `Module(name)`, `Statement(kind)`, and `Expression(kind)` to optimize unparsing read speeds.
