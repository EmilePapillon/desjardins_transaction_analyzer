#!/usr/bin/env python3
from parsers.td import (
    TDParser,
    parse_date_range,
    parse_transaction_line,
)


def test_parse_date_range_and_year_selection():
    header = "BranchNo. Account No. OCT31/25-NOV28/25"
    start_end = parse_date_range(header)
    assert start_end == ((2025, 10, 31), (2025, 11, 28))


def test_parse_transaction_withdrawal_line():
    start_end = ((2025, 10, 31), (2025, 11, 28))
    line = "SENDE-TFR***mYS 133.60 NOV03 293,851.47"
    tx = parse_transaction_line(line, *start_end)
    assert tx
    assert tx["transaction_date"] == "2025-11-03"
    assert tx["amount"] == 133.60
    assert tx["description"] == "SENDE-TFR***mYS"


def test_parse_transaction_deposit_line_sets_negative_amount():
    start_end = ((2025, 10, 31), (2025, 11, 28))
    line = "PAYROLL CO 0.00 1,234.56 NOV05 300,000.00"
    tx = parse_transaction_line(line, *start_end)
    assert tx
    assert tx["transaction_date"] == "2025-11-05"
    assert tx["amount"] == -1234.56
    assert tx["description"] == "PAYROLL CO"


def test_non_transaction_lines_are_ignored():
    start_end = ((2025, 10, 31), (2025, 11, 28))
    line = "STARTINGBALANCE OCT31 293,985.07"
    assert parse_transaction_line(line, *start_end) is None


def test_can_parse_uses_sniff_text():
    parser = TDParser()
    sniff_text = "STATEMENT OFACCOUNT\nACCOUNTISSUEDBY:THETORONTO-DOMINIONBANK\nBRANCHNO."
    from parsers.base import FileSniff

    sniff = FileSniff(extension=".pdf", first_page_text=sniff_text)
    assert parser.can_parse("statement.pdf", sniff=sniff)
