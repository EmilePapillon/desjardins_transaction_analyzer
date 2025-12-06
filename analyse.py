#!/usr/bin/env python3
import os
from datetime import datetime

import click
import pandas as pd
import plotly.express as px


def ensure_output_dir(path: str):
    os.makedirs(path, exist_ok=True)


def load_data(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    # Parse transaction_date as datetime
    if "transaction_date" not in df.columns:
        raise ValueError("CSV must contain a 'transaction_date' column.")

    df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
    df = df.dropna(subset=["transaction_date"])

    # Ensure amount exists and is numeric
    if "amount" not in df.columns:
        raise ValueError("CSV must contain an 'amount' column.")

    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df = df.dropna(subset=["amount"])

    # Derive year-month and merchant (rough)
    df["year_month"] = df["transaction_date"].dt.to_period("M").astype(str)
    # crude merchant extraction from description
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

    # Group debits by description for quick lookup
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
            # Unmatched credit: drop from expense analysis
            to_drop.add(idx_credit)

    return df.drop(index=list(to_drop)).copy(), len(to_drop)


def plot_monthly_spending(df: pd.DataFrame, out_dir: str):
    monthly = df.groupby("year_month")["amount"].sum().reset_index()

    fig = px.bar(
        monthly,
        x="year_month",
        y="amount",
        labels={"year_month": "Month", "amount": "Total spending (CAD)"},
        title="Monthly Spending",
    )
    fig.update_layout(xaxis_tickangle=-45)

    out_path = os.path.join(out_dir, "monthly_spending.html")
    fig.write_html(out_path)


def plot_daily_spending(df: pd.DataFrame, out_dir: str, window: int = 7):
    daily = df.groupby(df["transaction_date"].dt.date)["amount"].sum().reset_index()
    daily.rename(columns={"transaction_date": "date"}, inplace=True)
    daily = daily.sort_values("date")
    # Rolling mean for smoothing
    daily["rolling_mean"] = (
        daily["amount"].rolling(window=window, min_periods=1, center=False).mean()
    )

    fig = px.line(
        daily,
        x="date",
        y=["amount", "rolling_mean"],
        labels={"value": "Spending (CAD)", "date": "Date"},
        title=f"Daily Spending (with {window}-day rolling average)",
    )
    fig.update_layout(legend_title_text="Series")

    out_path = os.path.join(out_dir, "daily_spending.html")
    fig.write_html(out_path)


def plot_amount_histogram(df: pd.DataFrame, out_dir: str):
    fig = px.histogram(
        df[df["amount"] > 0],
        x="amount",
        nbins=40,
        labels={"amount": "Transaction amount (CAD)"},
        title="Distribution of Transaction Amounts",
    )

    out_path = os.path.join(out_dir, "amount_histogram.html")
    fig.write_html(out_path)


def plot_top_merchants(df: pd.DataFrame, out_dir: str, top_n: int = 15):
    by_merchant = (
        df.groupby("merchant")["amount"]
        .sum()
        .sort_values(ascending=False)
        .head(top_n)
        .reset_index()
    )

    fig = px.bar(
        by_merchant,
        x="amount",
        y="merchant",
        orientation="h",
        labels={"amount": "Total spending (CAD)", "merchant": "Merchant"},
        title=f"Top {top_n} Merchants by Spend",
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"})

    out_path = os.path.join(out_dir, "top_merchants.html")
    fig.write_html(out_path)


@click.command()
@click.option(
    "--input-csv",
    "-i",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to the CSV file produced by the extractor script.",
)
@click.option(
    "--output-dir",
    "-o",
    required=True,
    type=click.Path(file_okay=False),
    help="Directory where Plotly HTML charts will be saved.",
)
@click.option(
    "--rolling-window",
    "-w",
    default=7,
    show_default=True,
    help="Window size (in days) for daily spending rolling average.",
)
def main(input_csv, output_dir, rolling_window):
    """
    Analyze credit-card CSV transactions and generate
    interactive Plotly visualizations.
    """
    ensure_output_dir(output_dir)
    print(f"Loading data from: {input_csv}")
    df_raw = load_data(input_csv)

    df_no_payments, removed_payments = drop_payments(df_raw)
    df_expenses, removed_reimbursed = reconcile_reimbursements(df_no_payments)

    print(
        f"Cleaning: dropped {removed_payments} payments and {removed_reimbursed} "
        f"reimbursed/refunded rows. Remaining expenses: {len(df_expenses)}"
    )

    print("Generating monthly spending chart...")
    plot_monthly_spending(df_expenses, output_dir)

    print("Generating daily spending chart...")
    plot_daily_spending(df_expenses, output_dir, window=rolling_window)

    print("Generating transaction amount histogram...")
    plot_amount_histogram(df_expenses, output_dir)

    print("Generating top merchants chart...")
    plot_top_merchants(df_expenses, output_dir)

    print(f"Done. Open the HTML files in {output_dir} in your browser.")


if __name__ == "__main__":
    main()
