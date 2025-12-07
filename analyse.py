#!/usr/bin/env python3
import os
from typing import List

import click
import pandas as pd

from parsers import parse_statements, write_csv
from plots import get_plot_pages
from plots.theme import INDEX_PAGE_STYLES


def ensure_output_dir(path: str):
    os.makedirs(path, exist_ok=True)


def prepare_dataframe(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Normalize dates/amounts and derive helper columns for plotting."""
    if "transaction_date" not in df_raw.columns:
        raise ValueError("Data must contain a 'transaction_date' column.")
    if "amount" not in df_raw.columns:
        raise ValueError("Data must contain an 'amount' column.")

    df = df_raw.copy()
    df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
    df = df.dropna(subset=["transaction_date"])

    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df = df.dropna(subset=["amount"])

    df["year_month"] = df["transaction_date"].dt.to_period("M").astype(str)
    if "description" not in df.columns:
        df["description"] = ""
    df["merchant"] = (
        df["description"]
        .astype(str)
        .str.extract(r"^([A-Za-z0-9 #.&*\-]+)")[0]
        .fillna("UNKNOWN")
    )
    return df


def drop_payments(df: pd.DataFrame):
    """Remove payment rows from the dataset."""
    if "is_payment" not in df.columns:
        return df, 0
    is_payment = df["is_payment"].fillna(False)
    removed = int(is_payment.sum())
    return df[~is_payment].copy(), removed


def reconcile_reimbursements(df: pd.DataFrame, tolerance: float = 0.01):
    """
    Match negative amounts (credits/refunds) to positive amounts with the same
    description and nearly equal magnitude. Drops both the credit and the matched
    debit, leaving only unreimbursed expenses. Unmatched credits are removed
    from the expense view (they reduce spend elsewhere).
    """
    df = df.copy()
    to_drop = set()
    credits = df[df["amount"] < 0]
    debits = df[df["amount"] > 0]

    debit_groups = {}
    for idx, row in debits.iterrows():
        debit_groups.setdefault(row["description"], []).append((idx, row["amount"]))

    for idx_credit, credit in credits.iterrows():
        candidates = debit_groups.get(credit["description"], [])
        match_idx = None
        for idx_debit, amount in candidates:
            if idx_debit in to_drop:
                continue
            if abs(amount + credit["amount"]) <= tolerance:
                match_idx = idx_debit
                break
        if match_idx is not None:
            to_drop.add(idx_credit)
            to_drop.add(match_idx)
        else:
            to_drop.add(idx_credit)

    return df.drop(index=list(to_drop)).copy(), len(to_drop)


def write_index_html(out_dir: str, pages: List):
    cards = "\n".join(
        [
            f"    <div class=\"card\">\n      <a href=\"{p.filename}\">{p.title}</a>\n      <p>{p.description}</p>\n    </div>"
            for p in pages
        ]
    )
    html = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\">
  <title>Spending Analysis</title>
  <style>
{INDEX_PAGE_STYLES}
  </style>
</head>
<body>
  <h1>Spending Analysis</h1>
  <p>Open a chart below to explore the underlying transactions (click bars/points for details, sort columns in the detail tables).</p>
  <div class=\"cards\">
{cards}
  </div>
  <div class=\"footer\">Payments are excluded; matched reimbursements are removed from spend.</div>
</body>
</html>
"""
    out_path = os.path.join(out_dir, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)


@click.command()
@click.option(
    "--input-dir",
    "-i",
    required=True,
    type=click.Path(exists=True, file_okay=False),
    help="Directory containing statement files.",
)
@click.option(
    "--output-dir",
    "-o",
    required=True,
    type=click.Path(file_okay=False),
    help="Directory where Plotly HTML charts will be saved.",
)
@click.option(
    "--glob",
    "-g",
    "patterns",
    multiple=True,
    help="Only process filenames matching these glob patterns (can be given multiple times).",
)
@click.option(
    "--bank",
    default=None,
    help="Force a specific parser (by name). If set, the parser must accept each file it handles.",
)
@click.option(
    "--csv-output",
    default=None,
    type=click.Path(dir_okay=False),
    help="Optional path to also save the parsed transactions as CSV.",
)
@click.option(
    "--rolling-window",
    "-w",
    default=7,
    show_default=True,
    help="Window size (in days) for daily spending rolling average.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Print per-file parsing info.",
)
def main(input_dir, output_dir, patterns, bank, csv_output, rolling_window, verbose):
    """
    Parse statements with available bank parsers and generate interactive charts.
    """
    ensure_output_dir(output_dir)

    print(f"Reading statements from: {input_dir}")
    df_raw, unmatched = parse_statements(input_dir, patterns=list(patterns) or None, bank=bank, verbose=verbose)

    if unmatched:
        print("The following files were not parsed:")
        for path in unmatched:
            print(f"  - {path}")

    if df_raw.empty:
        print("No transactions found. Check the input files or parser selection.")
        return

    df_prepared = prepare_dataframe(df_raw)

    df_no_payments, removed_payments = drop_payments(df_prepared)
    df_expenses, removed_reimbursed = reconcile_reimbursements(df_no_payments)

    print(
        f"Cleaning: dropped {removed_payments} payments and {removed_reimbursed} "
        f"reimbursed/refunded rows. Remaining expenses: {len(df_expenses)}"
    )

    if csv_output:
        write_csv(df_raw, csv_output)
        print(f"Saved parsed transactions to CSV: {csv_output}")

    pages = get_plot_pages(rolling_window=rolling_window)
    for page in pages:
        print(f"Generating {page.title}...")
        page.generate(df_expenses, output_dir)

    print("Writing index page...")
    write_index_html(output_dir, pages)

    print(f"Done. Open the HTML files in {output_dir} in your browser.")


if __name__ == "__main__":
    main()
