#!/usr/bin/env python3
import os
import re
from datetime import datetime
from fnmatch import fnmatch
from typing import Dict, List, Optional

import click
import pdfplumber
import pandas as pd

# Precompiled regexes
TX_LINE_RE = re.compile(r"^(?P<tx>\d{2} \d{2})\s+(?P<posted>\d{2} \d{2})\s+(?P<rest>.+)$")
AMOUNT_TRAIL_RE = re.compile(
    r"(?P<amount>(?:-?\d[\d\s]*,\d{2}(?:CR)?|-?\d[\d\s]*CR|\(\d[\d\s]*,\d{2}\)))\s*$"
)
PERCENT_TRAIL_RE = re.compile(r"\s*\d+,\d{2}\s*%$")


# ------------------------------------------------------
# Helper: parse statement date from page header (fallback to filename)
# ------------------------------------------------------
def parse_statement_date_from_page(page) -> Optional[int]:
    """
    Try to extract the statement year from a header line like:
    'DATE DU RELEVÉ Jour 10 Mois 06 Année 2025'
    Returns the year int or None.
    """
    text = page.extract_text() or ""
    m = re.search(r"DATE DU RELEV[ÉE].*?Ann[ée]e\s+(\d{4})", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


# ------------------------------------------------------
# Helper: parse one page's transaction table
# ------------------------------------------------------
def parse_page_transactions(page) -> List[Dict[str, str]]:
    """
    Given a pdfplumber page, extract raw transaction rows from
    the Desjardins transaction table.
    Returns a list of dicts with raw fields (no date/amount parsing yet).
    """
    text = page.extract_text() or ""
    rows = []
    for line in text.splitlines():
        line = line.strip()
        m = TX_LINE_RE.match(line)
        if not m:
            continue
        tx_date, posted_date, rest = m.group("tx"), m.group("posted"), m.group("rest")
        m_amt = AMOUNT_TRAIL_RE.search(rest)
        if not m_amt:
            continue
        amt = m_amt.group("amount")
        desc_raw = rest[: m_amt.start()].rstrip()
        desc = re.sub(PERCENT_TRAIL_RE, "", desc_raw).rstrip()
        desc = re.sub(r"\s{2,}", " ", desc)
        rows.append(
            {
                "transaction_date_raw": tx_date,
                "posted_date_raw": posted_date,
                "description_raw": desc_raw,
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
# Helper: determine statement year for a PDF
# ------------------------------------------------------
def determine_statement_year(pdf_path: str, filename: str) -> int:
    """
    Try to extract the statement year from page 1, otherwise fall
    back to filename inference, and finally current year.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if pdf.pages:
                year = parse_statement_date_from_page(pdf.pages[0])
                if year:
                    return year
    except Exception:
        # Fallback handled below; keep silent to avoid noisy failures on malformed PDFs.
        pass
    inferred = infer_year_from_filename(filename)
    return inferred


# ------------------------------------------------------
# Main extraction logic
# ------------------------------------------------------
def extract_all_pdfs(
    input_dir: str, patterns: Optional[List[str]] = None, verbose: bool = False
) -> pd.DataFrame:
    """
    Iterate all PDFs in input_dir, parse transactions from each,
    and return a combined DataFrame.
    """
    all_tx = []
    parsed = 0
    skipped = 0

    for filename in sorted(os.listdir(input_dir)):
        if not filename.lower().endswith(".pdf"):
            continue
        if patterns and not any(fnmatch(filename, pat) for pat in patterns):
            continue

        pdf_path = os.path.join(input_dir, filename)
        year = determine_statement_year(pdf_path, filename)

        before_parsed = parsed
        before_skipped = skipped
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    rows = parse_page_transactions(page)

                    for r in rows:
                        dt_raw = r["transaction_date_raw"]
                        dp_raw = r["posted_date_raw"]

                        # Parse both dates consistently as YYYY-MM-DD
                        tx_date = parse_dd_mm(dt_raw, year)
                        posted_date = parse_dd_mm(dp_raw, year)
                        if tx_date is None or posted_date is None:
                            skipped += 1
                            continue
                        if posted_date < tx_date:
                            skipped += 1
                            continue

                        amt_raw = r["amount_raw"]
                        is_credit = False
                        amt_stripped = amt_raw
                        if amt_raw.endswith("CR"):
                            is_credit = True
                            amt_stripped = amt_raw[:-2]
                        negative = False
                        if amt_stripped.startswith("-"):
                            negative = True
                            amt_stripped = amt_stripped[1:]
                        if amt_stripped.startswith("(") and amt_stripped.endswith(")"):
                            negative = True
                            amt_stripped = amt_stripped.strip("()")

                        # Parse French-style amount (e.g. "122,77")
                        amt_clean = amt_stripped.replace(" ", "").replace("\xa0", "")
                        if amt_clean.count(",") == 1 and amt_clean.count(".") == 0:
                            amt_clean = amt_clean.replace(",", ".")
                        try:
                            amount = float(amt_clean)
                        except ValueError:
                            skipped += 1
                            continue
                        if is_credit or negative:
                            amount = -amount

                        description = r.get("description", "")
                        description_raw = r.get("description_raw", "")
                        if not description:
                            skipped += 1
                            continue

                        is_payment = description.upper().startswith("PAIEMENT CAISSE")

                        all_tx.append(
                            {
                                "file": filename,
                                "transaction_date": tx_date.strftime("%Y-%m-%d"),
                                "posted_date": posted_date.strftime("%Y-%m-%d"),
                                "transaction_date_raw": dt_raw,
                                "posted_date_raw": dp_raw,
                                "description": description,
                                "description_raw": description_raw,
                                "amount": amount,
                                "is_payment": is_payment,
                            }
                        )
                        parsed += 1
        except Exception as exc:
            click.echo(f"Failed to read {pdf_path}: {exc}", err=True)
            continue

        if verbose:
            click.echo(
                f"{filename}: parsed {parsed - before_parsed} rows (skipped {skipped - before_skipped})"
            )

    if verbose:
        click.echo(f"Total parsed: {parsed}, skipped: {skipped}")

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
@click.option(
    "--glob",
    "-g",
    "patterns",
    multiple=True,
    help="Only process PDF filenames matching these glob patterns (can be given multiple times).",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Print per-file and summary parsing stats.",
)
def main(input_dir, output_csv, patterns, verbose):
    """
    Extract all transactions from Desjardins credit card PDF statements
    in a directory and write them to a single CSV file.
    """
    click.echo(f"Reading PDFs from: {input_dir}")
    df = extract_all_pdfs(input_dir, patterns=list(patterns) or None, verbose=verbose)

    if df.empty:
        click.echo("No transactions found. Check the input directory or PDF format.")
        return

    tmp_path = f"{output_csv}.tmp"
    df.to_csv(tmp_path, index=False)
    os.replace(tmp_path, output_csv)
    click.echo(f"Extracted {len(df)} transactions.")
    click.echo(f"Saved CSV to: {output_csv}")


if __name__ == "__main__":
    main()
