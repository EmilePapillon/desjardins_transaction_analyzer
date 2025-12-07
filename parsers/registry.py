from typing import Dict, List

from .base import BankStatementParser
from .desjardins import DesjardinsParser
from .td import TDParser


def get_parsers() -> List[BankStatementParser]:
    return [DesjardinsParser(), TDParser()]


def get_parser_by_name(name: str) -> BankStatementParser:
    mapping: Dict[str, BankStatementParser] = {p.name: p for p in get_parsers()}
    try:
        return mapping[name]
    except KeyError as exc:
        raise ValueError(f"Unknown parser '{name}'") from exc
