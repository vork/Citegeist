"""
BibTeX parser that preserves @String macros, comments, and preambles.
Returns a structured representation of the bib file.
"""

import re
from typing import Optional


# ---------------------------------------------------------------------------
# Tokeniser helpers
# ---------------------------------------------------------------------------

def _find_matching_brace(text: str, start: int) -> int:
    """Return the index of the closing brace matching the open brace at *start*."""
    depth = 0
    i = start
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError(f"Unmatched brace starting at position {start}")


def _find_matching_paren(text: str, start: int) -> int:
    """Return the index of the closing paren matching the open paren at *start*."""
    depth = 0
    i = start
    while i < len(text):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError(f"Unmatched parenthesis starting at position {start}")


# ---------------------------------------------------------------------------
# Field value parsing
# ---------------------------------------------------------------------------

def _parse_value(text: str) -> str:
    """
    Parse a BibTeX field value (possibly concatenated with #).
    Returns the raw string (without outer delimiters) but keeps the
    structure for macro detection later.
    """
    text = text.strip()
    parts: list[str] = []
    i = 0
    while i < len(text):
        # Skip whitespace
        while i < len(text) and text[i].isspace():
            i += 1
        if i >= len(text):
            break
        if text[i] == "{":
            end = _find_matching_brace(text, i)
            parts.append(text[i : end + 1])
            i = end + 1
        elif text[i] == '"':
            # Find closing quote (not escaped)
            j = i + 1
            while j < len(text):
                if text[j] == '"' and text[j - 1] != "\\":
                    break
                j += 1
            parts.append(text[i : j + 1])
            i = j + 1
        else:
            # Bare word / macro name / number
            j = i
            while j < len(text) and text[j] not in (",", "}", ")", "#", " ", "\t", "\n"):
                j += 1
            parts.append(text[i:j])
            i = j

        # Skip '#' concatenation operator
        while i < len(text) and text[i].isspace():
            i += 1
        if i < len(text) and text[i] == "#":
            i += 1

    return " # ".join(parts)


# ---------------------------------------------------------------------------
# Entry parser
# ---------------------------------------------------------------------------

def _parse_entry_body(body: str) -> dict[str, str]:
    """Parse the key-value pairs inside a @Type{...} entry body."""
    fields: dict[str, str] = {}

    # First token is the cite key
    i = 0
    while i < len(body) and body[i].isspace():
        i += 1

    # Read cite key
    j = i
    while j < len(body) and body[j] not in (",", " ", "\t", "\n"):
        j += 1
    cite_key = body[i:j].strip()
    fields["__key__"] = cite_key
    i = j

    # Skip comma after cite key
    while i < len(body) and body[i].isspace():
        i += 1
    if i < len(body) and body[i] == ",":
        i += 1

    # Parse field = value pairs
    while i < len(body):
        # Skip whitespace
        while i < len(body) and body[i].isspace():
            i += 1
        if i >= len(body):
            break

        # Read field name
        j = i
        while j < len(body) and body[j] not in ("=", "}", " ", "\t", "\n"):
            j += 1
        field_name = body[i:j].strip().lower()
        i = j

        if not field_name:
            i += 1
            continue

        # Skip to '='
        while i < len(body) and body[i] != "=":
            i += 1
        if i >= len(body):
            break
        i += 1  # skip '='

        # Skip whitespace
        while i < len(body) and body[i].isspace():
            i += 1
        if i >= len(body):
            break

        # Read value (may span braces, quotes, or bare word)
        if body[i] == "{":
            end = _find_matching_brace(body, i)
            raw_val = body[i : end + 1]
            i = end + 1
        elif body[i] == '"':
            j = i + 1
            while j < len(body):
                if body[j] == '"' and body[j - 1] != "\\":
                    break
                j += 1
            raw_val = body[i : j + 1]
            i = j + 1
        else:
            # bare word/macro – read until comma or end
            j = i
            depth = 0
            while j < len(body):
                if body[j] == "{":
                    depth += 1
                elif body[j] == "}":
                    if depth == 0:
                        break
                    depth -= 1
                elif body[j] == "," and depth == 0:
                    break
                j += 1
            raw_val = body[i:j].strip()
            i = j

        fields[field_name] = raw_val

        # Skip comma
        while i < len(body) and body[i].isspace():
            i += 1
        if i < len(body) and body[i] == ",":
            i += 1

    return fields


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_bib_file(text: str) -> dict:
    """
    Parse a .bib file.

    Returns:
        {
          "strings": {key: value, ...},
          "preambles": [...],
          "comments": [...],
          "entries": [{"__type__": ..., "__key__": ..., field: value, ...}, ...]
        }
    """
    result: dict = {
        "strings": {},
        "preambles": [],
        "comments": [],
        "entries": [],
    }

    i = 0
    text_len = len(text)

    while i < text_len:
        # Find next '@'
        at_pos = text.find("@", i)
        if at_pos == -1:
            break

        # Capture any text before '@' as comment if non-whitespace
        between = text[i:at_pos]
        if between.strip():
            result["comments"].append(("raw", between))
        i = at_pos + 1  # skip '@'

        # Read entry type name
        j = i
        while j < text_len and (text[j].isalnum() or text[j] == "_"):
            j += 1
        entry_type = text[i:j].strip()
        i = j

        # Skip whitespace
        while i < text_len and text[i].isspace():
            i += 1
        if i >= text_len:
            break

        # Determine delimiter: '{' or '('
        if text[i] == "{":
            end = _find_matching_brace(text, i)
            body = text[i + 1 : end]
            i = end + 1
        elif text[i] == "(":
            end = _find_matching_paren(text, i)
            body = text[i + 1 : end]
            i = end + 1
        else:
            # Malformed – skip
            continue

        entry_type_lower = entry_type.lower()

        if entry_type_lower == "string":
            # Parse @String{key = {value}} or @String{key = "value"}
            m = re.match(r"\s*(\w+)\s*=\s*", body)
            if m:
                key = m.group(1)
                val_start = m.end()
                val_raw = body[val_start:].strip()
                if val_raw.startswith("{") and val_raw.endswith("}"):
                    val = val_raw[1:-1]
                elif val_raw.startswith('"') and val_raw.endswith('"'):
                    val = val_raw[1:-1]
                else:
                    val = val_raw
                result["strings"][key] = {"raw": val_raw, "value": val}
        elif entry_type_lower == "preamble":
            result["preambles"].append(body.strip())
        elif entry_type_lower == "comment":
            result["comments"].append(("comment", body.strip()))
        else:
            # Regular entry
            fields = _parse_entry_body(body)
            fields["__type__"] = entry_type.lower()
            result["entries"].append(fields)

    return result


def strip_braces(value: str) -> str:
    """Remove outermost braces or quotes from a BibTeX value."""
    v = value.strip()
    if (v.startswith("{") and v.endswith("}")) or (
        v.startswith('"') and v.endswith('"')
    ):
        return v[1:-1]
    return v


def get_field(entry: dict, field: str, strings: Optional[dict] = None) -> str:
    """
    Get a field value from an entry, resolving @String macros if *strings* provided.
    Returns empty string if field not present.
    """
    raw = entry.get(field, "")
    if not raw:
        return ""
    val = strip_braces(raw)
    if strings and val in strings:
        return strings[val]["value"]
    return val


def is_macro(raw: str, strings: dict) -> Optional[str]:
    """Return the macro name if *raw* is a bare-word @String key, else None."""
    v = raw.strip()
    # A macro is a bare word (no braces or quotes) that exists in strings
    if v and not v.startswith("{") and not v.startswith('"') and v in strings:
        return v
    return None
