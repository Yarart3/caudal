"""Meses como «AAAA-MM»: validar, sumar y saber dónde acaban."""

import re
from datetime import date, timedelta

MONTH_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


def parse_month(text: str) -> date:
    """«2026-09» → date(2026, 9, 1). ValueError si no tiene el formato AAAA-MM."""
    match = MONTH_RE.match(text)
    if match is None:
        raise ValueError("El mes tiene que ser AAAA-MM")
    return date(int(match.group(1)), int(match.group(2)), 1)


def month_key(first_day: date) -> str:
    return f"{first_day.year:04d}-{first_day.month:02d}"


def add_months(first_day: date, months: int) -> date:
    """Primer día del mes que está `months` meses después (o antes, si es negativo)."""
    index = first_day.year * 12 + first_day.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def month_end(first_day: date) -> date:
    """Último día del mes."""
    return add_months(first_day, 1) - timedelta(days=1)


def last_months(first_day: date, count: int) -> list[date]:
    """Los `count` meses que acaban en `first_day`, del más antiguo al más reciente."""
    return [add_months(first_day, offset) for offset in range(1 - count, 1)]
