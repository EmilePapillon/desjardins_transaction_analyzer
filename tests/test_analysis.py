#!/usr/bin/env python3
import pandas as pd

from analyse import drop_payments, reconcile_reimbursements


def test_drop_payments():
    df = pd.DataFrame(
        {
            "description": ["PAYMENT", "STORE"],
            "amount": [-100, 50],
            "is_payment": [True, False],
        }
    )
    cleaned, removed = drop_payments(df)
    assert removed == 1
    assert len(cleaned) == 1
    assert cleaned.iloc[0]["description"] == "STORE"


def test_reconcile_reimbursements_matches_and_drops():
    df = pd.DataFrame(
        {
            "description": ["STORE A", "STORE A", "STORE B"],
            "amount": [100.00, -100.00, 25.00],
            "is_payment": [False, False, False],
        }
    )
    cleaned, removed = reconcile_reimbursements(df, tolerance=0.01)
    # one pair dropped (2 rows), unmatched debit remains
    assert removed == 2
    assert len(cleaned) == 1
    assert cleaned.iloc[0]["description"] == "STORE B"
    assert cleaned.iloc[0]["amount"] == 25.00


def test_reconcile_reimbursements_drops_unmatched_credit():
    df = pd.DataFrame(
        {
            "description": ["STORE A", "REFUND X"],
            "amount": [50.0, -20.0],
            "is_payment": [False, False],
        }
    )
    cleaned, removed = reconcile_reimbursements(df, tolerance=0.01)
    # the credit is dropped even without a match
    assert removed == 1
    assert len(cleaned) == 1
    assert cleaned.iloc[0]["amount"] == 50.0
