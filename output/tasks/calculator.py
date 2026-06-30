def days_remaining(current_day: int, due_day: int) -> int:
    return due_day - current_day

def is_overdue(current_day: int, due_day: int) -> bool:
    return current_day > due_day

def completion_pct(done: int, total: int) -> float:
    if total == 0:
        return 0.0
    else:
        return done / total * 100
