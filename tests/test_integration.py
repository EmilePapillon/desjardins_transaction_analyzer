#!/usr/bin/env python3
from pathlib import Path

import pandas as pd

from main import extract_all_pdfs

SUPPORT_DIR = Path(__file__).parent / "support"


def test_extract_from_sample_statements(tmp_path):
    df = extract_all_pdfs(str(SUPPORT_DIR))
    assert not df.empty

    expected_cols = {
        "file",
        "transaction_date",
        "posted_date",
        "transaction_date_raw",
        "posted_date_raw",
        "description",
        "description_raw",
        "amount",
        "is_payment",
    }
    assert expected_cols.issubset(df.columns)

    tx_dates = pd.to_datetime(df["transaction_date"], errors="coerce")
    posted_dates = pd.to_datetime(df["posted_date"], errors="coerce")
    assert tx_dates.notna().all()
    assert posted_dates.notna().all()
    assert (posted_dates >= tx_dates).all()

    amounts = pd.to_numeric(df["amount"], errors="coerce")
    assert amounts.notna().all()
    assert amounts.abs().sum() > 0

    assert set(df["is_payment"].dropna().unique()).issubset({True, False})

    out_csv = tmp_path / "out.csv"
    df.to_csv(out_csv, index=False)
    df_back = pd.read_csv(out_csv)
    assert len(df_back) == len(df)
    assert sorted(df_back.columns) == sorted(df.columns)
