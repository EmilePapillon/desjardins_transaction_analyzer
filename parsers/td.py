import os
import re
from datetime import date
from typing import Dict, List, Optional, Tuple

import pandas as pd
import pdfplumber

from .base import BankStatementParser, FileSniff

MONTH_MAP = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}

DATE_RANGE_RE = re.compile(
    r"([A-Z]{3})\s*(\d{1,2})/(\d{2})-([A-Z]{3})\s*(\d{1,2})/(\d{2})"
)


def parse_date_range(text: str) -> Optional[Tuple[Tuple[int, int, int], Tuple[int, int, int]]]:
    """
    Parse the statement date range (e.g., OCT31/25-NOV28/25) into start/end tuples.
    Returns ((start_year, start_month, start_day), (end_year, end_month, end_day))
    """
    m = DATE_RANGE_RE.search(text)
    if not m:
        return None

    start_mon, start_day, start_year = m.group(1), int(m.group(2)), int(m.group(3))
    end_mon, end_day, end_year = m.group(4), int(m.group(5)), int(m.group(6))

    return (
        (2000 + start_year, MONTH_MAP.get(start_mon, 0), start_day),
        (2000 + end_year, MONTH_MAP.get(end_mon, 0), end_day),
    )


def normalize_amount(raw: str) -> Optional[float]:
    """Convert currency string like '10,000.00' to float."""
    if not raw:
        return None
    try:
        return float(raw.replace(",", ""))
    except ValueError:
        return None


def choose_year(month: int, start: Tuple[int, int, int], end: Tuple[int, int, int]) -> int:
    start_year, start_month, _ = start
    end_year, end_month, _ = end
    if start_year == end_year:
        return start_year
    # Statements that cross years (e.g., DEC -> JAN) need month-aware year selection.
    return end_year if month < start_month else start_year


def parse_date_token(token: str, start: Tuple[int, int, int], end: Tuple[int, int, int]) -> Optional[date]:
    m = re.match(r"([A-Z]{3})\s*(\d{1,2})", token)
    if not m:
        return None
    mon_abbr, day = m.group(1), int(m.group(2))
    month = MONTH_MAP.get(mon_abbr)
    if not month:
        return None
    year = choose_year(month, start, end)
    try:
        return date(year, month, day)
    except ValueError:
        return None


def split_amounts(tokens: List[str]) -> Tuple[List[str], List[str]]:
    """
    Split tokens before the date into description tokens and amount tokens.
    Amount tokens are the trailing numeric tokens.
    """
    amount_indices: List[int] = []
    for idx in range(len(tokens) - 1, -1, -1):
        if re.fullmatch(r"-?\d[\d,]*\.\d{2}", tokens[idx]):
            amount_indices.append(idx)
        else:
            break

    if not amount_indices:
        return tokens, []

    amount_indices = sorted(amount_indices)
    description = [tok for idx, tok in enumerate(tokens) if idx not in amount_indices]
    amounts = [tokens[idx] for idx in amount_indices]
    return description, amounts


def parse_transaction_line(line: str, start: Tuple[int, int, int], end: Tuple[int, int, int]) -> Optional[Dict]:
    """
    Parse a single text line into a transaction dict, or None if not a transaction.
    """
    line_clean = line.strip()
    if not line_clean:
        return None

    upper = line_clean.upper()
    if upper.startswith("STARTING") or upper.startswith("CLOSING"):
        return None

    date_match = re.search(r"(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s?\d{1,2}", upper)
    if not date_match:
        return None
    date_token = date_match.group(0)

    tokens = line_clean.split()
    try:
        date_idx = next(i for i, tok in enumerate(tokens) if date_token.replace(" ", "") in tok.upper())
    except StopIteration:
        return None

    before_date = tokens[:date_idx]
    description_tokens, amount_tokens = split_amounts(before_date)

    if not amount_tokens:
        return None

    tx_date = parse_date_token(date_token.replace(" ", ""), start, end)
    if tx_date is None:
        return None

    description = " ".join(description_tokens).strip()
    if not description:
        return None

    # Withdrawals/Deposits columns: if two amounts, second is deposit; treat deposits as negative spend.
    amounts = [normalize_amount(a) for a in amount_tokens]
    if any(a is None for a in amounts):
        return None

    amount_value: Optional[float] = None
    if len(amounts) >= 2:
        withdrawal, deposit = amounts[0], amounts[1]
        if deposit and deposit != 0:
            amount_value = -deposit
        elif withdrawal is not None:
            amount_value = withdrawal
    else:
        amount_value = amounts[0]

    if amount_value is None:
        return None

    return {
        "transaction_date": tx_date.strftime("%Y-%m-%d"),
        "description": description,
        "description_raw": " ".join(description_tokens),
        "amount": amount_value,
        "is_payment": "PAYMENT" in upper,
    }


class TDParser(BankStatementParser):
    name = "td"

    def can_parse(self, path: str, sniff: Optional[FileSniff] = None) -> bool:
        if not path.lower().endswith(".pdf"):
            return False

        text = sniff.first_page_text if sniff else None
        if text is None:
            try:
                with pdfplumber.open(path) as pdf:
                    if not pdf.pages:
                        return False
                    text = pdf.pages[0].extract_text() or ""
            except Exception:
                return False

        upper = text.upper()
        has_brand = "THETORONTO-DOMINIONBANK" in upper or "TORONTO-DOMINION BANK" in upper
        has_statement = "STATEMENT OFACCOUNT" in upper or "STATEMENT OF ACCOUNT" in upper
        has_branch = "BRANCHNO." in upper
        return bool(has_brand and has_statement and has_branch)

    def parse_file(self, path: str, sniff: Optional[FileSniff] = None) -> pd.DataFrame:
        filename = os.path.basename(path)
        try:
            with pdfplumber.open(path) as pdf:
                first_page_text = sniff.first_page_text if sniff else (pdf.pages[0].extract_text() if pdf.pages else "")
                start_end = parse_date_range(first_page_text or "")
                if not start_end:
                    # Fallback: try parsing from filename digits, assume single-month statement.
                    year_match = re.search(r"(20\d{2})", filename)
                    fallback_year = int(year_match.group(1)) if year_match else date.today().year
                    # Assume month from filename like _Oct_ etc; default to end-of-year.
                    fallback_month = 12
                    start_end = ((fallback_year, fallback_month, 1), (fallback_year, fallback_month, 28))

                start, end = start_end

                rows: List[Dict] = []
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    for line in text.splitlines():
                        tx = parse_transaction_line(line, start, end)
                        if tx:
                            tx["file"] = filename
                            rows.append(tx)

                return pd.DataFrame(rows)
        except Exception as exc:
            raise RuntimeError(f"Failed to read {path}: {exc}") from exc
