import json
import re
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable, List, Tuple

import pandas as pd

DEFAULT_CONFIG_CANDIDATES = [
    Path(".extracts_ignore.yaml"),
    Path(".extracts_ignore.yml"),
    Path(".extracts_ignore.json"),
    Path.home() / ".extracts_ignore.yaml",
    Path.home() / ".extracts_ignore.yml",
    Path.home() / ".extracts_ignore.json",
]


def load_user_settings(config_path: Path | None = None) -> dict:
    """
    Load user settings from YAML or JSON. If the file is missing or invalid, return {}.
    """
    if config_path:
        candidates = [Path(config_path)]
    else:
        candidates = DEFAULT_CONFIG_CANDIDATES

    for path in candidates:
        try:
            if not path.exists():
                continue
            if path.suffix.lower() in {".yaml", ".yml"}:
                loaded = _load_yaml(path)
                if loaded is not None:
                    return loaded
            if path.suffix.lower() == ".json":
                with path.open("r", encoding="utf-8") as f:
                    return json.load(f) or {}
        except Exception:
            continue
    return {}


def collect_ignore_patterns(cli_patterns: Iterable[str] | None = None, config_path: Path | None = None) -> dict:
    """
    Gather ignore patterns from config and CLI-provided patterns.
    Returns a dict with 'glob' and 'regex' lists.
    """
    settings = load_user_settings(config_path)
    glob_patterns: List[str] = settings.get("ignore_descriptions", []) or []
    regex_patterns: List[str] = settings.get("ignore_descriptions_regex", []) or []

    if cli_patterns:
        glob_patterns.extend(cli_patterns)

    # Deduplicate while preserving order.
    glob_patterns = _dedupe(glob_patterns)
    regex_patterns = _dedupe(regex_patterns)

    return {"glob": glob_patterns, "regex": regex_patterns}


def _dedupe(items: Iterable[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in items:
        if not item:
            continue
        key = item.upper()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def filter_transactions_by_description(df: pd.DataFrame, patterns: dict) -> Tuple[pd.DataFrame, int]:
    """
    Drop rows whose description matches any glob or regex pattern (case-insensitive).
    `patterns` is a dict with keys 'glob' (list of glob patterns) and 'regex' (list of regex strings).
    """
    glob_patterns = patterns.get("glob") if patterns else None
    regex_patterns = patterns.get("regex") if patterns else None

    if df.empty or "description" not in df.columns:
        return df, 0
    if not (glob_patterns or regex_patterns):
        return df, 0

    glob_upper = [p.upper() for p in (glob_patterns or [])]
    regex_compiled = []
    for pat in regex_patterns or []:
        try:
            regex_compiled.append(re.compile(pat, re.IGNORECASE))
        except re.error:
            continue

    descriptions = df["description"].fillna("").astype(str)

    def matches_any(desc: str) -> bool:
        desc_upper = desc.upper()
        if any(fnmatch(desc_upper, pat) for pat in glob_upper):
            return True
        return any(rgx.search(desc) for rgx in regex_compiled)

    mask = descriptions.apply(matches_any)
    filtered = df[~mask].copy()
    return filtered, int(mask.sum())


def _load_yaml(path: Path) -> dict | None:
    """
    Minimal YAML loader supporting the simple list-of-strings structure we need.
    Tries PyYAML if available; otherwise falls back to a tiny parser for key: [list].
    """
    try:
        import yaml  # type: ignore
    except ImportError:
        return _load_yaml_simple(path)

    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return None


def _load_yaml_simple(path: Path) -> dict | None:
    """
    Parse a restricted YAML subset:
      key:
        - value1
        - value2
    """
    data: dict = {}
    current_key = None
    try:
        with path.open("r", encoding="utf-8") as f:
            for raw_line in f:
                line = _strip_inline_comment(raw_line.rstrip("\n"))
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if ":" in line and not line.startswith("-"):
                    key = line.split(":", 1)[0].strip()
                    current_key = key
                    data.setdefault(key, [])
                elif line.startswith("-") and current_key:
                    value = line.lstrip("-").strip().strip('"').strip("'")
                    data[current_key].append(value)
        return data
    except Exception:
        return None


def _strip_inline_comment(line: str) -> str:
    """Remove inline comments (# ...) when not inside quotes."""
    in_single = False
    in_double = False
    result = []
    for ch in line:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        if ch == "#" and not in_single and not in_double:
            break
        result.append(ch)
    return "".join(result)
