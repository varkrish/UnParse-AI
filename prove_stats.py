import kuzu
from src.ast_agent.tools import ast_tools
from java_unparser import unparse_java_project
from run import init_db
import os
import shutil

db, conn = init_db()
ast_tools.set_connection(conn)

print("Populating calculator/Stats AST manually to prove the Java unparser fix...")

ast_tools.create_module("mod_stats", "calculator/Stats")
ast_tools.create_function("mod_stats", "func_avg", "average", "double", 0)
ast_tools.add_function_argument("func_avg", "arg_vals", "values", "list", 0)

# Assign total = Operations.add(values[0], values[1])
ast_tools.add_statement("func_avg", "Function", "assign_tot", "Assign", 0)
ast_tools.set_assign_targets("assign_tot", "total")
ast_tools.add_expression("assign_tot", "Assign", "call_add", "Call", "value")
ast_tools.add_expression("call_add", "Call", "name_op", "Name", "func", value="Operations.add")
ast_tools.add_expression("call_add", "Call", "val0", "Name", "arg", value="values[0]")
ast_tools.add_expression("call_add", "Call", "val1", "Name", "arg", value="values[1]")

# Return total / 2
ast_tools.add_statement("func_avg", "Function", "ret_avg", "Return", 1)
ast_tools.add_expression("ret_avg", "Return", "binop_div", "BinOp", "value", op="/")
ast_tools.add_expression("binop_div", "BinOp", "name_tot", "Name", "left", value="total")
ast_tools.add_expression("binop_div", "BinOp", "const_2", "Constant", "right", value="2", kind="int")

# Add Dependencies to the module
ast_tools.add_dependency("mod_stats", "dep_numpy", "numpy", "^1.26.0", 0)
ast_tools.add_dependency("mod_stats", "dep_math3", "org.apache.commons:commons-math3", "3.6.1", 1)

# Unparse to Java
os.makedirs("java_output", exist_ok=True)
unparse_java_project(conn, "java_output")
print("\n✅ Successfully unparsed to Java!")

# Unparse to Python to verify requirements.txt
from unparser import unparse_project
os.makedirs("python_output", exist_ok=True)
unparse_project(conn, "python_output")
print("\n✅ Successfully unparsed to Python!")

with open("java_output/calculator/Stats.java", "r") as f:
    print("\n=== java_output/calculator/Stats.java ===\n")
    print(f.read())

with open("java_output/pom.xml", "r") as f:
    print("\n=== java_output/pom.xml ===\n")
    print(f.read())

with open("python_output/requirements.txt", "r") as f:
    print("\n=== python_output/requirements.txt ===\n")
    print(f.read())
