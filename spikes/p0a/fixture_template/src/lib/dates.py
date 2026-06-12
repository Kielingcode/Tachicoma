from datetime import date, timedelta


def add_business_days(start: date, days: int) -> date:
    current = start
    remaining = days
    while remaining > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


def quarter_of(d: date) -> int:
    return (d.month - 1) // 3 + 1
