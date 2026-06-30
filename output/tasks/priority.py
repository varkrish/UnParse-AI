def is_high_priority(urgency: int) -> bool:
    return urgency >= 8

def priority_label(urgency: int) -> str:
    if urgency >= 8:
        return 'HIGH'
    elif urgency >= 5:
        return 'MEDIUM'
    else:
        return 'LOW'
