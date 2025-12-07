#!/usr/bin/env python3
import click

from parsers import parse_statements, write_csv
from parsers.desjardins import parse_dd_mm, parse_page_transactions
from user_settings import collect_ignore_patterns, filter_transactions_by_description


@click.command()
@click.option(
    "--input-dir",
    "-i",
    required=True,
    type=click.Path(exists=True, file_okay=False),
    help="Directory containing statement files.",
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
    help="Only process filenames matching these glob patterns (can be given multiple times).",
)
@click.option(
    "--bank",
    default=None,
    help="Force a specific parser (by name). If set, the parser must accept each file it handles.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Print per-file parsing info.",
)
@click.option(
    "--ignore-pattern",
    "-x",
    "ignore_patterns",
    multiple=True,
    help="Glob pattern(s) of descriptions to drop (applied after parsing).",
)
@click.option(
    "--ignore-config",
    default=None,
    type=click.Path(dir_okay=False, exists=False),
    help="Optional JSON config file with ignore settings (defaults to ~/.extracts_ignore.json).",
)
def main(input_dir, output_csv, patterns, bank, verbose, ignore_patterns, ignore_config):
    """
    Parse statement files with the available bank parsers and write a CSV extract.
    """
    df, unmatched = parse_statements(input_dir, patterns=list(patterns) or None, bank=bank, verbose=verbose)

    if unmatched:
        click.echo("The following files were not parsed:")
        for path in unmatched:
            click.echo(f"  - {path}")

    if df.empty:
        click.echo("No transactions found. Check the input files or parser selection.")
        return

    patterns_all = collect_ignore_patterns(ignore_patterns, config_path=ignore_config)
    df, dropped = filter_transactions_by_description(df, patterns_all)
    if dropped:
        click.echo(f"Filtered {dropped} transactions using ignore patterns.")

    write_csv(df, output_csv)
    click.echo(f"Extracted {len(df)} transactions.")
    click.echo(f"Saved CSV to: {output_csv}")


if __name__ == "__main__":
    main()
