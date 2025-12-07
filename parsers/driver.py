import os
from fnmatch import fnmatch
from typing import List, Optional, Tuple

import pandas as pd
import pdfplumber

from .base import BankStatementParser, FileSniff
from .registry import get_parser_by_name, get_parsers


def sniff_file(path: str) -> FileSniff:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        try:
            with pdfplumber.open(path) as pdf:
                if pdf.pages:
                    text = pdf.pages[0].extract_text() or ""
                    return FileSniff(extension=ext, first_page_text=text)
        except Exception:
            return FileSniff(extension=ext)
    return FileSniff(extension=ext)


def iter_statement_files(input_dir: str, patterns: Optional[List[str]] = None) -> List[str]:
    files: List[str] = []
    for filename in sorted(os.listdir(input_dir)):
        if patterns and not any(fnmatch(filename, pat) for pat in patterns):
            continue
        path = os.path.join(input_dir, filename)
        if os.path.isfile(path):
            files.append(path)
    return files


def resolve_parser(path: str, sniff: FileSniff, forced: Optional[BankStatementParser], available: List[BankStatementParser]):
    if forced is not None:
        if not forced.can_parse(path, sniff=sniff):
            raise RuntimeError(f"Forced parser '{forced.name}' cannot parse file: {path}")
        return forced

    matches = [p for p in available if p.can_parse(path, sniff=sniff)]
    if not matches:
        return None
    if len(matches) > 1:
        names = ", ".join(p.name for p in matches)
        raise RuntimeError(f"Multiple parsers match file {path}: {names}")
    return matches[0]


def parse_statements(input_dir: str, patterns: Optional[List[str]] = None, bank: Optional[str] = None, verbose: bool = False) -> Tuple[pd.DataFrame, List[str]]:
    available = get_parsers()
    forced = get_parser_by_name(bank) if bank else None

    unmatched: List[str] = []
    dfs = []
    files = iter_statement_files(input_dir, patterns=patterns)

    for path in files:
        sniff = sniff_file(path)
        parser = resolve_parser(path, sniff, forced, available)
        if parser is None:
            unmatched.append(path)
            if verbose:
                print(f"No parser for file: {path}")
            continue
        if verbose:
            print(f"Parsing {path} with {parser.name}...")
        df = parser.parse_file(path, sniff=sniff)
        df["parser"] = parser.name
        dfs.append(df)

    combined = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    return combined, unmatched
