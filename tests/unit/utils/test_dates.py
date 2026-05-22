import pytest

from src.utils.dates import parse_optional_date


def test_parse_optional_date_accepts_iso_date():
    assert parse_optional_date("2026-05-22").isoformat() == "2026-05-22"


def test_parse_optional_date_returns_none_for_none():
    assert parse_optional_date(None) is None


def test_parse_optional_date_rejects_compact_dates_in_public_schema():
    with pytest.raises(ValueError):
        parse_optional_date("20260522")
