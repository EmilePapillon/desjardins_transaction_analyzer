#!/usr/bin/env python3
import pandas as pd

from user_settings import collect_ignore_patterns, filter_transactions_by_description


def test_collect_ignore_patterns_merges_and_dedupes():
    patterns = collect_ignore_patterns(["SEND E-TFR*", "send e-tfr*"])
    globs = patterns["glob"]
    assert "SEND E-TFR*" in globs
    # Deduped despite different casing.
    assert len([p for p in globs if p.upper() == "SEND E-TFR*"]) == 1
    # Regex list should exist even if empty.
    assert isinstance(patterns["regex"], list)


def test_filter_transactions_by_description():
    df = pd.DataFrame(
        [
            {"description": "SENDE-TFR***vDb", "amount": 100},
            {"description": "GROCERY STORE", "amount": 50},
        ]
    )
    filtered, dropped = filter_transactions_by_description(df, {"glob": ["SENDE-TFR***vDb"], "regex": []})
    assert dropped == 1
    assert len(filtered) == 1
    assert filtered.iloc[0]["description"] == "GROCERY STORE"


def test_filter_transactions_by_regex():
    df = pd.DataFrame(
        [
            {"description": "SENDE-TFR***ABC", "amount": 100},
            {"description": "Other", "amount": 10},
        ]
    )
    filtered, dropped = filter_transactions_by_description(df, {"glob": [], "regex": [r"^SENDE-TFR"]})
    assert dropped == 1
    assert len(filtered) == 1
