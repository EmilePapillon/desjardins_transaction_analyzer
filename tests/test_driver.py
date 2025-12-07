#!/usr/bin/env python3
import pandas as pd
import pytest

from parsers import driver
from parsers.base import BankStatementParser, FileSniff


class AlwaysYesParser(BankStatementParser):
    name = "yes"

    def can_parse(self, path: str, sniff: FileSniff | None = None) -> bool:
        return True

    def parse_file(self, path: str, sniff: FileSniff | None = None) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "file": path,
                    "transaction_date": "2025-01-01",
                    "description": "X",
                    "amount": 1.0,
                    "is_payment": False,
                }
            ]
        )


class AlwaysNoParser(BankStatementParser):
    name = "no"

    def can_parse(self, path: str, sniff: FileSniff | None = None) -> bool:
        return False

    def parse_file(self, path: str, sniff: FileSniff | None = None) -> pd.DataFrame:
        raise AssertionError("should not be called")


def test_unmatched_files_soft_fail(monkeypatch, tmp_path):
    f = tmp_path / "noop.pdf"
    f.write_text("dummy")

    monkeypatch.setattr(driver, "get_parsers", lambda: [])

    df, unmatched = driver.parse_statements(str(tmp_path))
    assert df.empty
    assert unmatched == [str(f)]


def test_multi_match_hard_fails(monkeypatch, tmp_path):
    f = tmp_path / "multi.pdf"
    f.write_text("dummy")

    monkeypatch.setattr(
        driver,
        "get_parsers",
        lambda: [AlwaysYesParser(), AlwaysYesParser()],
    )

    with pytest.raises(RuntimeError, match="Multiple parsers match file"):
        driver.parse_statements(str(tmp_path))


def test_forced_parser_must_accept(monkeypatch, tmp_path):
    f = tmp_path / "forced.pdf"
    f.write_text("dummy")

    forced = AlwaysNoParser()
    monkeypatch.setattr(driver, "get_parser_by_name", lambda name: forced)
    monkeypatch.setattr(driver, "get_parsers", lambda: [AlwaysYesParser()])

    with pytest.raises(RuntimeError, match="Forced parser .* cannot parse file"):
        driver.parse_statements(str(tmp_path), bank="forced")
