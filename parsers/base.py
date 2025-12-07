import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class FileSniff:
    """Lightweight peek data to help parsers decide if they can handle a file."""

    extension: str
    first_page_text: Optional[str] = None


class BankStatementParser(ABC):
    """
    Interface for bank statement parsers.

    Implementations should keep `can_parse` very specific to avoid false positives.
    """

    name: str

    @abstractmethod
    def can_parse(self, path: str, sniff: Optional[FileSniff] = None) -> bool:
        """Return True if this parser can handle the given file."""

    @abstractmethod
    def parse_file(self, path: str, sniff: Optional[FileSniff] = None) -> pd.DataFrame:
        """Parse a single statement file into a normalized DataFrame."""


def write_csv(df: pd.DataFrame, output_csv: str):
    """Atomic CSV writer shared by parsers/drivers."""
    tmp_path = f"{output_csv}.tmp"
    df.to_csv(tmp_path, index=False)
    os.replace(tmp_path, output_csv)
