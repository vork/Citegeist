"""
Command-line entry point for the BibTeX reference checker.

Usage:
    bib-check references.bib [options]
"""

import argparse
import sys
from pathlib import Path

from .checker import BibChecker
from .datatypes import IssueType
from .parser import parse_bib_file
from .report import generate_report, print_summary
from .search import PublicationLookup
from .writer import _collect_used_macros, write_bib


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bib-check",
        description=(
            "Check, standardize, and upgrade a BibTeX file.\n\n"
            "Performs:\n"
            "  • Venue/journal name standardization via @String macros\n"
            "  • arXiv preprint → published paper upgrades (online search)\n"
            "  • Missing required field detection\n"
            "  • Duplicate cite-key detection\n"
            "  • Undefined @String macro detection\n"
            "  • Entry type inference (@misc → @article / @inproceedings)\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("bib_file", type=Path, help="Input .bib file")
    p.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output .bib file (default: <input>_fixed.bib)",
    )
    p.add_argument(
        "-r", "--report",
        type=Path,
        default=None,
        help="Output report file (default: <input>_report.md)",
    )
    p.add_argument(
        "--offline",
        action="store_true",
        help="Skip all network lookups (no arXiv / Semantic Scholar / CrossRef queries)",
    )
    p.add_argument(
        "--no-upgrade",
        action="store_true",
        help="Do not attempt to upgrade arXiv entries to published versions",
    )
    p.add_argument(
        "--perplexity-key",
        metavar="KEY",
        default=None,
        help=(
            "Perplexity AI API key for web-search based lookups "
            "(overrides PERPLEXITY_API_KEY env var). "
            "Get a key at https://www.perplexity.ai/settings/api"
        ),
    )
    p.add_argument(
        "--no-learn-venues",
        action="store_true",
        help=(
            "Do not save newly discovered venues to venues.json. "
            "By default, unrecognized venues are automatically added to venues.json "
            "with a suggested abbreviation for manual review."
        ),
    )
    p.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print detailed progress to stderr",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    bib_path: Path = args.bib_file
    if not bib_path.exists():
        print(f"Error: file not found: {bib_path}", file=sys.stderr)
        return 1

    output_path: Path = args.output or bib_path.with_name(
        bib_path.stem + "_fixed" + bib_path.suffix
    )
    report_path: Path = args.report or bib_path.with_name(
        bib_path.stem + "_report.md"
    )

    # --- Parse ---
    print(f"Parsing {bib_path} ...", file=sys.stderr)
    text = bib_path.read_text(encoding="utf-8")
    parsed = parse_bib_file(text)
    n_total = len(parsed["entries"])
    print(f"  Found {n_total} entries, {len(parsed['strings'])} @String macros.", file=sys.stderr)

    # --- Check ---
    skip_network = args.offline or args.no_upgrade
    lookup = (
        PublicationLookup(verbose=args.verbose, perplexity_api_key=args.perplexity_key)
        if not skip_network else None
    )
    checker = BibChecker(
        lookup=lookup,
        skip_network=skip_network,
        verbose=args.verbose,
        learn_venues=not args.no_learn_venues,
    )

    print("Checking entries ...", file=sys.stderr)
    fixed_entries, issues = checker.check_entries(parsed)

    # --- Stats ---
    n_upgraded = sum(1 for i in issues if i.issue_type == IssueType.ARXIV_UPGRADED)
    n_manual   = sum(1 for i in issues if i.issue_type == IssueType.MANUAL_REVIEW)

    # --- Write fixed bib ---
    used_macros = _collect_used_macros(fixed_entries)
    bib_content = write_bib(fixed_entries, parsed, used_macros=used_macros)
    output_path.write_text(bib_content, encoding="utf-8")
    print(f"Fixed bib written to: {output_path}", file=sys.stderr)

    # --- Write report ---
    report_content = generate_report(
        issues=issues,
        input_path=str(bib_path),
        output_path=str(output_path),
        n_total=n_total,
        n_arxiv_upgraded=n_upgraded,
        n_manual_review=n_manual,
    )
    report_path.write_text(report_content, encoding="utf-8")
    print(f"Report written to:    {report_path}", file=sys.stderr)

    # --- Terminal summary ---
    print_summary(issues)

    # Return non-zero if there are errors
    n_errors = sum(1 for i in issues if i.issue_type.name == "ERROR")
    return 1 if n_errors else 0


if __name__ == "__main__":
    sys.exit(main())
