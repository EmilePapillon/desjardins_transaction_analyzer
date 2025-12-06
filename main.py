#!/usr/bin/env python3
import os
import re
from datetime import datetime

import click
import pdfplumber
import pandas as pd


# ------------------------------------------------------
# Helper: parse one page's transaction table
# ------------------------------------------------------
def parse_page_transactions(page):
    """
    Given a pdfplumber page, extract raw transaction rows from
    the Desjardins transaction table.
    Returns a list of dicts with raw fields (no date/amount parsing yet).
    """
    tx_line_re = re.compile(r"^\d{2} \d{2} \d{2} \d{2}")
    text = page.extract_text() or ""
    rows = []
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"^(\d{2} \d{2})\s+(\d{2} \d{2})\s+(.*)$", line)
        if not m:
            continue
        tx_date, posted_date, rest = m.groups()
        amount_re = re.compile(
    r"(\d[\d\s]*,\d{2}CR?|\d[\d\s]*CR|\d[\d\s]*,\d{2})\s*$"
)
        m_amt = amount_re.search(rest)
        amt = m_amt.group(1)
        desc_raw = rest[:m_amt.start()].rstrip()
        desc = re.sub(r"\s*\d+,\d{2}\s*%$", "", desc_raw).rstrip()
        rows.append(
            {
                "transaction_date_raw": tx_date,
                "posted_date_raw": posted_date,
                "description": desc,
                "amount_raw": amt,
            }
        )
    return rows
# ------------------------------------------------------
# Helper: infer year from filename (use LAST 4-digit group)
# ------------------------------------------------------
def infer_year_from_filename(filename: str) -> int:
    """
    Desjardins filenames often contain multiple 4-digit chunks,
    e.g. '09-############3000-mars-2025.pdf'.
    We want the LAST 4-digit group as the statement year -> 2025.
    """
    matches = re.findall(r"(\d{4})", filename)
    if matches:
        return int(matches[-1])
    return datetime.now().year


# ------------------------------------------------------
# Helper: parse DD MM into datetime with given year
# ------------------------------------------------------
def parse_dd_mm(date_str: str, year: int):
    """
    Parse 'DD MM' into a datetime.date using the provided year.
    Returns a datetime or None on failure.
    """
    parts = date_str.split()
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        return None

    day = int(parts[0])
    month = int(parts[1])
    try:
        return datetime(year, month, day)
    except ValueError:
        return None


# ------------------------------------------------------
# Main extraction logic
# ------------------------------------------------------
def extract_all_pdfs(input_dir: str) -> pd.DataFrame:
    """
    Iterate all PDFs in input_dir, parse transactions from each,
    and return a combined DataFrame.
    """
    all_tx = []

    for filename in os.listdir(input_dir):
        if not filename.lower().endswith(".pdf"):
            continue

        pdf_path = os.path.join(input_dir, filename)
        year = infer_year_from_filename(filename)

        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                rows = parse_page_transactions(page)

                for r in rows:
                    dt_raw = r["transaction_date_raw"]
                    dp_raw = r["posted_date_raw"]

                    # Parse both dates consistently as YYYY-MM-DD
                    tx_date = parse_dd_mm(dt_raw, year)
                    posted_date = parse_dd_mm(dp_raw, year)
                    is_credit = False
                    if r["amount_raw"].endswith("CR"):
                        is_credit = True
                        r["amount_raw"] = r["amount_raw"][:-2]
                    # Parse French-style amount (e.g. "122,77")
                    amt_clean = (
                        r["amount_raw"]
                        .replace(" ", "")
                        .replace("\xa0", "")
                    )
                    if amt_clean.count(",") == 1 and amt_clean.count(".") == 0:
                        amt_clean = amt_clean.replace(",", ".")
                    try:
                        amount = float(amt_clean)
                    except ValueError:
                        continue
                    if is_credit:
                        amount = -amount
                    if r["description"] != "PAIEMENT CAISSE":
                        all_tx.append(
                            {
                                "file": filename,
                                "transaction_date": tx_date.strftime("%Y-%m-%d")
                                if tx_date
                                else None,
                                "posted_date": posted_date.strftime("%Y-%m-%d")
                                if posted_date
                                else None,
                                #"transaction_date_raw": dt_raw,
                                #"posted_date_raw": dp_raw,
                                "description": r["description"],
                                "amount": amount,
                            }
                        )

    return pd.DataFrame(all_tx)


# ------------------------------------------------------
# CLI with click
# ------------------------------------------------------
@click.command()
@click.option(
    "--input-dir",
    "-i",
    required=True,
    type=click.Path(exists=True, file_okay=False),
    help="Directory containing Desjardins PDF statements.",
)
@click.option(
    "--output-csv",
    "-o",
    required=True,
    type=click.Path(dir_okay=False),
    help="Output CSV file path.",
)
def main(input_dir, output_csv):
    """
    Extract all transactions from Desjardins credit card PDF statements
    in a directory and write them to a single CSV file.
    """
    click.echo(f"Reading PDFs from: {input_dir}")
    df = extract_all_pdfs(input_dir)

    if df.empty:
        click.echo("No transactions found. Check the input directory or PDF format.")
        return

    df.to_csv(output_csv, index=False)
    click.echo(f"Extracted {len(df)} transactions.")
    click.echo(f"Saved CSV to: {output_csv}")


if __name__ == "__main__":
    main()

