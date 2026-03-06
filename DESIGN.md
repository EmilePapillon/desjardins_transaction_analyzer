Desjardins PDF Extractor & Analyzer — Design Notes

Purpose
- Extract transactions from bank statement PDFs (Desjardins, TD), normalize them, and generate interactive spending visuals plus an optional CSV export.
- Keep the pipeline scriptable (CLIs) but provide a lightweight GUI wrapper for non-technical users.

Architecture & Data Flow
- Entry points: `main.py` (CSV-only extraction) and `analyse.py` (charts + optional CSV). Both use the same parsing pipeline and ignore/filter logic.
- Statement discovery: `parsers/driver.py` walks the input directory, applies optional glob filters, sniffs each file (extension + first-page text), and chooses a parser (forced via `--bank` or auto-resolved). Soft-fails unmatched files, hard-fails multiple matches.
- Parsing contract: parsers implement `BankStatementParser` (`parsers/base.py`) with `can_parse` (guard against false positives) and `parse_file` (returns a normalized `DataFrame`).
- Data model (post-parse): columns include `file`, `transaction_date` (YYYY-MM-DD), `description`, `description_raw`, `amount` (float, spend > 0, refunds/credits < 0), `is_payment` (bool), and `parser`. Downstream analysis adds `year_month` and `merchant`.
- Post-parse cleaning (`analyse.py`): drop rows flagged as payments; reconcile reimbursements by matching negative amounts to same-description positive amounts (within tolerance) and removing both; drop unmatched credits. User-provided ignore patterns are applied before analysis.
- Outputs: `write_csv` writes atomically via a temp file; chart pages are written to an output directory with an `index.html` landing page.

Parsing Strategies
- Desjardins (`parsers/desjardins.py`):
  - Detects PDFs with "DATE DU RELE" + "DESJARDINS" on the first page.
  - Extracts text with pdfplumber, parses transaction lines via regex (dd mm posted, amount at end), cleans descriptions (collapsing whitespace, trimming trailing percentages), normalizes amounts (handles commas, CR suffixes, parentheses, leading minus).
  - Infers statement year from sniffed text, first page, or filename; skips rows with invalid dates, backwards posted dates, missing/invalid amounts, or empty descriptions; flags payments when descriptions start with "PAIEMENT CAISSE".
- TD (`parsers/td.py`):
  - Detects PDFs by TD branding/statement strings on the first page.
  - Parses the statement date range (e.g., OCT31/25-NOV28/25) to resolve years, handles year-crossing statements.
  - Extracts transactions line-by-line using date token detection and column heuristics; splits withdrawal/deposit columns and treats deposits as negative spend; flags payments when "PAYMENT" appears.
- Both parsers attach the originating filename and return data ready for downstream normalization.

User Settings & Filtering
- Ignore patterns can be provided via CLI (`-x`) and/or config files (`.extracts_ignore.{yaml,yml,json}` or home-dir equivalents). YAML supports simple list-of-strings structures; JSON uses keys `ignore_descriptions` and `ignore_descriptions_regex`.
- Filtering (`user_settings.py`): drops rows whose descriptions match any case-insensitive glob or regex; patterns are deduped case-insensitively.

Analysis & Feature Engineering (`analyse.py`)
- `prepare_dataframe`: coerces dates/amounts, drops invalid rows, derives `year_month`, ensures `description`, and extracts a coarse `merchant` prefix from the description.
- `drop_payments`: removes rows flagged as payments, reports count.
- `reconcile_reimbursements`: matches credits to like-sized debits (same description, within tolerance), removes matched pairs, and removes unmatched credits to avoid negative spend bias.
- Rolling/aggregation steps are done per-plot (monthly totals, daily sums + rolling mean, histogram bins, top merchants).

Visualization Layer
- Plot pages (`plots/*.py` implement `PlotPage`): Monthly spend bar chart, Daily spend line + rolling average, Amount histogram, and Top merchants horizontal bar chart. Plotly Express is used for quick grouping/labeling; figures embed Plotly JS via CDN.
- Detail drill-down: `ui/detail.py` builds `customdata` payloads mapping plot points to their contributing transactions; `wrap_html_with_detail` injects a detail panel that listens for Plotly click events, renders a sortable table, and shows counts/sort state.
- Styling: `ui/theme.py` defines light, minimal CSS for the index cards and detail tables (Arial, soft gray backgrounds/borders, hover states). `analyse.py` assembles an `index.html` card grid linking to each chart with brief descriptions and a footer note about payment/refund handling.

CLI Interfaces
- `./main.py -i releves -o transactions.csv` parses statements and writes a CSV. Options: `-g` globs, `--bank` to force a parser, `-v` verbose parsing logs, ignore pattern flags, optional ignore config path.
- `./analyse.py -i releves -o html --csv-output transactions.csv` runs the same parsing/cleaning, writes charts + optional CSV, supports a daily rolling window size for the daily plot.

GUI Launcher (`launcher.py`)
- Tkinter wrapper prompting for a statements ZIP and an output folder; unzips to a temp dir, runs `analyse.py`, opens `index.html`, and then the output directory. Supports PyInstaller single-file builds; when frozen, runs target scripts in-process to avoid nested launchers.

Extensibility Notes
- Adding a bank: implement `BankStatementParser`, register it in `parsers/registry.py`, and ensure `can_parse` is strict. Provide tests similar to `tests/test_td_parser.py`.
- Adding a chart: subclass `PlotPage`, implement `generate`, and add it to `plots/registry.py`; wire up `customdata` to enable transaction drill-down.
- User customization: extend ignore pattern handling or merchant extraction in `analyse.py` if more precise grouping is needed.
