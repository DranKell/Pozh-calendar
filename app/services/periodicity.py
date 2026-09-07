# -*- coding: utf-8 -*-
"""Периодичность работ. «Разовая» = «по необходимости» = «по вызову»."""
import calendar
from datetime import date, timedelta

FREQUENCIES = [
    "Разовая",
    "Еженедельно",
    "Ежемесячно",
    "Ежеквартально",
    "Раз в полгода",
    "Ежегодно",
    "Раз в 3 года",
    "Раз в 5 лет",
]

ONETIME_KEYS = ("разов", "необходим", "вызов", "требован", "однократн")


def add_months_anchor(base_date, months):
    """Сдвиг на N месяцев от базовой даты с сохранением исходного числа месяца."""
    idx = base_date.month - 1 + months
    year = base_date.year + idx // 12
    month = idx % 12 + 1
    max_day = calendar.monthrange(year, month)[1]
    day = min(base_date.day, max_day)
    return date(year, month, day)


def frequency_months(freq):
    """0 = разовая, -7 = еженедельно, иначе интервал в месяцах."""
    f = (freq or "").lower().strip()
    if any(k in f for k in ONETIME_KEYS):
        return 0
    if "недел" in f:
        return -7
    if "ежемесяч" in f or "раз в месяц" in f or "каждый месяц" in f:
        return 1
    if "квартал" in f:
        return 3
    if "полгода" in f or "6 мес" in f:
        return 6
    if "ежегод" in f or "раз в год" in f or "каждый год" in f:
        return 12
    if "3 год" in f or "три года" in f:
        return 36
    if "5 лет" in f or "пять лет" in f:
        return 60
    return 12


def generate_schedule(start, end, freq):
    """Список дат выполнений от start до end включительно."""
    if not start or not end or end < start:
        return []
    months = frequency_months(freq)
    if months == 0:
        return [start]
    if months == -7:
        schedule = []
        current = start
        while current <= end:
            schedule.append(current)
            current += timedelta(days=7)
        return schedule

    schedule = []
    step = 0
    while True:
        current = add_months_anchor(start, step * months)
        if current > end:
            break
        schedule.append(current)
        step += 1
    return schedule

