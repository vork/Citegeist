"""
Generate a human-readable Markdown report of all issues found.
"""

from datetime import datetime
from typing import TextIO
import sys

from .datatypes import Issue, IssueLevel, IssueType


_LEVEL_ICONS = {
    IssueLevel.INFO: "ℹ️ ",
    IssueLevel.WARNING: "⚠️ ",
    IssueLevel.ERROR: "❌",
}

_TYPE_LABELS = {
    IssueType.VENUE_STANDARDIZED: "Venue Standardized",
    IssueType.ARXIV_UPGRADED: "arXiv → Published",
    IssueType.ARXIV_NOT_FOUND_PUBLISHED: "arXiv (no pub. found)",
    IssueType.ENTRY_TYPE_FIXED: "Entry Type Fixed",
    IssueType.FIELD_NORMALIZED: "Field Normalized",
    IssueType.MISSING_FIELD: "Missing Field",
    IssueType.SUSPICIOUS_VENUE: "Suspicious Venue",
    IssueType.DUPLICATE_KEY: "Duplicate Key",
    IssueType.UNDEFINED_STRING: "Undefined @String",
    IssueType.MANUAL_REVIEW: "Manual Review Needed",
}


def _section(title: str, level: int = 2) -> str:
    return f"\n{'#' * level} {title}\n"


def generate_report(
    issues: list[Issue],
    input_path: str,
    output_path: str,
    n_total: int,
    n_arxiv_upgraded: int,
    n_manual_review: int,
) -> str:
    lines: list[str] = []

    lines.append("# BibTeX Check Report")
    lines.append(f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Input:**  `{input_path}`")
    lines.append(f"**Output:** `{output_path}`")

    # --- Summary ---
    lines.append(_section("Summary"))

    errors   = [i for i in issues if i.level == IssueLevel.ERROR]
    warnings = [i for i in issues if i.level == IssueLevel.WARNING]
    infos    = [i for i in issues if i.level == IssueLevel.INFO]

    lines.append(f"| Stat | Count |")
    lines.append(f"|------|-------|")
    lines.append(f"| Total entries | {n_total} |")
    lines.append(f"| Errors | {len(errors)} |")
    lines.append(f"| Warnings | {len(warnings)} |")
    lines.append(f"| Changes (info) | {len(infos)} |")
    lines.append(f"| arXiv → published upgrades | {n_arxiv_upgraded} |")
    lines.append(f"| Entries needing manual review | {n_manual_review} |")

    # --- Errors ---
    if errors:
        lines.append(_section("Errors", 2))
        lines.append("These must be fixed for the bib file to work correctly.\n")
        _append_issues_table(lines, errors)

    # --- Manual review ---
    manual = [i for i in issues if i.issue_type == IssueType.MANUAL_REVIEW]
    arxiv_no_pub = [i for i in issues
                    if i.issue_type == IssueType.ARXIV_NOT_FOUND_PUBLISHED]
    if manual or arxiv_no_pub:
        lines.append(_section("Manual Review Required", 2))
        lines.append(
            "The following entries are still arXiv preprints and no published "
            "version was found automatically. Please verify these manually.\n"
        )
        seen_keys: set[str] = set()
        for iss in arxiv_no_pub:
            if iss.key not in seen_keys:
                lines.append(f"- **`{iss.key}`** – {iss.message}")
                seen_keys.add(iss.key)

    # --- Warnings ---
    if warnings:
        lines.append(_section("Warnings", 2))
        _append_issues_table(lines, warnings)

    # --- Changes applied ---
    if infos:
        lines.append(_section("Changes Applied", 2))

        upgraded = [i for i in infos if i.issue_type == IssueType.ARXIV_UPGRADED]
        standardized = [i for i in infos if i.issue_type == IssueType.VENUE_STANDARDIZED]
        type_fixed = [i for i in infos if i.issue_type == IssueType.ENTRY_TYPE_FIXED]
        other_info = [i for i in infos
                      if i.issue_type not in {IssueType.ARXIV_UPGRADED,
                                               IssueType.VENUE_STANDARDIZED,
                                               IssueType.ENTRY_TYPE_FIXED}]

        if upgraded:
            lines.append(_section("arXiv → Published Upgrades", 3))
            _append_issues_table(lines, upgraded)

        if standardized:
            lines.append(_section("Venue Standardizations", 3))
            _append_issues_table(lines, standardized)

        if type_fixed:
            lines.append(_section("Entry Type Fixes", 3))
            _append_issues_table(lines, type_fixed)

        if other_info:
            lines.append(_section("Other Changes", 3))
            _append_issues_table(lines, other_info)

    return "\n".join(lines) + "\n"


def _append_issues_table(lines: list[str], issues: list[Issue]) -> None:
    lines.append("| Key | Type | Message | Old → New |")
    lines.append("|-----|------|---------|-----------|")
    for iss in issues:
        icon = _LEVEL_ICONS.get(iss.level, "")
        type_label = _TYPE_LABELS.get(iss.issue_type, str(iss.issue_type))
        old_new = ""
        if iss.old_value or iss.new_value:
            old = f"`{iss.old_value}`" if iss.old_value else "—"
            new = f"`{iss.new_value}`" if iss.new_value else "—"
            old_new = f"{old} → {new}"
        msg = iss.message.replace("|", "\\|")
        lines.append(
            f"| `{iss.key}` | {icon} {type_label} | {msg} | {old_new} |"
        )
    lines.append("")


def print_summary(issues: list[Issue], out: TextIO = sys.stderr) -> None:
    """Print a compact terminal summary."""
    errors   = sum(1 for i in issues if i.level == IssueLevel.ERROR)
    warnings = sum(1 for i in issues if i.level == IssueLevel.WARNING)
    upgraded = sum(1 for i in issues if i.issue_type == IssueType.ARXIV_UPGRADED)
    manual   = sum(1 for i in issues if i.issue_type == IssueType.MANUAL_REVIEW)

    print(f"\n{'='*60}", file=out)
    print(f" RESULTS", file=out)
    print(f"{'='*60}", file=out)
    if errors:
        print(f"  ❌ Errors:           {errors}", file=out)
    if warnings:
        print(f"  ⚠️  Warnings:         {warnings}", file=out)
    print(f"  🔄 arXiv upgraded:   {upgraded}", file=out)
    print(f"  👁  Manual review:    {manual}", file=out)
    print(f"{'='*60}\n", file=out)
