#!/usr/bin/env python3
import click

from parsers import parse_statements, write_csv
from parsers.desjardins import parse_dd_mm, parse_page_transactions


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
def main(input_dir, output_csv, patterns, bank, verbose):
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

    write_csv(df, output_csv)
    click.echo(f"Extracted {len(df)} transactions.")
    click.echo(f"Saved CSV to: {output_csv}")


if __name__ == "__main__":
    main()
