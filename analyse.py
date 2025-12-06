#!/usr/bin/env python3
import os
from datetime import datetime
from typing import Dict, List

import click
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


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


def format_rows_for_detail(rows: pd.DataFrame) -> List[Dict]:
    """Convert a set of rows into serializable dicts for customdata."""
    subset = rows[["transaction_date", "description", "amount"]].copy()
    subset["transaction_date"] = subset["transaction_date"].astype(str)
    subset["description"] = subset["description"].astype(str)
    return subset.to_dict(orient="records")


def wrap_html_with_detail(fig_html: str, title: str, chart_id: str, detail_id: str) -> str:
    """Embed a detail container and click handler alongside the Plotly chart HTML."""
    style = """
    <style>
    body { font-family: Arial, sans-serif; margin: 0 auto; padding: 16px; max-width: 1100px; }
    .detail-box { margin-top: 12px; padding: 12px; border: 1px solid #ddd; border-radius: 6px; background: #fafafa; }
    .detail-box table { border-collapse: collapse; width: 100%; }
    .detail-box th, .detail-box td { text-align: left; padding: 6px; border-bottom: 1px solid #eee; }
    .detail-box th { cursor: pointer; user-select: none; }
    .detail-box tr:hover { background: #f2f2f2; }
    </style>
    """
    script = f"""
    <script>
    (function() {{
      const chart = document.getElementById('{chart_id}');
      const detail = document.getElementById('{detail_id}');
      if (!chart || !detail) return;
      const state = {{ rows: [], baseRows: [], sortKey: null, sortDir: 'none' }};
      const comparator = (a, b, key) => {{
        const va = a[key];
        const vb = b[key];
        if (key === 'amount') {{
          return (parseFloat(va) || 0) - (parseFloat(vb) || 0);
        }}
        return String(va || '').localeCompare(String(vb || ''), undefined, {{ numeric: true }});
      }};
      const cycleDir = (current) => current === 'none' ? 'asc' : current === 'asc' ? 'desc' : 'none';
      const applySort = () => {{
        if (state.sortDir === 'none' || !state.sortKey) return state.baseRows.slice();
        const sorted = state.baseRows.slice().sort((a,b) => comparator(a,b,state.sortKey));
        if (state.sortDir === 'desc') sorted.reverse();
        return sorted;
      }};
      const dirSymbol = (key) => {{
        if (state.sortKey !== key) return '';
        return state.sortDir === 'asc' ? ' ↑' : state.sortDir === 'desc' ? ' ↓' : '';
      }};
      const renderTable = () => {{
        if (!state.baseRows.length) {{
          detail.innerHTML = '<strong>No transactions for this selection.</strong>';
          return;
        }}
        const header = `<tr>
          <th data-sort="transaction_date">Date${{dirSymbol('transaction_date')}}</th>
          <th data-sort="description">Description${{dirSymbol('description')}}</th>
          <th data-sort="amount">Amount${{dirSymbol('amount')}}</th>
        </tr>`;
        const rows = applySort();
        const body = rows.map(r => {{
          const amt = typeof r.amount === 'number' ? r.amount.toFixed(2) : r.amount;
          return `<tr><td>${{r.transaction_date || ''}}</td><td>${{r.description || ''}}</td><td>${{amt}}</td></tr>`;
        }}).join('');
        const sortLabel = state.sortDir === 'none' ? '' : ' (sorted ' + state.sortDir + ' by ' + state.sortKey + ')';
        detail.innerHTML = `<h3>{title} — Transactions</h3><table>` + header + body + '</table><div>' + rows.length + ' transaction(s)' + sortLabel + '</div>';
      }};
      chart.on('plotly_click', function(ev) {{
        if (!ev.points || !ev.points.length) return;
        const rows = ev.points[0].customdata || [];
        state.baseRows = rows.slice();
        state.sortKey = null;
        state.sortDir = 'none';
        renderTable();
      }});
      detail.addEventListener('click', (ev) => {{
        const th = ev.target.closest('th[data-sort]');
        if (!th) return;
        const key = th.getAttribute('data-sort');
        state.sortDir = cycleDir(state.sortDir);
        state.sortKey = state.sortDir === 'none' ? null : key;
        renderTable();
      }});
    }})();
    </script>
    """
    return f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{title}</title>{style}</head><body>{fig_html}<div id='{detail_id}' class='detail-box'>Click a bar/point to see transactions.</div>{script}</body></html>"


def plot_monthly_spending(df: pd.DataFrame, out_dir: str):
    monthly = (
        df.groupby("year_month")["amount"]
        .agg(total="sum", count="size")
        .reset_index()
        .sort_values("year_month")
    )

    custom = [
        format_rows_for_detail(df[df["year_month"] == ym])
        for ym in monthly["year_month"]
    ]

    fig = px.bar(
        monthly,
        x="year_month",
        y="total",
        labels={"year_month": "Month", "total": "Total spending (CAD)"},
        title="Monthly Spending",
        hover_data={"count": True},
    )
    fig.update_layout(xaxis_tickangle=-45)
    fig.update_traces(customdata=custom)

    fig_html = fig.to_html(full_html=False, include_plotlyjs="cdn", div_id="chart-monthly")
    html = wrap_html_with_detail(fig_html, "Monthly Spending", "chart-monthly", "detail-monthly")

    out_path = os.path.join(out_dir, "monthly_spending.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)


def plot_daily_spending(df: pd.DataFrame, out_dir: str, window: int = 7):
    daily = (
        df.groupby(df["transaction_date"].dt.date)["amount"]
        .sum()
        .reset_index()
        .rename(columns={"transaction_date": "date"})
        .sort_values("date")
    )
    daily["rolling_mean"] = (
        daily["amount"].rolling(window=window, min_periods=1, center=False).mean()
    )

    custom = [
        format_rows_for_detail(df[df["transaction_date"].dt.date == d])
        for d in daily["date"]
    ]

    fig = px.line(
        daily,
        x="date",
        y=["amount", "rolling_mean"],
        labels={"value": "Spending (CAD)", "date": "Date"},
        title=f"Daily Spending (with {window}-day rolling average)",
    )
    fig.update_layout(legend_title_text="Series")
    if fig.data:
        fig.data[0].customdata = custom  # amount series
        fig.data[0].hovertemplate = "Date: %{x}<br>Amount: %{y:.2f}<extra></extra>"
    if len(fig.data) > 1:
        fig.data[1].hovertemplate = "Date: %{x}<br>Rolling mean: %{y:.2f}<extra></extra>"

    fig_html = fig.to_html(full_html=False, include_plotlyjs="cdn", div_id="chart-daily")
    html = wrap_html_with_detail(fig_html, "Daily Spending", "chart-daily", "detail-daily")

    out_path = os.path.join(out_dir, "daily_spending.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)


def plot_amount_histogram(df: pd.DataFrame, out_dir: str):
    positive = df[df["amount"] > 0].copy()
    if positive.empty:
        fig = go.Figure()
        fig.update_layout(title="Distribution of Transaction Amounts")
        custom = []
        bin_df = pd.DataFrame({"bin_label": [], "count": []})
    else:
        positive["bin"] = pd.cut(positive["amount"], bins=40, include_lowest=True)
        bin_df = (
            positive.groupby("bin")["amount"]
            .agg(count="size")
            .reset_index()
            .sort_values("bin")
        )
        bin_df["bin_label"] = bin_df["bin"].astype(str)
        custom = [
            format_rows_for_detail(positive[positive["bin"] == interval])
            for interval in bin_df["bin"]
        ]

        fig = px.bar(
            bin_df,
            x="bin_label",
            y="count",
            labels={"bin_label": "Amount range (CAD)", "count": "Transaction count"},
            title="Distribution of Transaction Amounts",
        )
        fig.update_layout(xaxis_tickangle=-45)
        fig.update_traces(customdata=custom, hovertemplate="Range: %{x}<br>Count: %{y}<extra></extra>")

    fig_html = fig.to_html(full_html=False, include_plotlyjs="cdn", div_id="chart-hist")
    html = wrap_html_with_detail(fig_html, "Amount Distribution", "chart-hist", "detail-hist")

    out_path = os.path.join(out_dir, "amount_histogram.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)


def plot_top_merchants(df: pd.DataFrame, out_dir: str, top_n: int = 15):
    by_merchant = (
        df.groupby("merchant")["amount"]
        .sum()
        .sort_values(ascending=False)
        .head(top_n)
        .reset_index()
    )

    custom = [
        format_rows_for_detail(df[df["merchant"] == m]) for m in by_merchant["merchant"]
    ]

    fig = px.bar(
        by_merchant,
        x="amount",
        y="merchant",
        orientation="h",
        labels={"amount": "Total spending (CAD)", "merchant": "Merchant"},
        title=f"Top {top_n} Merchants by Spend",
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    fig.update_traces(customdata=custom, hovertemplate="Merchant: %{y}<br>Spend: %{x:.2f}<extra></extra>")

    fig_html = fig.to_html(full_html=False, include_plotlyjs="cdn", div_id="chart-merchants")
    html = wrap_html_with_detail(fig_html, "Top Merchants", "chart-merchants", "detail-merchants")

    out_path = os.path.join(out_dir, "top_merchants.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)


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
