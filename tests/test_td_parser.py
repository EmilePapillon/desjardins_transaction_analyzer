#!/usr/bin/env python3
from parsers.td import (
    TDParser,
    parse_date_range,
    parse_transaction_line,
    parse_words_row,
)


def test_parse_date_range_and_year_selection():
    header = "BranchNo. Account No. OCT31/25-NOV28/25"
    start_end = parse_date_range(header)
    assert start_end == ((2025, 10, 31), (2025, 11, 28))


def test_parse_transaction_withdrawal_line():
    start_end = ((2025, 10, 31), (2025, 11, 28))
    line = "SENDE-TFR***ABC 250.00 NOV03 9,750.00"
    tx = parse_transaction_line(line, *start_end)
    assert tx
    assert tx["transaction_date"] == "2025-11-03"
    assert tx["amount"] == 250.00
    assert tx["description"] == "SENDE-TFR***ABC"


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
    line = "STARTINGBALANCE OCT31 10,000.00"
    assert parse_transaction_line(line, *start_end) is None


def _make_word(text, x0, top=100.0):
    return {"text": text, "x0": x0, "x1": x0 + 40, "top": top, "bottom": top + 10}


def test_parse_words_row_withdrawal():
    """Amount in withdrawal column (x0 < deposit threshold) → positive."""
    start_end = ((2025, 10, 31), (2025, 11, 28))
    row = [
        _make_word("SENDE-TFR", 69),
        _make_word("250.00", 279),   # withdrawal column
        _make_word("NOV03", 416),
        _make_word("9,750.00", 491),
    ]
    tx = parse_words_row(row, *start_end, deposit_threshold=339.0)
    assert tx is not None
    assert tx["amount"] == 250.00
    assert tx["transaction_date"] == "2025-11-03"
    assert tx["description"] == "SENDE-TFR"


def test_parse_words_row_deposit_is_negative():
    """Amount in deposit column (x0 >= deposit threshold) → negative."""
    start_end = ((2025, 4, 30), (2025, 5, 30))
    row = [
        _make_word("MOBILEDEPOSIT", 69),
        _make_word("487.00", 378),   # deposit column (x0 >= 339)
        _make_word("MAY22", 416),
    ]
    tx = parse_words_row(row, *start_end, deposit_threshold=339.0)
    assert tx is not None
    assert tx["amount"] == -487.00
    assert tx["transaction_date"] == "2025-05-22"


def test_parse_words_row_starting_balance_ignored():
    start_end = ((2025, 4, 30), (2025, 5, 30))
    row = [
        _make_word("STARTINGBALANCE", 69),
        _make_word("APR30", 416),
        _make_word("153,054.16", 491),
    ]
    assert parse_words_row(row, *start_end, deposit_threshold=339.0) is None


def test_can_parse_uses_sniff_text():
    parser = TDParser()
    sniff_text = "STATEMENT OFACCOUNT\nACCOUNTISSUEDBY:THETORONTO-DOMINIONBANK\nBRANCHNO."
    from parsers.base import FileSniff

    sniff = FileSniff(extension=".pdf", first_page_text=sniff_text)
    assert parser.can_parse("statement.pdf", sniff=sniff)
