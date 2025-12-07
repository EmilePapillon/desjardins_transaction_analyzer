#!/usr/bin/env python3
from pathlib import Path

import pandas as pd

from parsers import parse_statements

SUPPORT_DIR = Path(__file__).parent / "support"


def test_extract_from_sample_statements(tmp_path):
    df, unmatched = parse_statements(str(SUPPORT_DIR))
    assert not unmatched
    assert not df.empty

    expected_cols = {
        "file",
        "transaction_date",
        "description",
        "description_raw",
        "amount",
        "is_payment",
        "parser",
    }
    assert expected_cols.issubset(df.columns)

    tx_dates = pd.to_datetime(df["transaction_date"], errors="coerce")
    assert tx_dates.notna().all()

    amounts = pd.to_numeric(df["amount"], errors="coerce")
    assert amounts.notna().all()
    assert amounts.abs().sum() > 0

    assert set(df["is_payment"].dropna().unique()).issubset({True, False})

    out_csv = tmp_path / "out.csv"
    df.to_csv(out_csv, index=False)
    df_back = pd.read_csv(out_csv)
    assert len(df_back) == len(df)
    assert sorted(df_back.columns) == sorted(df.columns)
