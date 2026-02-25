"""
Serialize fixed entries back to .bib format.
Emits canonical @String definitions first, then entries in their original
section order (preserving % comments as section separators).
"""

from .strings import CANONICAL_STRINGS

# Fields to emit in a consistent order (others come after, alphabetically)
FIELD_ORDER = [
    "author", "title", "booktitle", "journal", "year", "volume", "number",
    "pages", "month", "publisher", "institution", "school", "edition",
    "doi", "url", "eprint", "archiveprefix", "primaryclass",
    "issn", "isbn", "note", "howpublished", "urldate", "langid",
]

# Fields that should NOT be emitted in the output (internal bookkeeping)
INTERNAL_FIELDS = {"__key__", "__type__"}


def _serialize_value(raw: str) -> str:
    """
    Return the value in its serializable form.
    - Bare macro names stay bare.
    - Everything else gets braces if not already delimited.
    """
    v = raw.strip()
    if not v:
        return "{}"
    if (v.startswith("{") and v.endswith("}")) or (v.startswith('"') and v.endswith('"')):
        return v  # already delimited
    # bare number
    if v.lstrip("-").isdigit():
        return v
    # bare macro (in canonical strings)
    if v in CANONICAL_STRINGS:
        return v
    # wrap in braces
    return f"{{{v}}}"


def _emit_entry(entry: dict) -> str:
    etype = entry.get("__type__", "misc")
    key = entry.get("__key__", "unknown")
    lines = [f"@{etype}{{{key},"]

    # Collect fields
    field_items = {k: v for k, v in entry.items() if k not in INTERNAL_FIELDS}

    # Ordered fields first
    emitted = set()
    for field in FIELD_ORDER:
        if field in field_items and field_items[field].strip():
            val = _serialize_value(field_items[field])
            lines.append(f"  {field:<16} = {val},")
            emitted.add(field)

    # Remaining fields alphabetically
    for field in sorted(field_items.keys()):
        if field in emitted:
            continue
        if not field_items[field].strip():
            continue
        val = _serialize_value(field_items[field])
        lines.append(f"  {field:<16} = {val},")

    # Remove trailing comma from last field
    if len(lines) > 1:
        lines[-1] = lines[-1].rstrip(",")

    lines.append("}")
    return "\n".join(lines)


def _collect_used_macros(entries: list[dict]) -> set[str]:
    """Find all bare macro names actually used in the entries."""
    used = set()
    for entry in entries:
        for k, v in entry.items():
            if k in INTERNAL_FIELDS:
                continue
            vv = v.strip()
            if vv in CANONICAL_STRINGS:
                used.add(vv)
    return used


def write_bib(
    entries: list[dict],
    original_parsed: dict,
    used_macros: set[str] | None = None,
) -> str:
    """
    Produce the full .bib file content.

    Strategy:
    - Emit @String definitions for all canonical macros that are actually used.
    - Preserve raw section comments (lines starting with %).
    - Emit entries in original order.
    """
    parts: list[str] = []

    # --- @String block ---
    if used_macros is None:
        used_macros = _collect_used_macros(entries)

    if used_macros:
        parts.append("% ---- Venue / Journal Strings ----")
        for key in sorted(used_macros):
            display = CANONICAL_STRINGS[key]
            parts.append(f"@String{{{key:<16} = {{{display}}}}}")
        parts.append("")

    # --- Reconstruct entries with original section comments ---
    # Map from original entry keys to fixed entries
    fixed_map = {e["__key__"]: e for e in entries}

    # Interleave raw comments (section headers) with entries
    # We need to match comments to their position. Use a simple approach:
    # emit comments before each block, then the entries in original order.

    # Build an ordered list of (comment_text, [entry_key, ...]) blocks
    # by walking original_parsed["entries"] and "comments" in document order.
    # Since we don't track exact positions, we emit all section comments
    # and entries in original order.

    emitted_keys: set[str] = set()

    # Walk original entries in order, grouping by section comments
    orig_entries = original_parsed["entries"]
    comments_raw = [c for kind, c in original_parsed.get("comments", [])
                    if kind == "raw"]

    # Interleave: emit one block of comments then matching entries.
    # Simple heuristic: emit comments that appear at the document level
    # (i.e. between entries) by scanning original text positions isn't
    # available here. Instead, emit all raw-comment blocks as section
    # headers before the first entry that falls after them.
    # Since we don't have position info, emit section comments
    # proportionally (best effort).

    comment_idx = 0
    section_comment_texts = [c for kind, c in original_parsed.get("comments", [])
                              if kind == "raw" and "%" in c]

    n_orig = len(orig_entries)
    n_comments = len(section_comment_texts)

    for i, orig_entry in enumerate(orig_entries):
        orig_key = orig_entry.get("__key__", "")

        # Emit a proportional section comment if available
        comment_position = int(i * n_comments / max(n_orig, 1))
        while comment_idx < comment_position and comment_idx < n_comments:
            raw_comment = section_comment_texts[comment_idx].strip()
            if raw_comment:
                parts.append(raw_comment)
            comment_idx += 1

        if orig_key in fixed_map:
            entry_str = _emit_entry(fixed_map[orig_key])
            parts.append(entry_str)
            parts.append("")
            emitted_keys.add(orig_key)

    # Emit any remaining section comments
    while comment_idx < n_comments:
        raw_comment = section_comment_texts[comment_idx].strip()
        if raw_comment:
            parts.append(raw_comment)
        comment_idx += 1

    # Emit any entries not yet emitted (shouldn't happen normally)
    for entry in entries:
        k = entry.get("__key__", "")
        if k not in emitted_keys:
            parts.append(_emit_entry(entry))
            parts.append("")

    return "\n".join(parts) + "\n"
