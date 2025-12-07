import os
import re
from datetime import datetime
from fnmatch import fnmatch
from typing import Dict, List, Optional

import pandas as pd
import pdfplumber

from .base import BankStatementParser, FileSniff

TX_LINE_RE = re.compile(r"^(?P<tx>\d{2} \d{2})\s+(?P<posted>\d{2} \d{2})\s+(?P<rest>.+)$")
AMOUNT_TRAIL_RE = re.compile(
    r"(?P<amount>(?:-?\d[\d\s]*,\d{2}(?:CR)?|-?\d[\d\s]*CR|\(\d[\d\s]*,\d{2}\)))\s*$"
)
PERCENT_TRAIL_RE = re.compile(r"\s*\d+,\d{2}\s*%$")


class DesjardinsParser(BankStatementParser):
    name = "desjardins"

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

        text_upper = text.upper()
        has_header = "DATE DU RELE" in text_upper
        has_brand = "DESJARDINS" in text_upper
        return bool(has_header and has_brand)

    def parse_file(self, path: str, sniff: Optional[FileSniff] = None) -> pd.DataFrame:
        filename = os.path.basename(path)
        year = determine_statement_year(path, filename, sniff=sniff)

        all_tx = []
        parsed = 0
        skipped = 0

        try:
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    rows = parse_page_transactions(page)

                    for r in rows:
                        dt_raw = r["transaction_date_raw"]
                        dp_raw = r["posted_date_raw"]

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
            raise RuntimeError(f"Failed to read {path}: {exc}") from exc

        return pd.DataFrame(all_tx)


def parse_statement_date_from_page(page) -> Optional[int]:
    text = page.extract_text() or ""
    m = re.search(r"DATE DU RELEV[ÉE].*?Ann[ée]e\s+(\d{4})", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def parse_page_transactions(page) -> List[Dict[str, str]]:
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


def infer_year_from_filename(filename: str) -> int:
    matches = re.findall(r"(\d{4})", filename)
    if matches:
        return int(matches[-1])
    return datetime.now().year


def parse_dd_mm(date_str: str, year: int):
    parts = date_str.split()
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        return None

    day = int(parts[0])
    month = int(parts[1])
    try:
        return datetime(year, month, day)
    except ValueError:
        return None


def determine_statement_year(pdf_path: str, filename: str, sniff: Optional[FileSniff] = None) -> int:
    if sniff and sniff.first_page_text:
        m = re.search(r"Ann[ée]e\s+(\d{4})", sniff.first_page_text, re.IGNORECASE)
        if m:
            return int(m.group(1))

    try:
        with pdfplumber.open(pdf_path) as pdf:
            if pdf.pages:
                year = parse_statement_date_from_page(pdf.pages[0])
                if year:
                    return year
    except Exception:
        pass
    return infer_year_from_filename(filename)


def collect_files(input_dir: str, patterns: Optional[List[str]] = None) -> List[str]:
    files = []
    for filename in sorted(os.listdir(input_dir)):
        if patterns and not any(fnmatch(filename, pat) for pat in patterns):
            continue
        path = os.path.join(input_dir, filename)
        if os.path.isfile(path):
            files.append(path)
    return files
