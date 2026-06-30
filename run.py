"""
run.py — End-to-end runner for the AST-Agent multi-file project experiment.

Usage:
    python3 run.py              # runs the default multi-file calculator project
    python3 run.py "your prompt"
"""

from __future__ import annotations

import sys
import os
import shutil
import subprocess

from schema import init_db, DB_PATH
from agent import run_agent
from unparser import unparse_project

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

# ── Multi-file project prompt ─────────────────────────────────────────────────
DEFAULT_PROMPT = """
Build a 5-file Python Task Manager project across 3 packages.

=== FILE 1: tasks/priority.py  (id: mod_priority) ===
Functions:
  - is_high_priority(urgency: int) -> bool
      return urgency >= 8
  - priority_label(urgency: int) -> str
      if urgency >= 8: return "HIGH"
      elif urgency >= 5: return "MEDIUM"   (nested IfStmt in else branch)
      else: return "LOW"

=== FILE 2: tasks/calculator.py  (id: mod_calc) ===
Functions:
  - days_remaining(current_day: int, due_day: int) -> int
      return due_day - current_day
  - is_overdue(current_day: int, due_day: int) -> bool
      return current_day > due_day
  - completion_pct(done: int, total: int) -> float
      if total == 0: return 0.0
      else: return (done / total) * 100

=== FILE 3: tasks/validator.py  (id: mod_validator) ===
Functions:
  - is_valid_urgency(urgency: int) -> bool
      if urgency < 1: return False
      if urgency > 10: return False
      return True
  - is_valid_days(days: int) -> bool
      if days < 0: return False
      return True

=== FILE 4: reports/summary.py  (id: mod_summary) ===
Imports: from tasks.priority import priority_label
         from tasks.calculator import days_remaining, completion_pct
Functions:
  - task_summary_label(urgency: int, current_day: int, due_day: int) -> str
      label = priority_label(urgency)
      days = days_remaining(current_day, due_day)
      return label
  - progress_report(done: int, total: int) -> float
      pct = completion_pct(done, total)
      return pct

=== FILE 5: main.py  (id: mod_main) ===
Imports: from tasks.priority import priority_label, is_high_priority
         from tasks.calculator import days_remaining, is_overdue, completion_pct
         from reports.summary import task_summary_label, progress_report
Functions:
  - main() -> None
      label = priority_label(9)
      high = is_high_priority(9)
      days = days_remaining(5, 20)
      overdue = is_overdue(25, 20)
      pct = completion_pct(7, 10)
      summary = task_summary_label(9, 5, 20)
      progress = progress_report(7, 10)
      return None

=== NODE ID CONVENTIONS ===
Use these Module ids/names:
  id='mod_priority',  name='tasks/priority'
  id='mod_calc',      name='tasks/calculator'
  id='mod_validator', name='tasks/validator'
  id='mod_summary',   name='reports/summary'
  id='mod_main',      name='main'

Use unique ids for everything, e.g.:
  func_is_high_priority, func_priority_label, func_days_remaining, func_is_overdue,
  func_completion_pct, func_is_valid_urgency, func_is_valid_days,
  func_task_summary_label, func_progress_report, func_main

CRITICAL:
  - Create all nodes and connect them using the tools provided.
  - elif chains = nested IfStmt inside the else branch:
      outer IfStmt (then=return HIGH) → add_statement(branch=else) → inner IfStmt
  - Return True/False: use Constant expressions with kind='bool', value='True'/'False'
  - Use exact node IDs everywhere.
"""


# ── Per-file specs (one LLM call each) ───────────────────────────────────────
FILE_SPECS = [
    {
        "module_id": "mod_priority",
        "module_name": "tasks/priority",
        "prompt": """
Create nodes and edges for module id='mod_priority', name='tasks/priority'.

Functions:
  1. is_high_priority(urgency: int) -> bool
       return urgency >= 8
       (Compare: urgency >= 8, op='>=', Constant value='8' kind='int')

  2. priority_label(urgency: int) -> str
       if urgency >= 8: return "HIGH"
       else:
           if urgency >= 5: return "MEDIUM"   [nested IfStmt in else branch]
           else: return "LOW"

Node ids to use:
  mod_priority, func_is_high_priority, func_priority_label
  arg_ihp_urgency, arg_pl_urgency
  ret_ihp, ret_pl_high, ret_pl_med, ret_pl_low
  ifstmt_pl_outer, ifstmt_pl_inner
  cmp_ihp (urgency>=8), cmp_pl_outer (urgency>=8), cmp_pl_inner (urgency>=5)
  name_ihp_urgency, name_pl_urgency_outer, name_pl_urgency_inner
  const_8a, const_8b, const_5
  const_high (value='HIGH' kind='str'), const_med (value='MEDIUM' kind='str'), const_low (value='LOW' kind='str')
  const_true_ihp (value='True' kind='bool')
""",
    },
    {
        "module_id": "mod_calc",
        "module_name": "tasks/calculator",
        "prompt": """
Create nodes and edges for module id='mod_calc', name='tasks/calculator'.

Functions:
  1. days_remaining(current_day: int, due_day: int) -> int
       return due_day - current_day   [BinOp: due_day - current_day]

  2. is_overdue(current_day: int, due_day: int) -> bool
       return current_day > due_day   [Compare: current_day > due_day]

  3. completion_pct(done: int, total: int) -> float
       if total == 0: return 0.0
       else: return (done / total) * 100
       [(done / total) = BinOp(/, done, total), then BinOp(*, that, 100)]

Node ids to use:
  mod_calc, func_days_remaining, func_is_overdue, func_completion_pct
  arg_dr_current, arg_dr_due, arg_io_current, arg_io_due, arg_cp_done, arg_cp_total
  ret_dr, ret_io, ret_cp_then, ret_cp_else
  ifstmt_cp
  cmp_dr (current>due), cmp_io (total==0)
  binop_dr_sub, binop_io (done/total), binop_cp_mul
  name_dr_due, name_dr_current, name_io_current, name_io_due
  name_cp_done, name_cp_total, name_cp_done2, name_cp_total2
  const_0_int (value='0' kind='int'), const_0f (value='0.0' kind='float'), const_100 (value='100' kind='int')
""",
    },
    {
        "module_id": "mod_validator",
        "module_name": "tasks/validator",
        "prompt": """
Create nodes and edges for module id='mod_validator', name='tasks/validator'.

Functions:
  1. is_valid_urgency(urgency: int) -> bool
       if urgency < 1: return False
       if urgency > 10: return False
       return True
       [Three separate statements: IfStmt, IfStmt, Return]

  2. is_valid_days(days: int) -> bool
       if days < 0: return False
       return True

Node ids to use:
  mod_validator, func_is_valid_urgency, func_is_valid_days
  arg_ivu_urgency, arg_ivd_days
  ifstmt_ivu_lt1, ifstmt_ivu_gt10, ret_ivu_false1, ret_ivu_false2, ret_ivu_true
  ifstmt_ivd_lt0, ret_ivd_false, ret_ivd_true
  cmp_ivu_lt1 (urgency<1), cmp_ivu_gt10 (urgency>10), cmp_ivd_lt0 (days<0)
  name_ivu_urgency_1, name_ivu_urgency_2, name_ivd_days
  const_1_v (value='1' kind='int'), const_10 (value='10' kind='int'), const_0_d (value='0' kind='int')
  const_false1 (value='False' kind='bool'), const_false2 (value='False' kind='bool')
  const_false3 (value='False' kind='bool'), const_true1 (value='True' kind='bool')
  const_true2 (value='True' kind='bool')
""",
    },
    {
        "module_id": "mod_summary",
        "module_name": "reports/summary",
        "prompt": """
Create nodes and edges for module id='mod_summary', name='reports/summary'.

Dependencies:
  numpy (^1.26.0)

Imports:
  from tasks.priority import priority_label
  from tasks.calculator import days_remaining, completion_pct

Functions:
  1. task_summary_label(urgency: int, current_day: int, due_day: int) -> str
       label = priority_label(urgency)
       days = days_remaining(current_day, due_day)
       return label

  2. progress_report(done: int, total: int) -> float
       pct = completion_pct(done, total)
       return pct

Node ids to use:
  mod_summary
  dep_numpy (name='numpy', version='^1.26.0')
  importfrom_summary_priority (module='tasks.priority', names='priority_label')
  importfrom_summary_calc (module='tasks.calculator', names='days_remaining,completion_pct')
  func_task_summary_label, func_progress_report
  arg_tsl_urgency, arg_tsl_current, arg_tsl_due, arg_pr_done, arg_pr_total
  assign_tsl_label, assign_tsl_days, ret_tsl
  assign_pr_pct, ret_pr
  call_priority_label_in_tsl (func='priority_label')
  call_days_remaining_in_tsl (func='days_remaining')
  call_completion_pct_in_pr (func='completion_pct')
  name_tsl_urgency, name_tsl_current, name_tsl_due
  name_tsl_label_ret (value='label')
  name_pr_done, name_pr_total, name_pr_pct_ret (value='pct')
""",
    },
    {
        "module_id": "mod_main",
        "module_name": "main",
        "prompt": """
Create nodes and edges for module id='mod_main', name='main'.

Imports:
  from tasks.priority import priority_label, is_high_priority
  from tasks.calculator import days_remaining, is_overdue, completion_pct
  from reports.summary import task_summary_label, progress_report

Functions:
  - main() -> None
      label = priority_label(9)
      high = is_high_priority(9)
      days = days_remaining(5, 20)
      overdue = is_overdue(25, 20)
      pct = completion_pct(7, 10)
      summary = task_summary_label(9, 5, 20)
      progress = progress_report(7, 10)
      return None

Node ids to use:
  mod_main
  importfrom_main_priority (module='tasks.priority', names='priority_label,is_high_priority')
  importfrom_main_calc (module='tasks.calculator', names='days_remaining,is_overdue,completion_pct')
  importfrom_main_summary (module='reports.summary', names='task_summary_label,progress_report')
  func_main, ret_main
  assign_m_label, assign_m_high, assign_m_days, assign_m_overdue, assign_m_pct, assign_m_summary, assign_m_progress
  call_pl_main (func='priority_label'), call_ihp_main (func='is_high_priority')
  call_dr_main (func='days_remaining'), call_io_main (func='is_overdue')
  call_cp_main (func='completion_pct'), call_tsl_main (func='task_summary_label')
  call_pr_main (func='progress_report')
  const_9a, const_9b, const_5a, const_20a, const_25, const_20b, const_7a, const_10a
  const_9c, const_5b, const_20c, const_7b, const_10b
  const_none_main (value='None' kind='none')
""",
    },
]


def main():
    user_prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else DEFAULT_PROMPT

    print("=" * 60)
    print("  AST-Agent: Multi-File Graph-First Code Generation")
    print("=" * 60)

    # Stage 1: Fresh DB
    print("\n─" * 20)
    print("Stage 1: Fresh Kùzu DB & schema")
    if os.path.exists(DB_PATH):
        if os.path.isdir(DB_PATH):
            shutil.rmtree(DB_PATH)
        else:
            os.remove(DB_PATH)
    db, conn = init_db()

    # Stage 2: LLM populates the graph — ONE CALL PER FILE
    print("\n─" * 20)
    print("Stage 2: LLM Agent → Kùzu graph (one call per file)")
    for i, spec in enumerate(FILE_SPECS):
        print(f"\n  [{i+1}/{len(FILE_SPECS)}] 📄 {spec['module_name']}  (id: {spec['module_id']})")
        run_agent(conn, spec["prompt"], module_id=spec["module_id"])

    # Stage 3: Unparse ALL Module nodes → separate .py files
    print("\n─" * 20)
    print("Stage 3: Kùzu graph → Python files")
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR)

    generated = unparse_project(conn, OUTPUT_DIR)

    print(f"\n✅ Generated {len(generated)} file(s):")
    for path, source in generated.items():
        rel = os.path.relpath(path, os.path.dirname(__file__))
        print(f"\n{'─'*40}")
        print(f"📄 {rel}")
        print(f"{'─'*40}")
        print(source)

    # Stage 4: Syntax check all files
    print("\n─" * 20)
    print("Stage 4: Syntax verification")
    all_ok = True
    for path in generated:
        r = subprocess.run(
            [sys.executable, "-m", "py_compile", path],
            capture_output=True, text=True
        )
        rel = os.path.relpath(path, os.path.dirname(__file__))
        if r.returncode == 0:
            print(f"  ✅ {rel}")
        else:
            print(f"  ❌ {rel}: {r.stderr.strip()}")
            all_ok = False

    # Stage 5: Functional test
    print("\n─" * 20)
    print("Stage 5: Functional test")
    main_py = os.path.join(OUTPUT_DIR, "main.py")
    if os.path.exists(main_py) and all_ok:
        # Create __init__.py for each package directory
        for pkg_dir in ["tasks", "reports"]:
            pkg_path = os.path.join(OUTPUT_DIR, pkg_dir)
            if os.path.isdir(pkg_path):
                open(os.path.join(pkg_path, "__init__.py"), "w").close()

        test_code = (
            f"import sys; sys.path.insert(0, '{OUTPUT_DIR}'); "
            "from tasks.priority import priority_label, is_high_priority; "
            "from tasks.calculator import days_remaining, is_overdue, completion_pct; "
            "from tasks.validator import is_valid_urgency, is_valid_days; "
            "print('priority_label(9)      =', priority_label(9)); "
            "print('priority_label(6)      =', priority_label(6)); "
            "print('priority_label(2)      =', priority_label(2)); "
            "print('is_high_priority(9)   =', is_high_priority(9)); "
            "print('is_high_priority(4)   =', is_high_priority(4)); "
            "print('days_remaining(5,20)  =', days_remaining(5, 20)); "
            "print('is_overdue(25,20)     =', is_overdue(25, 20)); "
            "print('completion_pct(7,10)  =', completion_pct(7, 10)); "
            "print('completion_pct(0,0)   =', completion_pct(0, 0)); "
            "print('is_valid_urgency(5)   =', is_valid_urgency(5)); "
            "print('is_valid_urgency(11)  =', is_valid_urgency(11)); "
            "print('is_valid_days(-1)     =', is_valid_days(-1)); "
        )
        r = subprocess.run([sys.executable, "-c", test_code], capture_output=True, text=True)
        if r.returncode == 0:
            print("  ✅ All functions executed successfully:")
            for line in r.stdout.strip().split("\n"):
                print(f"     {line}")
        else:
            print(f"  ❌ Error:\n{r.stderr}")
    else:
        if not all_ok:
            print("  ⚠️  Skipped (syntax errors present)")
        else:
            print("  ⚠️  No main.py found in output.")

    print("\n" + "=" * 60)
    print(f"  {'✅ EXPERIMENT COMPLETE' if all_ok else '⚠️  COMPLETE WITH ISSUES'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
