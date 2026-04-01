"""
Canonical @String definitions for venues and journals.

Each entry maps a canonical macro key to its display name.
The tool will detect common variants/aliases in the bib file and replace
them with the canonical macro.

User-defined venues live in ``venues.json`` at the repository root.
That file is loaded and merged at import time, extending CANONICAL_STRINGS
and VENUE_ALIASES without touching this source file.
"""

import json
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Canonical string definitions that will be emitted in the fixed bib file.
# Key   -> display name (what goes in the bib @String definition)
# ---------------------------------------------------------------------------

CANONICAL_STRINGS: dict[str, str] = {
    # --- Computer Vision Conferences ---
    "CVPR": "Conference on Computer Vision and Pattern Recognition (CVPR)",
    "ICCV": "International Conference on Computer Vision (ICCV)",
    "ECCV": "European Conference on Computer Vision (ECCV)",
    "CVPRW": "CVPR Workshops",
    "WACV": "Winter Conference on Applications of Computer Vision (WACV)",
    "ACCV": "Asian Conference on Computer Vision (ACCV)",
    "BMVC": "British Machine Vision Conference (BMVC)",
    "TDV": "International Conference on 3D Vision (3DV)",
    "FGR": "IEEE International Conference on Automatic Face and Gesture Recognition (FG)",
    # --- ML / AI Conferences ---
    "NIPS": "Neural Information Processing Systems (NeurIPS)",
    "ICML": "International Conference on Machine Learning (ICML)",
    "ICLR": "International Conference on Learning Representations (ICLR)",
    "AAAI": "AAAI Conference on Artificial Intelligence (AAAI)",
    "IJCAI": "International Joint Conference on Artificial Intelligence (IJCAI)",
    "AISTATS": "International Conference on Artificial Intelligence and Statistics (AISTATS)",
    "UAI": "Conference on Uncertainty in Artificial Intelligence (UAI)",
    "COLT": "Conference on Learning Theory (COLT)",
    "KDD": "ACM SIGKDD Conference on Knowledge Discovery and Data Mining (KDD)",
    # --- NLP ---
    "EMNLP": "Conference on Empirical Methods in Natural Language Processing (EMNLP)",
    "ACL": "Annual Meeting of the Association for Computational Linguistics (ACL)",
    "NAACL": "North American Chapter of the Association for Computational Linguistics (NAACL)",
    "EACL": "European Chapter of the Association for Computational Linguistics (EACL)",
    "COLING": "International Conference on Computational Linguistics (COLING)",
    "TACL": "Transactions of the Association for Computational Linguistics (TACL)",
    # --- Robotics Conferences ---
    "ICRA": "IEEE International Conference on Robotics and Automation (ICRA)",
    "IROS": "IEEE/RSJ International Conference on Intelligent Robots and Systems (IROS)",
    "RSS": "Robotics: Science and Systems (RSS)",
    "CORL": "Conference on Robot Learning (CoRL)",
    "HRI": "ACM/IEEE International Conference on Human-Robot Interaction (HRI)",
    # --- Robotics Journals ---
    "TRO": "IEEE Transactions on Robotics (TRO)",
    "RAL": "IEEE Robotics and Automation Letters (RA-L)",
    "IJRR": "International Journal of Robotics Research (IJRR)",
    # --- Graphics Conferences ---
    "SIGGRAPH": "ACM SIGGRAPH",
    "SIGGRAPHASIA": "ACM SIGGRAPH Asia",
    "EGSR": "Eurographics Symposium on Rendering (EGSR)",
    "EUROGRAPHICS": "Eurographics",
    "PG": "Pacific Graphics",
    "SCA": "ACM SIGGRAPH / Eurographics Symposium on Computer Animation (SCA)",
    "SGP": "Eurographics Symposium on Geometry Processing (SGP)",
    "HPG": "High-Performance Graphics (HPG)",
    # --- Graphics / Vision Journals ---
    "TOG": "ACM Transactions on Graphics (TOG)",
    "CGF": "Computer Graphics Forum (CGF)",
    "TVCG": "IEEE Transactions on Visualization and Computer Graphics (TVCG)",
    # --- Vision/Image Processing Journals ---
    "PAMI": "IEEE Transactions on Pattern Analysis and Machine Intelligence (TPAMI)",
    "IJCV": "International Journal of Computer Vision (IJCV)",
    "TIP": "IEEE Transactions on Image Processing (TIP)",
    "TMM": "IEEE Transactions on Multimedia (TMM)",
    "TCSVT": "IEEE Transactions on Circuits and Systems for Video Technology (TCSVT)",
    "SPL": "IEEE Signal Processing Letters",
    "PR": "Pattern Recognition",
    "ICPR": "International Conference on Pattern Recognition (ICPR)",
    # --- Multimedia Conferences ---
    "ACMMM": "ACM International Conference on Multimedia (ACM MM)",
    "ICME": "IEEE International Conference on Multimedia and Expo (ICME)",
    "ICASSP": "IEEE International Conference on Acoustics, Speech and Signal Processing (ICASSP)",
    "ICIP": "IEEE International Conference on Image Processing (ICIP)",
    # --- Medical Imaging ---
    "MICCAI": "Medical Image Computing and Computer-Assisted Intervention (MICCAI)",
    "MIA": "Medical Image Analysis",
    # --- ML/AI Journals ---
    "JMLR": "Journal of Machine Learning Research (JMLR)",
    "TMLR": "Transactions on Machine Learning Research (TMLR)",
    "JAIR": "Journal of Artificial Intelligence Research (JAIR)",
    "AIJ": "Artificial Intelligence",
    "TNNLS": "IEEE Transactions on Neural Networks and Learning Systems (TNNLS)",
    # --- NLP (additional) ---
    "LREC": "International Conference on Language Resources and Evaluation (LREC)",
    # --- CS Surveys ---
    "CSUR": "ACM Computing Surveys",
    # --- General Science ---
    "NATURE": "Nature",
    "NATURECOMM": "Nature Communications",
    "NATUREMI": "Nature Machine Intelligence",
    "SCIENCE": "Science",
    "SCIENCEADV": "Science Advances",
    "SCIROBOT": "Science Robotics",
    "PNAS": "Proceedings of the National Academy of Sciences (PNAS)",
    # --- Other ---
    "ARXIV": "arXiv preprint",
}

# ---------------------------------------------------------------------------
# Alias table: maps known spelling/case variants -> canonical key above.
# Values that are *already* in CANONICAL_STRINGS are covered automatically.
# ---------------------------------------------------------------------------

VENUE_ALIASES: dict[str, str] = {
    # ── Computer Vision Conferences ──────────────────────────────────────
    # CVPR
    "ieee conf. comput. vis. pattern recog.": "CVPR",
    "ieee conference on computer vision and pattern recognition": "CVPR",
    "proceedings of the ieee/cvf conference on computer vision and pattern recognition": "CVPR",
    "computer vision and pattern recognition": "CVPR",
    "ieee/cvf conference on computer vision and pattern recognition": "CVPR",
    "conf. comput. vis. pattern recog.": "CVPR",
    # ICCV
    "int. conf. comput. vis.": "ICCV",
    "international conference on computer vision": "ICCV",
    "proceedings of the ieee/cvf international conference on computer vision": "ICCV",
    "ieee/cvf international conference on computer vision": "ICCV",
    "ieee international conference on computer vision": "ICCV",
    # ECCV
    "eur. conf. comput. vis.": "ECCV",
    "european conference on computer vision": "ECCV",
    "proceedings of the european conference on computer vision": "ECCV",
    # WACV
    "proceedings of the ieee/cvf winter conference on applications of computer vision": "WACV",
    "ieee/cvf winter conference on applications of computer vision": "WACV",
    "winter conference on applications of computer vision": "WACV",
    # ACCV
    "asian conference on computer vision": "ACCV",
    # BMVC
    "british machine vision conference": "BMVC",
    "brit. mach. vis. conf.": "BMVC",
    # 3DV
    "international conference on 3d vision": "TDV",
    "3dv": "TDV",
    # FG / FGR
    "ieee international conference on automatic face and gesture recognition": "FGR",
    "ieee conference on automatic face and gesture recognition": "FGR",

    # ── ML / AI Conferences ──────────────────────────────────────────────
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
    # AISTATS
    "international conference on artificial intelligence and statistics": "AISTATS",
    # UAI
    "uncertainty in artificial intelligence": "UAI",
    "conference on uncertainty in artificial intelligence": "UAI",
    # COLT
    "conference on learning theory": "COLT",
    # KDD
    "acm sigkdd conference on knowledge discovery and data mining": "KDD",
    "knowledge discovery and data mining": "KDD",
    "kdd": "KDD",

    # ── NLP ───────────────────────────────────────────────────────────────
    # EMNLP
    "conference on empirical methods in natural language processing": "EMNLP",
    "empirical methods in natural language processing": "EMNLP",
    "emnlp": "EMNLP",
    # ACL
    "annual meeting of the association for computational linguistics": "ACL",
    "association for computational linguistics": "ACL",
    # NAACL
    "north american chapter of the association for computational linguistics": "NAACL",
    "naacl": "NAACL",
    # EACL
    "european chapter of the association for computational linguistics": "EACL",
    "eacl": "EACL",
    # COLING
    "international conference on computational linguistics": "COLING",
    "coling": "COLING",
    # TACL
    "transactions of the association for computational linguistics": "TACL",
    "tacl": "TACL",

    # ── Robotics Conferences ─────────────────────────────────────────────
    # ICRA
    "ieee international conference on robotics and automation": "ICRA",
    "icra": "ICRA",
    # IROS
    "ieee/rsj international conference on intelligent robots and systems": "IROS",
    "international conference on intelligent robots and systems": "IROS",
    "iros": "IROS",
    # RSS
    "robotics: science and systems": "RSS",
    "robotics science and systems": "RSS",
    "rss": "RSS",
    # CoRL
    "conference on robot learning": "CORL",
    "corl": "CORL",
    # HRI
    "acm/ieee international conference on human-robot interaction": "HRI",
    "international conference on human-robot interaction": "HRI",
    "human-robot interaction": "HRI",
    "hri": "HRI",

    # ── Robotics Journals ────────────────────────────────────────────────
    # TRO
    "ieee transactions on robotics": "TRO",
    "ieee trans. robot.": "TRO",
    "ieee tro": "TRO",
    # RA-L
    "ieee robotics and automation letters": "RAL",
    "ieee robot. autom. lett.": "RAL",
    "ra-l": "RAL",
    "ral": "RAL",
    # IJRR
    "international journal of robotics research": "IJRR",
    "int. j. robot. res.": "IJRR",
    "ijrr": "IJRR",

    # ── Graphics Conferences ─────────────────────────────────────────────
    # SIGGRAPH
    "acm siggraph conference": "SIGGRAPH",
    "siggraph": "SIGGRAPH",
    # SIGGRAPH Asia
    "siggraph asia": "SIGGRAPHASIA",
    "acm siggraph asia": "SIGGRAPHASIA",
    "siggraph asia conference": "SIGGRAPHASIA",
    "acm siggraph conference and exhibition on computer graphics and interactive techniques in asia": "SIGGRAPHASIA",
    # Eurographics
    "eurographics symposium on rendering": "EGSR",
    "conference of the european association for computer graphics eurographics": "EUROGRAPHICS",
    "european association for computer graphics": "EUROGRAPHICS",
    # Pacific Graphics
    "pacific graphics": "PG",
    "pacific conference on computer graphics and applications": "PG",
    # SCA
    "symposium on computer animation": "SCA",
    "acm siggraph/eurographics symposium on computer animation": "SCA",
    # SGP
    "symposium on geometry processing": "SGP",
    "eurographics symposium on geometry processing": "SGP",
    # HPG
    "high-performance graphics": "HPG",
    "high performance graphics": "HPG",

    # ── Graphics / Vision Journals ───────────────────────────────────────
    # TOG / SIGGRAPH
    "acm transactions on graphics": "TOG",
    "acm transactions on graphics (siggraph)": "SIGGRAPH",
    "acm transactions on graphics (siggraph asia)": "SIGGRAPHASIA",
    "acm trans. graph.": "TOG",
    "acm tog": "TOG",
    # CGF
    "computer graphics forum": "CGF",
    "comput. graph. forum": "CGF",
    # TVCG
    "ieee trans. vis. comput. graph.": "TVCG",
    "ieee transactions on visualization and computer graphics": "TVCG",
    "ieee tvcg": "TVCG",

    # ── Vision / Image Processing Journals ───────────────────────────────
    # PAMI
    "ieee trans. pattern anal. mach. intell.": "PAMI",
    "ieee transactions on pattern analysis and machine intelligence": "PAMI",
    "ieee tpami": "PAMI",
    "tpami": "PAMI",
    # IJCV
    "int. j. comput. vis.": "IJCV",
    "international journal of computer vision": "IJCV",
    # TIP
    "ieee trans. image process.": "TIP",
    "ieee transactions on image processing": "TIP",
    "ieee tip": "TIP",
    # TMM
    "ieee trans. multimedia": "TMM",
    "ieee transactions on multimedia": "TMM",
    "ieee tmm": "TMM",
    # TCSVT
    "ieee trans. circuit syst. video technol.": "TCSVT",
    "ieee transactions on circuits and systems for video technology": "TCSVT",
    "ieee tcsvt": "TCSVT",
    # Pattern Recognition
    "pattern recognition": "PR",

    # ── Multimedia Conferences ───────────────────────────────────────────
    # ACM MM
    "acm int. conf. multimedia": "ACMMM",
    "acm international conference on multimedia": "ACMMM",
    "acm mm": "ACMMM",
    # ICME
    "ieee international conference on multimedia and expo": "ICME",
    # ICASSP
    "ieee international conference on acoustics, speech and signal processing": "ICASSP",
    "ieee int. conf. acoust. speech signal process.": "ICASSP",
    # ICIP
    "ieee international conference on image processing": "ICIP",
    # ICPR
    "international conference on pattern recognition": "ICPR",

    # ── Medical Imaging ──────────────────────────────────────────────────
    "medical image computing and computer-assisted intervention": "MICCAI",
    "medical image computing and computer assisted intervention": "MICCAI",
    "miccai": "MICCAI",
    # MIA
    "medical image analysis": "MIA",
    "med. image anal.": "MIA",

    # ── ML/AI Journals ───────────────────────────────────────────────────
    # JMLR
    "journal of machine learning research": "JMLR",
    "jmlr": "JMLR",
    # TMLR
    "transactions on machine learning research": "TMLR",
    "tmlr": "TMLR",
    # JAIR
    "journal of artificial intelligence research": "JAIR",
    "jair": "JAIR",
    # AIJ
    "artificial intelligence": "AIJ",
    # TNNLS
    "ieee transactions on neural networks and learning systems": "TNNLS",
    "ieee trans. neural netw. learn. syst.": "TNNLS",
    "tnnls": "TNNLS",

    # ── NLP (additional) ─────────────────────────────────────────────────
    # LREC
    "international conference on language resources and evaluation": "LREC",
    "language resources and evaluation conference": "LREC",
    "lrec": "LREC",

    # ── CS Surveys ───────────────────────────────────────────────────────
    "acm computing surveys": "CSUR",
    "acm comput. surv.": "CSUR",
    "csur": "CSUR",

    # ── General Science ──────────────────────────────────────────────────
    "nature": "NATURE",
    "nature communications": "NATURECOMM",
    "nat. commun.": "NATURECOMM",
    "nature machine intelligence": "NATUREMI",
    "nat. mach. intell.": "NATUREMI",
    "science": "SCIENCE",
    "science advances": "SCIENCEADV",
    "sci. adv.": "SCIENCEADV",
    "science robotics": "SCIROBOT",
    "sci. robot.": "SCIROBOT",
    "proceedings of the national academy of sciences": "PNAS",
    "proc. natl. acad. sci.": "PNAS",
    "pnas": "PNAS",

    # ── arXiv ────────────────────────────────────────────────────────────
    "arxiv": "ARXIV",
    "arxiv preprint": "ARXIV",
}


# ---------------------------------------------------------------------------
# Reverse map: parenthesized abbreviations in display names → canonical key.
# E.g. "neurips" → "NIPS", "tpami" → "PAMI", "3dv" → "TDV"
# ---------------------------------------------------------------------------

_ABBREV_TO_KEY: dict[str, str] = {}


def _build_abbrev_map() -> None:
    """Build reverse map from parenthesized abbreviations in display names."""
    _ABBREV_TO_KEY.clear()
    for key, display in CANONICAL_STRINGS.items():
        m = re.search(r'\(([^)]+)\)\s*$', display)
        if m:
            _ABBREV_TO_KEY[m.group(1).strip().lower()] = key
        _ABBREV_TO_KEY[key.lower()] = key


def normalize_venue_key(raw: str) -> str:
    """Lower-case, strip outer LaTeX braces, and collapse whitespace for alias matching."""
    s = raw.strip()
    while s.startswith("{") and s.endswith("}"):
        s = s[1:-1]
    return " ".join(s.lower().split())


def _clean_venue_name(norm: str) -> str:
    """Strip common prefixes, suffixes, and year numbers from a normalized venue name.

    Applies stripping rules iteratively until no more changes occur, so that
    rules like year removal and suffix removal work regardless of order.
    """
    s = norm
    _RULES = [
        (r'^proceedings\s+of\s+(the\s+)?', ''),
        (r'^(ieee/cvf|ieee/rsj|ieee|acm)\s+', ''),
        (r'\s*\([^)]+\)\s*$', ''),
        # Trailing generic descriptors
        (r'\s+(conference\s+papers|technical\s+papers|conference\s+proceedings'
         r'|full\s+papers|paper\s+presentations)\s*$', ''),
        # Year at start / end (must come after suffix stripping)
        (r'^\d{4}\s+', ''),
        (r'\s+\d{4}$', ''),
    ]
    prev = None
    while s != prev:
        prev = s
        for pattern, repl in _RULES:
            s = re.sub(pattern, repl, s).strip()
    return s


def lookup_venue(raw_venue: str) -> tuple[str | None, str | None]:
    """
    Try to match *raw_venue* to a canonical @String key.

    Returns (canonical_key, display_name) or (None, None) if no match.
    Checks both the built-in tables and user-defined entries from venues.json.

    Matching strategy (in order):
    1. Direct canonical key match (case-insensitive)
    2. arXiv special case (anything starting with "arxiv")
    3. Exact alias match
    4. Parenthesized abbreviation extraction: "... (CVPR)" → CVPR
    5. Prefix/suffix stripping (Proceedings of, IEEE/CVF, year, etc.)
    6. Year stripping from key-like names: "CVPR 2026" → CVPR
    """
    norm = normalize_venue_key(raw_venue)
    if not norm:
        return None, None

    # 1. Direct match against canonical keys (case-insensitive)
    upper = raw_venue.strip().upper()
    if upper in CANONICAL_STRINGS:
        return upper, CANONICAL_STRINGS[upper]

    # 2. arXiv special case: anything starting with "arxiv"
    if re.match(r'arxiv\b', norm):
        return "ARXIV", CANONICAL_STRINGS["ARXIV"]

    # 3. Exact alias match
    if norm in VENUE_ALIASES:
        key = VENUE_ALIASES[norm]
        return key, CANONICAL_STRINGS[key]

    # 4. Extract parenthesized abbreviation: "... (CVPR)" → try CVPR
    m = re.search(r'\(([^)]+)\)\s*$', norm)
    if m:
        abbrev = m.group(1).strip().lower()
        if abbrev in _ABBREV_TO_KEY:
            key = _ABBREV_TO_KEY[abbrev]
            return key, CANONICAL_STRINGS[key]

    # 5. Strip common prefixes/suffixes and retry
    cleaned = _clean_venue_name(norm)
    if cleaned and cleaned != norm:
        cleaned_upper = cleaned.upper()
        if cleaned_upper in CANONICAL_STRINGS:
            return cleaned_upper, CANONICAL_STRINGS[cleaned_upper]
        if cleaned in VENUE_ALIASES:
            key = VENUE_ALIASES[cleaned]
            return key, CANONICAL_STRINGS[key]
        # Try without spaces for concatenated keys (e.g. "siggraph asia" → "SIGGRAPHASIA")
        nospace = cleaned_upper.replace(" ", "")
        if nospace in CANONICAL_STRINGS:
            return nospace, CANONICAL_STRINGS[nospace]

    # 6. Strip year from key-like names: "cvpr 2026" → "CVPR"
    year_stripped = re.sub(r'\b\d{4}\b', '', norm).strip()
    year_stripped = " ".join(year_stripped.split())
    if year_stripped and year_stripped != norm:
        year_upper = year_stripped.upper()
        if year_upper in CANONICAL_STRINGS:
            return year_upper, CANONICAL_STRINGS[year_upper]
        if year_stripped in VENUE_ALIASES:
            key = VENUE_ALIASES[year_stripped]
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


def is_plausible_venue(raw: str) -> bool:
    """
    Return True if *raw* looks like a real venue name rather than a broken
    macro, typo, or random identifier.

    Rejects strings like "APA21", "N", "C", "2ICCVPRC" that are obviously
    not venue names.  A plausible venue is either:
    - A multi-word string (contains spaces), or
    - A known abbreviation already in our tables (handled before this is called), or
    - A single word that is long enough and all-alphabetic (e.g. "Neurocomputing").
    """
    s = raw.strip()
    if not s:
        return False
    # Multi-word strings are generally plausible
    if " " in s:
        return True
    # Single-word: reject if it contains digits (looks like a broken macro)
    if any(c.isdigit() for c in s):
        return False
    # Single-word: reject if very short (< 6 chars) — real single-word
    # venues like "Nature" or "Science" are already in our canonical tables
    if len(s) < 6:
        return False
    return True


def _suggest_venue_key(display: str) -> str:
    """
    Derive a short uppercase key from a venue display name.

    First checks for a parenthesized abbreviation like "(CVPR)" at the end.
    Falls back to taking the first letter of each significant word.
    """
    m = re.search(r'\(([^)]+)\)\s*$', display)
    if m:
        abbrev = m.group(1).strip().upper().replace(" ", "")
        if abbrev.isalnum() and len(abbrev) <= 10:
            return abbrev

    STOP = {"of", "on", "in", "the", "a", "an", "and", "for", "to",
            "at", "with", "by", "from", "is", "its", "proceedings", "annual",
            "conference", "international", "workshop", "symposium"}
    clean = re.sub(r"[^A-Za-z0-9 ]", " ", display)
    words = clean.split()
    letters = [w[0].upper() for w in words if w.lower() not in STOP and w]
    key = "".join(letters)[:10]
    return key or "UNKNOWN"


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
_build_abbrev_map()
