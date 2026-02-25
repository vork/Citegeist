"""
Core checking logic: runs all checks on parsed entries and produces
fixed entries + a list of issues.
"""

import re
import unicodedata
from typing import Optional

from .datatypes import Issue, IssueLevel, IssueType, Paper
from .parser import get_field, is_macro, strip_braces
from .strings import CANONICAL_STRINGS, lookup_venue, normalize_venue_key, save_user_venue
from .search import PublicationLookup, _title_similarity


# ---------------------------------------------------------------------------
# Required / recommended fields per entry type
# ---------------------------------------------------------------------------

REQUIRED_FIELDS: dict[str, list[str]] = {
    "article":        ["author", "title", "journal", "year"],
    "inproceedings":  ["author", "title", "booktitle", "year"],
    "proceedings":    ["title", "year"],
    "book":           ["author", "title", "publisher", "year"],
    "incollection":   ["author", "title", "booktitle", "publisher", "year"],
    "phdthesis":      ["author", "title", "school", "year"],
    "mastersthesis":  ["author", "title", "school", "year"],
    "techreport":     ["author", "title", "institution", "year"],
    "misc":           ["author", "title", "year"],
    "unpublished":    ["author", "title"],
}

VENUE_FIELDS = {"journal", "booktitle"}

# arXiv entry detection patterns
ARXIV_ID_RE = re.compile(r"(\d{4}\.\d{4,5})(v\d+)?")
ARXIV_URL_RE = re.compile(r"arxiv\.org", re.IGNORECASE)
ARXIV_JOURNAL_RE = re.compile(r"arxiv", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _raw_to_display(raw: str, strings: dict) -> str:
    """Resolve a raw field value to its display string."""
    v = raw.strip()
    # bare macro
    if v in strings:
        return strings[v]["value"]
    # braced or quoted
    return strip_braces(v)


def _is_arxiv_entry(entry: dict, strings: dict) -> Optional[str]:
    """
    Return the arXiv ID if this entry is (or appears to be) an arXiv preprint,
    else None.
    """
    # Check journal/booktitle for 'arxiv'
    for vf in VENUE_FIELDS:
        raw = entry.get(vf, "")
        if raw:
            display = _raw_to_display(raw, strings)
            if ARXIV_JOURNAL_RE.search(display):
                # Try to get eprint
                eprint = strip_braces(entry.get("eprint", ""))
                if eprint:
                    return eprint
                # Try from URL
                url = strip_braces(entry.get("url", ""))
                m = ARXIV_ID_RE.search(url)
                if m:
                    return m.group(1)
                return "unknown"

    # Check URL field
    url = strip_braces(entry.get("url", ""))
    if ARXIV_URL_RE.search(url):
        m = ARXIV_ID_RE.search(url)
        return m.group(1) if m else "unknown"

    # Check eprint + archiveprefix
    eprint = strip_braces(entry.get("eprint", ""))
    archive = strip_braces(entry.get("archiveprefix", "")).lower()
    if eprint and (archive == "arxiv" or ARXIV_ID_RE.match(eprint)):
        return eprint

    # publisher = arxiv (some entries use this)
    pub = _raw_to_display(entry.get("publisher", ""), strings)
    if ARXIV_JOURNAL_RE.search(pub):
        eprint = strip_braces(entry.get("eprint", ""))
        return eprint if eprint else "unknown"

    return None


def _build_arxiv_entry(original: dict, found: Paper, strings: dict) -> dict:
    """Build an upgraded @article / @inproceedings from a published Paper."""
    updated = dict(original)

    if found.doi:
        updated["doi"] = f"{{{found.doi}}}"

    # Determine venue field and entry type
    venue = found.venue or ""
    canonical_key, display = lookup_venue(venue)

    if canonical_key:
        # Use macro
        entry_type = "inproceedings" if _is_conference_venue(canonical_key) else "article"
        venue_field = "booktitle" if entry_type == "inproceedings" else "journal"
        # Remove old venue fields
        updated.pop("journal", None)
        updated.pop("booktitle", None)
        updated[venue_field] = canonical_key  # bare macro
        updated["__type__"] = entry_type
    elif venue:
        # Keep venue as a string literal
        entry_type = "article"
        updated.pop("journal", None)
        updated.pop("booktitle", None)
        updated["journal"] = f"{{{venue}}}"
        updated["__type__"] = entry_type

    # Remove arXiv-specific fields
    for f in ("eprint", "archiveprefix", "primaryclass"):
        updated.pop(f, None)

    # Update year if we have a better one
    if found.year and not updated.get("year"):
        updated["year"] = f"{{{found.year}}}"

    return updated


def _suggest_venue_key(display: str) -> str:
    """
    Derive a short uppercase key from a venue display name.

    Strategy: take the first letter of each significant word (skip common
    stop-words).  Result is upper-cased and up to 10 chars.

    Examples:
        "Journal of Machine Learning Research" → "JMLR"
        "Transactions on Robotics"             → "TR"
        "Nature Machine Intelligence"          → "NMI"
    """
    STOP = {"of", "on", "in", "the", "a", "an", "and", "for", "to",
            "at", "with", "by", "from", "is", "its", "proceedings", "annual",
            "conference", "international", "workshop", "symposium"}
    # Strip LaTeX artifacts and punctuation
    clean = re.sub(r"[^A-Za-z0-9 ]", " ", display)
    words = clean.split()
    letters = [w[0].upper() for w in words if w.lower() not in STOP and w]
    key = "".join(letters)[:10]
    return key or "UNKNOWN"


def _is_conference_venue(key: str) -> bool:
    """Heuristic: is this canonical key a conference (vs journal)?"""
    JOURNAL_KEYS = {"PAMI", "IJCV", "TIP", "TVCG", "TMM", "TCSVT", "TOG",
                    "CGF", "SPL", "PR", "SIGGRAPH", "SIGGRAPHASIA", "ARXIV"}
    return key not in JOURNAL_KEYS


# ---------------------------------------------------------------------------
# Author-name normalization
# ---------------------------------------------------------------------------

# Name particles that should stay with the family name
_PARTICLES = {"von", "van", "de", "del", "della", "di", "du", "le", "la",
              "dos", "das", "der", "den"}


def _normalize_single_author(name: str) -> str:
    """
    Normalize one author name to "Last, First" format.

    Rules:
    - Already has a comma → assumed to be "Last, First [Middle]"; returned as-is.
    - Single word → return as-is (organisation or single-name author).
    - "First [Middle] Last" → "Last, First [Middle]"
    - Handles leading particles: "John von Neumann" → "von Neumann, John"
    """
    name = name.strip()
    if not name:
        return name
    # Already in "Last, First" form
    if "," in name:
        return name
    parts = name.split()
    if len(parts) == 1:
        return name  # single token – can't determine order
    # Find where the last-name part starts (handle particles)
    # The family name is the last token(s); particles attach to it.
    # Walk backwards to collect the family name block.
    family_parts = [parts[-1]]
    i = len(parts) - 2
    while i >= 0 and parts[i].lower() in _PARTICLES:
        family_parts.insert(0, parts[i])
        i -= 1
    given_parts = parts[:i + 1]
    family = " ".join(family_parts)
    given = " ".join(given_parts)
    if not given:
        return family  # only particles + last name, e.g. "von Neumann"
    return f"{family}, {given}"


def _normalize_author_field(raw: str) -> tuple[str, bool]:
    """
    Parse a BibTeX author field string and normalize each name to "Last, First".

    Returns (normalized_string, changed) where changed=True if any name was
    actually rewritten.
    """
    # Strip outer braces/quotes
    inner = strip_braces(raw)
    # Split on " and " (case-insensitive)
    names = re.split(r"\s+and\s+", inner, flags=re.IGNORECASE)
    normalized = []
    changed = False
    for name in names:
        fixed = _normalize_single_author(name.strip())
        if fixed != name.strip():
            changed = True
        normalized.append(fixed)
    return " and ".join(normalized), changed


# ---------------------------------------------------------------------------
# Main checker class
# ---------------------------------------------------------------------------

class BibChecker:
    def __init__(self, lookup: Optional[PublicationLookup] = None,
                 skip_network: bool = False,
                 verbose: bool = False,
                 learn_venues: bool = True):
        self.lookup = lookup or PublicationLookup(verbose=verbose)
        self.skip_network = skip_network
        self.verbose = verbose
        self.learn_venues = learn_venues  # save new venues to venues.json

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg)

    # ------------------------------------------------------------------
    # Check: author field formatting
    # ------------------------------------------------------------------

    def _check_authors(self, entry: dict, strings: dict) -> tuple[dict, list[Issue]]:
        """
        Normalize author names to 'Last, First' format.

        BibTeX convention is 'Last, First' or 'Last, First and Last2, First2'.
        If any name looks like 'First Last' (no comma), convert it.
        """
        issues = []
        updated = dict(entry)
        key = entry.get("__key__", "?")
        raw = entry.get("author", "")
        if not raw.strip():
            return updated, issues

        normalized, changed = _normalize_author_field(raw)
        if changed:
            # Re-wrap in braces (strip outer delimiters first, then re-wrap)
            updated["author"] = f"{{{normalized}}}"
            issues.append(Issue(
                key=key,
                level=IssueLevel.INFO,
                issue_type=IssueType.FIELD_NORMALIZED,
                message="Normalized author name(s) to 'Last, First' format",
                old_value=strip_braces(raw),
                new_value=normalized,
            ))
        return updated, issues

    # ------------------------------------------------------------------
    # Check: missing required fields
    # ------------------------------------------------------------------

    def _check_required_fields(self, entry: dict, strings: dict) -> list[Issue]:
        issues = []
        etype = entry.get("__type__", "misc")
        key = entry.get("__key__", "?")
        required = REQUIRED_FIELDS.get(etype, [])
        for field in required:
            if not entry.get(field, "").strip():
                issues.append(Issue(
                    key=key,
                    level=IssueLevel.WARNING,
                    issue_type=IssueType.MISSING_FIELD,
                    message=f"Missing required field '{field}' for @{etype}",
                ))
        return issues

    # ------------------------------------------------------------------
    # Check: venue standardization
    # ------------------------------------------------------------------

    def _check_venue(self, entry: dict, strings: dict) -> tuple[dict, list[Issue]]:
        issues = []
        updated = dict(entry)
        key = entry.get("__key__", "?")
        etype = entry.get("__type__", "misc")

        for vf in VENUE_FIELDS:
            raw = entry.get(vf, "")
            if not raw:
                continue

            raw_stripped = raw.strip()

            # If it's already a macro that's in our canonical set → fine
            if raw_stripped in CANONICAL_STRINGS:
                continue
            # If it's a macro in the file's own strings
            if raw_stripped in strings:
                display_val = strings[raw_stripped]["value"]
                # Try to remap to our canonical key
                canonical_key, _ = lookup_venue(display_val)
                if canonical_key and canonical_key != raw_stripped:
                    updated[vf] = canonical_key
                    issues.append(Issue(
                        key=key,
                        level=IssueLevel.INFO,
                        issue_type=IssueType.VENUE_STANDARDIZED,
                        message=f"Remapped @String macro '{raw_stripped}' → '{canonical_key}' in '{vf}'",
                        old_value=raw_stripped,
                        new_value=canonical_key,
                    ))
                continue

            # It's a literal string – try to match
            display_val = strip_braces(raw_stripped)
            canonical_key, canonical_display = lookup_venue(display_val)
            if canonical_key:
                updated[vf] = canonical_key  # store as bare macro name
                issues.append(Issue(
                    key=key,
                    level=IssueLevel.INFO,
                    issue_type=IssueType.VENUE_STANDARDIZED,
                    message=(
                        f"Standardized '{vf}': '{display_val}' → @String macro '{canonical_key}'"
                    ),
                    old_value=display_val,
                    new_value=canonical_key,
                ))
            else:
                # Unknown venue: flag it, and optionally learn it
                norm = normalize_venue_key(display_val)
                # Only warn for non-trivial venue strings
                if len(norm) > 4:
                    suggested_key = _suggest_venue_key(display_val)
                    if self.learn_venues and display_val:
                        save_user_venue(display_val, suggested_key, display_val)
                        issues.append(Issue(
                            key=key,
                            level=IssueLevel.INFO,
                            issue_type=IssueType.SUSPICIOUS_VENUE,
                            message=(
                                f"Unrecognized venue in '{vf}': '{display_val}'. "
                                f"Suggested macro '{suggested_key}' saved to venues.json – "
                                "please review and edit the display name there."
                            ),
                            old_value=display_val,
                            new_value=suggested_key,
                        ))
                    else:
                        issues.append(Issue(
                            key=key,
                            level=IssueLevel.WARNING,
                            issue_type=IssueType.SUSPICIOUS_VENUE,
                            message=(
                                f"Unrecognized venue in '{vf}': '{display_val}'. "
                                "Consider adding a @String macro."
                            ),
                            old_value=display_val,
                        ))

        return updated, issues

    # ------------------------------------------------------------------
    # Check: entry type correctness
    # ------------------------------------------------------------------

    def _check_entry_type(self, entry: dict, strings: dict) -> tuple[dict, list[Issue]]:
        issues = []
        updated = dict(entry)
        key = entry.get("__key__", "?")
        etype = entry.get("__type__", "misc")

        # @misc with journal= should be @article
        if etype == "misc" and entry.get("journal"):
            updated["__type__"] = "article"
            issues.append(Issue(
                key=key,
                level=IssueLevel.INFO,
                issue_type=IssueType.ENTRY_TYPE_FIXED,
                message="Changed @misc → @article (has 'journal' field)",
                old_value="misc",
                new_value="article",
            ))
        # @misc with booktitle= should be @inproceedings
        elif etype == "misc" and entry.get("booktitle"):
            updated["__type__"] = "inproceedings"
            issues.append(Issue(
                key=key,
                level=IssueLevel.INFO,
                issue_type=IssueType.ENTRY_TYPE_FIXED,
                message="Changed @misc → @inproceedings (has 'booktitle' field)",
                old_value="misc",
                new_value="inproceedings",
            ))

        return updated, issues

    # ------------------------------------------------------------------
    # Check & upgrade arXiv entries
    # ------------------------------------------------------------------

    def _check_arxiv(self, entry: dict, strings: dict) -> tuple[dict, list[Issue]]:
        issues = []
        updated = dict(entry)
        key = entry.get("__key__", "?")
        title = _raw_to_display(entry.get("title", ""), strings)

        arxiv_id = _is_arxiv_entry(entry, strings)
        if not arxiv_id:
            return updated, issues

        if self.skip_network:
            issues.append(Issue(
                key=key,
                level=IssueLevel.INFO,
                issue_type=IssueType.ARXIV_NOT_FOUND_PUBLISHED,
                message=f"arXiv preprint (ID: {arxiv_id}) – network search skipped (--offline mode)",
            ))
            return updated, issues

        self._log(f"\n[{key}] Searching for published version of arXiv:{arxiv_id}...")
        results = self.lookup.find_published(title)

        published = results.get("published_result")
        verified = results.get("verified", False)
        if published and published.doi:
            venue_str = published.venue or "(unknown venue)"
            verified_note = " [DuckDuckGo verified ✓]" if verified else ""
            new_entry = _build_arxiv_entry(updated, published, strings)

            # Fix title if the authoritative source has a better spelling
            if published.title and published.title != title:
                sim = _title_similarity(title, published.title)
                if sim >= 0.7:   # close enough – trust the remote title
                    new_entry["title"] = f"{{{published.title}}}"
                    issues.append(Issue(
                        key=key,
                        level=IssueLevel.INFO,
                        issue_type=IssueType.FIELD_NORMALIZED,
                        message="Updated title to match authoritative source",
                        old_value=title,
                        new_value=published.title,
                    ))

            # Fix authors if the remote source has a normalized list
            if published.authors:
                remote_authors = " and ".join(published.authors)
                new_entry["author"] = f"{{{remote_authors}}}"

            issues.append(Issue(
                key=key,
                level=IssueLevel.INFO,
                issue_type=IssueType.ARXIV_UPGRADED,
                message=(
                    f"Upgraded from arXiv preprint to published version: "
                    f"venue='{venue_str}', doi='{published.doi}'{verified_note}"
                ),
                old_value=f"arXiv:{arxiv_id}",
                new_value=f"doi:{published.doi}",
            ))
            return new_entry, issues
        else:
            issues.append(Issue(
                key=key,
                level=IssueLevel.WARNING,
                issue_type=IssueType.ARXIV_NOT_FOUND_PUBLISHED,
                message=(
                    f"arXiv preprint (ID: {arxiv_id}) – no published version found. "
                    "Please verify manually."
                ),
            ))
            issues.append(Issue(
                key=key,
                level=IssueLevel.WARNING,
                issue_type=IssueType.MANUAL_REVIEW,
                message="Manual review required: check if this paper has been published.",
            ))
            return updated, issues

    # ------------------------------------------------------------------
    # Duplicate key detection
    # ------------------------------------------------------------------

    def _find_duplicates(self, entries: list[dict]) -> list[Issue]:
        seen: dict[str, int] = {}
        issues = []
        for entry in entries:
            k = entry.get("__key__", "")
            if k in seen:
                issues.append(Issue(
                    key=k,
                    level=IssueLevel.ERROR,
                    issue_type=IssueType.DUPLICATE_KEY,
                    message=f"Duplicate cite key '{k}'",
                ))
            else:
                seen[k] = 1
        return issues

    # ------------------------------------------------------------------
    # Undefined @String macro detection
    # ------------------------------------------------------------------

    # Standard BibTeX month macros – always valid bare words
    _BIBTEX_MONTHS = {
        "jan", "feb", "mar", "apr", "may", "jun",
        "jul", "aug", "sep", "oct", "nov", "dec",
    }

    def _check_undefined_strings(self, entry: dict, known_strings: set[str]) -> list[Issue]:
        issues = []
        key = entry.get("__key__", "?")
        skip = {"__key__", "__type__"}
        for field, raw in entry.items():
            if field in skip:
                continue
            v = raw.strip()
            # A bare word that's not a number and not a macro we know
            if (v
                    and not v.startswith("{")
                    and not v.startswith('"')
                    and not v.lstrip("-").isdigit()
                    and v.lower() not in self._BIBTEX_MONTHS
                    and v not in known_strings
                    and v not in CANONICAL_STRINGS):
                issues.append(Issue(
                    key=key,
                    level=IssueLevel.ERROR,
                    issue_type=IssueType.UNDEFINED_STRING,
                    message=f"Field '{field}' references undefined @String macro '{v}'",
                    old_value=v,
                ))
        return issues

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def check_entries(self, parsed: dict) -> tuple[list[dict], list[Issue]]:
        """
        Run all checks on parsed bib data.

        Returns:
            (fixed_entries, all_issues)
        """
        entries = parsed["entries"]
        strings = parsed["strings"]

        # All known string macro names (file's own + our canonical set)
        known_strings = set(strings.keys()) | set(CANONICAL_STRINGS.keys())

        all_issues: list[Issue] = []
        fixed: list[dict] = []

        # Pass 1: duplicate keys (global check)
        all_issues.extend(self._find_duplicates(entries))

        for entry in entries:
            key = entry.get("__key__", "?")
            self._log(f"\nChecking [{key}]")

            current = dict(entry)
            entry_issues: list[Issue] = []

            # 1. Fix entry type first (may affect later checks)
            current, iss = self._check_entry_type(current, strings)
            entry_issues.extend(iss)

            # 2. Author field normalization (Last, First format)
            current, iss = self._check_authors(current, strings)
            entry_issues.extend(iss)

            # 3. Venue standardization
            current, iss = self._check_venue(current, strings)
            entry_issues.extend(iss)

            # 4. arXiv upgrade (most expensive – does network calls)
            current, iss = self._check_arxiv(current, strings)
            entry_issues.extend(iss)

            # 5. Required fields (after type fix)
            entry_issues.extend(self._check_required_fields(current, strings))

            # 6. Undefined @String macros
            entry_issues.extend(self._check_undefined_strings(current, known_strings))

            all_issues.extend(entry_issues)
            fixed.append(current)

        return fixed, all_issues
