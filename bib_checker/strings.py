"""
Canonical @String definitions for venues and journals.

Each entry maps a canonical macro key to its abbreviated display name.
The tool will detect common variants/aliases in the bib file and replace
them with the canonical macro.

User-defined venues live in ``venues.json`` at the repository root.
That file is loaded and merged at import time, extending CANONICAL_STRINGS
and VENUE_ALIASES without touching this source file.
"""

import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Canonical string definitions that will be emitted in the fixed bib file.
# Key   -> short display name (what goes in the bib)
# ---------------------------------------------------------------------------

CANONICAL_STRINGS: dict[str, str] = {
    # --- Computer Vision Conferences ---
    "CVPR": "CVPR",
    "ICCV": "ICCV",
    "ECCV": "ECCV",
    "CVPRW": "CVPRW",
    "WACV": "WACV",
    # --- ML / AI Conferences ---
    "NIPS": "NeurIPS",
    "ICML": "ICML",
    "ICLR": "ICLR",
    "AAAI": "AAAI",
    "IJCAI": "IJCAI",
    "AISTATS": "AISTATS",
    # --- Graphics ---
    "SIGGRAPH": "ACM SIGGRAPH",
    "SIGGRAPHASIA": "ACM SIGGRAPH Asia",
    "EGSR": "EGSR",
    "EUROGRAPHICS": "Eurographics",
    "TOG": "ACM TOG",
    "CGF": "Comput. Graph. Forum",
    # --- Vision/Multimedia Journals ---
    "PAMI": "IEEE TPAMI",
    "IJCV": "IJCV",
    "TIP": "IEEE TIP",
    "TVCG": "IEEE TVCG",
    "TMM": "IEEE TMM",
    "TCSVT": "IEEE TCSVT",
    "SPL": "IEEE Sign. Process. Letters",
    "PR": "Pattern Recognit.",
    # --- Multimedia Conferences ---
    "ACMMM": "ACM MM",
    "ICME": "ICME",
    "ICASSP": "ICASSP",
    "ICIP": "ICIP",
    "ACCV": "ACCV",
    "BMVC": "BMVC",
    "ICPR": "ICPR",
    "TDV": "3DV",
    # --- Other ---
    "ARXIV": "arXiv",
}

# ---------------------------------------------------------------------------
# Alias table: maps known spelling/case variants -> canonical key above.
# Values that are *already* in CANONICAL_STRINGS are covered automatically.
# ---------------------------------------------------------------------------

VENUE_ALIASES: dict[str, str] = {
    # CVPR
    "ieee conf. comput. vis. pattern recog.": "CVPR",
    "ieee conference on computer vision and pattern recognition": "CVPR",
    "proceedings of the ieee/cvf conference on computer vision and pattern recognition": "CVPR",
    "computer vision and pattern recognition": "CVPR",
    # ICCV
    "int. conf. comput. vis.": "ICCV",
    "international conference on computer vision": "ICCV",
    "proceedings of the ieee/cvf international conference on computer vision": "ICCV",
    # ECCV
    "eur. conf. comput. vis.": "ECCV",
    "european conference on computer vision": "ECCV",
    "proceedings of the european conference on computer vision": "ECCV",
    # NeurIPS / NIPS
    "adv. neural inform. process. syst.": "NIPS",
    "advances in neural information processing systems": "NIPS",
    "neural information processing systems": "NIPS",
    "neurips": "NIPS",
    "nips": "NIPS",
    # ICML
    "international conference on machine learning": "ICML",
    "proc. int. conf. mach. learn.": "ICML",
    # ICLR
    "international conference on learning representations": "ICLR",
    "int. conf. learn. represent.": "ICLR",
    # AAAI
    "aaai conference on artificial intelligence": "AAAI",
    "proceedings of the aaai conference on artificial intelligence": "AAAI",
    # IJCAI
    "international joint conference on artificial intelligence": "IJCAI",
    # PAMI
    "ieee trans. pattern anal. mach. intell.": "PAMI",
    "ieee transactions on pattern analysis and machine intelligence": "PAMI",
    "ieee tpami": "PAMI",
    # IJCV
    "int. j. comput. vis.": "IJCV",
    "international journal of computer vision": "IJCV",
    # TOG / SIGGRAPH
    "acm transactions on graphics": "TOG",
    "acm transactions on graphics (siggraph)": "SIGGRAPH",
    "acm transactions on graphics (siggraph asia)": "SIGGRAPHASIA",
    "acm trans. graph.": "TOG",
    "acm tog": "TOG",
    # Eurographics
    "eurographics symposium on rendering": "EGSR",
    "conference of the european association for computer graphics eurographics": "EUROGRAPHICS",
    "european association for computer graphics": "EUROGRAPHICS",
    # TIP
    "ieee trans. image process.": "TIP",
    "ieee transactions on image processing": "TIP",
    "ieee tip": "TIP",
    # TVCG
    "ieee trans. vis. comput. graph.": "TVCG",
    "ieee transactions on visualization and computer graphics": "TVCG",
    "ieee tvcg": "TVCG",
    # TMM
    "ieee trans. multimedia": "TMM",
    "ieee transactions on multimedia": "TMM",
    "ieee tmm": "TMM",
    # TCSVT / CSVT
    "ieee trans. circuit syst. video technol.": "TCSVT",
    "ieee transactions on circuits and systems for video technology": "TCSVT",
    "ieee tcsvt": "TCSVT",
    # CGF
    "computer graphics forum": "CGF",
    "comput. graph. forum": "CGF",
    # ACM MM
    "acm int. conf. multimedia": "ACMMM",
    "acm international conference on multimedia": "ACMMM",
    "acm mm": "ACMMM",
    # WACV
    "proceedings of the ieee/cvf winter conference on applications of computer vision": "WACV",
    "ieee/cvf winter conference on applications of computer vision": "WACV",
    "winter conference on applications of computer vision": "WACV",
    # arXiv
    "arxiv": "ARXIV",
    "arxiv preprint": "ARXIV",
    # Pattern Recognition
    "pattern recognition": "PR",
    # BMVC
    "british machine vision conference": "BMVC",
    "brit. mach. vis. conf.": "BMVC",
    # 3DV
    "international conference on 3d vision": "TDV",
    "3dv": "TDV",
    # AISTATS
    "international conference on artificial intelligence and statistics": "AISTATS",
}


def normalize_venue_key(raw: str) -> str:
    """Lower-case and collapse whitespace for alias matching."""
    return " ".join(raw.lower().split())


def lookup_venue(raw_venue: str) -> tuple[str | None, str | None]:
    """
    Try to match *raw_venue* to a canonical @String key.

    Returns (canonical_key, display_name) or (None, None) if no match.
    Checks both the built-in tables and user-defined entries from venues.json.
    """
    norm = normalize_venue_key(raw_venue)

    # Direct match against canonical keys (case-insensitive)
    upper = raw_venue.strip().upper()
    if upper in CANONICAL_STRINGS:
        return upper, CANONICAL_STRINGS[upper]

    # Alias match
    if norm in VENUE_ALIASES:
        key = VENUE_ALIASES[norm]
        return key, CANONICAL_STRINGS[key]

    return None, None


# ---------------------------------------------------------------------------
# venues.json – user-extensible venue database
# ---------------------------------------------------------------------------

_VENUES_JSON = Path(__file__).parent.parent / "venues.json"


def _load_user_venues() -> None:
    """
    Load ``venues.json`` from the project root and merge its entries into
    CANONICAL_STRINGS and VENUE_ALIASES.  Safe to call multiple times.
    """
    if not _VENUES_JSON.is_file():
        return
    try:
        data = json.loads(_VENUES_JSON.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return

    for key, display in (data.get("strings") or {}).items():
        key = key.strip().upper()
        if key and display and key not in CANONICAL_STRINGS:
            CANONICAL_STRINGS[key] = display

    for raw, target in (data.get("aliases") or {}).items():
        norm = normalize_venue_key(raw)
        target = target.strip().upper()
        if norm and target and norm not in VENUE_ALIASES:
            VENUE_ALIASES[norm] = target


def save_user_venue(raw: str, canonical_key: str, display: str) -> None:
    """
    Persist a new (raw_venue → canonical_key, display) mapping to venues.json.

    If the key or alias already exists it is silently skipped.
    Thread-safety: fine for a single-process CLI tool.
    """
    canonical_key = canonical_key.strip().upper()
    norm = normalize_venue_key(raw)

    # Read current content (or start fresh)
    if _VENUES_JSON.is_file():
        try:
            data = json.loads(_VENUES_JSON.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        data = {}

    changed = False

    strings_map: dict[str, str] = data.get("strings") or {}
    if canonical_key not in strings_map:
        strings_map[canonical_key] = display
        changed = True

    aliases_map: dict[str, str] = data.get("aliases") or {}
    if norm not in aliases_map:
        aliases_map[norm] = canonical_key
        changed = True

    if not changed:
        return

    data["strings"] = dict(sorted(strings_map.items()))
    data["aliases"] = dict(sorted(aliases_map.items()))
    # Preserve the comment/format keys if present
    ordered: dict = {}
    for k in ("_comment", "_format"):
        if k in data:
            ordered[k] = data[k]
    ordered.update({k: v for k, v in data.items() if not k.startswith("_")})

    _VENUES_JSON.write_text(
        json.dumps(ordered, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # Also update in-memory tables so the rest of the current run benefits
    CANONICAL_STRINGS.setdefault(canonical_key, display)
    VENUE_ALIASES.setdefault(norm, canonical_key)


# Merge user venues at import time so every module benefits immediately.
_load_user_venues()
