def is_valid_urgency(urgency: int) -> bool:
    if urgency < 1:
        return False
    if urgency > 10:
        return False
    return True

def is_valid_days(days: int) -> bool:
    if days < 0:
        return False
    return True
