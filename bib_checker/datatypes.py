"""Core data types for the BibTeX checker."""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class IssueLevel(Enum):
    INFO = auto()
    WARNING = auto()
    ERROR = auto()


class IssueType(Enum):
    VENUE_STANDARDIZED = auto()
    ARXIV_UPGRADED = auto()
    ARXIV_NOT_FOUND_PUBLISHED = auto()
    ENTRY_TYPE_FIXED = auto()
    FIELD_NORMALIZED = auto()
    MISSING_FIELD = auto()
    SUSPICIOUS_VENUE = auto()
    DUPLICATE_KEY = auto()
    UNDEFINED_STRING = auto()
    MANUAL_REVIEW = auto()


@dataclass
class Issue:
    key: str          # BibTeX entry key
    level: IssueLevel
    issue_type: IssueType
    message: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None


@dataclass
class Paper:
    title: str
    authors: list[str]
    url: Optional[str] = None
    pdf_url: Optional[str] = None
    summary: Optional[str] = None
    date: Optional[str] = None
    doi: Optional[str] = None
    venue: Optional[str] = None
    year: Optional[int] = None
    entry_type: Optional[str] = None  # 'article', 'inproceedings', etc.
    arxiv_id: Optional[str] = None


@dataclass
class CheckResult:
    original_entries: list[dict] = field(default_factory=list)
    fixed_entries: list[dict] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    string_defs: dict[str, str] = field(default_factory=dict)
    comments: list[str] = field(default_factory=list)
    preambles: list[str] = field(default_factory=list)
