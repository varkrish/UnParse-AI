from tasks.priority import priority_label
from tasks.calculator import days_remaining, completion_pct

def task_summary_label(urgency: int, current_day: int, due_day: int) -> str:
    label = priority_label(urgency)
    days = days_remaining(current_day, due_day)
    return label

def progress_report(done: int, total: int) -> float:
    pct = completion_pct(done, total)
    return pct
