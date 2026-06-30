from tasks.priority import priority_label, is_high_priority
from tasks.calculator import days_remaining, is_overdue, completion_pct
from reports.summary import task_summary_label, progress_report

def main() -> None:
    label = priority_label(9)
    high = is_high_priority(9)
    days = days_remaining(5, 20)
    overdue = is_overdue(25, 20)
    pct = completion_pct(7, 10)
    summary = task_summary_label(9, 5, 20)
    progress = progress_report(7, 10)
    return None
