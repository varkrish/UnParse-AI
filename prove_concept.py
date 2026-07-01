import kuzu
from src.ast_agent.tools import ast_tools
from unparser import unparse_project, unparse_to_python
import os

EXPECTED_SOURCE = """\
def priority_label(urgency: int) -> str:
    if urgency >= 8:
        return 'HIGH'
    elif urgency >= 5:
        return 'MEDIUM'
    else:
        return 'LOW'\
"""

def populate_priority_module():
    from run import init_db
    import shutil

    if os.path.exists("ast_db"):
        shutil.rmtree("ast_db")

    db, conn = init_db()
    ast_tools.set_connection(conn)

    print("Populating tasks/priority AST manually to prove the concept...")

    # 1. Module
    ast_tools.create_module("mod_priority", "tasks/priority")

    # 2. priority_label function
    ast_tools.create_function("mod_priority", "func_pl", "priority_label", "str", 0)
    ast_tools.add_function_argument("func_pl", "arg_pl_urgency", "urgency", "int", 0)

    # IfStmt: if urgency >= 8
    ast_tools.add_statement("func_pl", "Function", "if_pl_high", "IfStmt", 0)
    # test
    ast_tools.add_expression("if_pl_high", "IfStmt", "cmp_pl_high", "Compare", "test", 0, op=">=")
    ast_tools.add_expression("cmp_pl_high", "Compare", "name_pl_urg_high", "Name", "left", 0, value="urgency")
    ast_tools.add_expression("cmp_pl_high", "Compare", "const_pl_8", "Constant", "comparator", 0, value="8", kind="int")

    # then body: return "high"
    ast_tools.add_statement("if_pl_high", "IfStmt", "ret_pl_high", "Return", 0, branch="then")
    ast_tools.add_expression("ret_pl_high", "Return", "const_pl_high_ret", "Constant", "value", 0, value="HIGH", kind="str")

    # else body: IfStmt: if urgency >= 5
    ast_tools.add_statement("if_pl_high", "IfStmt", "if_pl_med", "IfStmt", 0, branch="else")
    # test
    ast_tools.add_expression("if_pl_med", "IfStmt", "cmp_pl_med", "Compare", "test", 0, op=">=")
    ast_tools.add_expression("cmp_pl_med", "Compare", "name_pl_urg_med", "Name", "left", 0, value="urgency")
    ast_tools.add_expression("cmp_pl_med", "Compare", "const_pl_5", "Constant", "comparator", 0, value="5", kind="int")

    # then body: return "medium"
    ast_tools.add_statement("if_pl_med", "IfStmt", "ret_pl_med", "Return", 0, branch="then")
    ast_tools.add_expression("ret_pl_med", "Return", "const_pl_med_ret", "Constant", "value", 0, value="MEDIUM", kind="str")

    # else body: return "low"
    ast_tools.add_statement("if_pl_med", "IfStmt", "ret_pl_low", "Return", 0, branch="else")
    ast_tools.add_expression("ret_pl_low", "Return", "const_pl_low_ret", "Constant", "value", 0, value="LOW", kind="str")

    # Unparse
    os.makedirs("output", exist_ok=True)
    unparse_project(conn, "output")
    print("\n✅ Successfully unparsed!")

    with open("output/tasks/priority.py", "r") as f:
        actual = f.read()
        print("\n=== output/tasks/priority.py ===\n")
        print(actual)

    # Regression assertion
    actual_stripped = actual.strip()
    expected_stripped = EXPECTED_SOURCE.strip()
    assert actual_stripped == expected_stripped, (
        f"\n❌ Regression test FAILED!\n"
        f"Expected:\n{expected_stripped}\n\n"
        f"Got:\n{actual_stripped}"
    )
    print("✅ Regression test PASSED — output matches expected source exactly.")

    # Verify table counts
    result = conn.execute("CALL show_tables() RETURN *")
    node_count, rel_count = 0, 0
    while result.has_next():
        row = result.get_next()
        if row[2] == "NODE":
            node_count += 1
        else:
            rel_count += 1
    print(f"\n📊 Table counts: {node_count} node tables, {rel_count} rel tables")
    assert rel_count <= 20, f"Expected <= 20 rel tables, got {rel_count}"
    print("✅ Table count check PASSED.")

if __name__ == "__main__":
    populate_priority_module()
