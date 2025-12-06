#!/usr/bin/env python3
import pytest

from main import parse_dd_mm, parse_page_transactions


class FakePage:
    """Minimal pdfplumber-like page returning controlled text."""

    def __init__(self, text: str):
        self._text = text

    def extract_text(self):
        return self._text


def test_parse_page_transactions_basic_and_percent_stripping():
    sample = "\n".join(
        [
            "01 06 02 06 ZEHRS #529 PARKWAY WINDSOR ON 3,00 % 90,45",
            "02 06 03 06 THE HOME DEPOT #7184 WINDSOR ON 1,50 % 57,63",
        ]
    )
    rows = parse_page_transactions(FakePage(sample))
    assert len(rows) == 2
    assert rows[0]["transaction_date_raw"] == "01 06"
    assert rows[0]["posted_date_raw"] == "02 06"
    assert rows[0]["amount_raw"] == "90,45"
    assert rows[0]["description_raw"].startswith("ZEHRS #529")
    assert rows[0]["description"] == "ZEHRS #529 PARKWAY WINDSOR ON"


def test_parse_page_transactions_credit_and_spacing():
    sample = "05 06 05 06 REFUND ABC STORE 1,00 % 12,34CR"
    rows = parse_page_transactions(FakePage(sample))
    assert len(rows) == 1
    assert rows[0]["amount_raw"] == "12,34CR"
    assert rows[0]["description"] == "REFUND ABC STORE"


def test_parse_page_transactions_parentheses_negative():
    sample = "10 06 11 06 SAMPLE STORE 1,00 % (45,67)"
    rows = parse_page_transactions(FakePage(sample))
    assert len(rows) == 1
    assert rows[0]["amount_raw"] == "(45,67)"


def test_parse_dd_mm_validation():
    assert parse_dd_mm("10 06", 2025).strftime("%Y-%m-%d") == "2025-06-10"
    assert parse_dd_mm("32 06", 2025) is None  # invalid day
    assert parse_dd_mm("10-06", 2025) is None  # wrong format
