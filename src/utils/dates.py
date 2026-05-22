from __future__ import annotations

from datetime import date


def parse_optional_date(value: str | None) -> date | None:
    if value is None:
        return None
    if len(value) != 10 or value[4] != "-" or value[7] != "-":
        raise ValueError("Dates must use YYYY-MM-DD format.")
    return date.fromisoformat(value)
