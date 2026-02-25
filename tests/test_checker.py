"""
Unit tests for bib_checker.checker – all run in offline/skip_network mode
so no real HTTP requests are made.
"""

import textwrap
from pathlib import Path

import pytest

from bib_checker.checker import BibChecker
from bib_checker.datatypes import IssueLevel, IssueType
from bib_checker.parser import parse_bib_file

FIXTURES = Path(__file__).parent / "fixtures"


def make_checker() -> BibChecker:
    return BibChecker(skip_network=True, learn_venues=False)


def dedent(s: str) -> str:
    return textwrap.dedent(s).strip()


def issues_of_type(issues, issue_type):
    return [i for i in issues if i.issue_type == issue_type]


def issue_keys_of_type(issues, issue_type):
    return {i.key for i in issues_of_type(issues, issue_type)}


# ---------------------------------------------------------------------------
# Venue standardization
# ---------------------------------------------------------------------------

class TestVenueStandardization:
    def test_lowercase_macro_standardized(self):
        bib = dedent("""
            @String{CVPR = {CVPR}}
            @inproceedings{k2024,
              author    = {Smith, A},
              title     = {A Paper},
              booktitle = cvpr,
              year      = {2024}
            }
        """)
        parsed = parse_bib_file(bib)
        checker = make_checker()
        fixed, issues = checker.check_entries(parsed)
        std = issues_of_type(issues, IssueType.VENUE_STANDARDIZED)
        assert any(i.key == "k2024" for i in std)
        # Fixed entry booktitle should be the canonical key
        entry = next(e for e in fixed if e["__key__"] == "k2024")
        assert entry["booktitle"] == "CVPR"

    def test_long_form_venue_standardized(self):
        bib = dedent("""
            @inproceedings{long2024,
              author    = {Doe, Jane},
              title     = {Conference Paper},
              booktitle = {Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition},
              year      = {2024}
            }
        """)
        parsed = parse_bib_file(bib)
        checker = make_checker()
        fixed, issues = checker.check_entries(parsed)
        std = issues_of_type(issues, IssueType.VENUE_STANDARDIZED)
        assert any(i.key == "long2024" for i in std)
        entry = next(e for e in fixed if e["__key__"] == "long2024")
        assert entry["booktitle"] == "CVPR"

    def test_already_canonical_not_flagged(self):
        bib = dedent("""
            @String{CVPR = {CVPR}}
            @inproceedings{k2024,
              author    = {Smith, A},
              title     = {A Paper},
              booktitle = CVPR,
              year      = {2024}
            }
        """)
        parsed = parse_bib_file(bib)
        checker = make_checker()
        _, issues = checker.check_entries(parsed)
        std = issues_of_type(issues, IssueType.VENUE_STANDARDIZED)
        assert not any(i.key == "k2024" for i in std)

    def test_unknown_venue_flagged_as_suspicious(self):
        bib = dedent("""
            @article{k2024,
              author  = {X, Y},
              title   = {Paper},
              journal = {Journal of Imaginary Science},
              year    = {2024}
            }
        """)
        parsed = parse_bib_file(bib)
        checker = make_checker()
        _, issues = checker.check_entries(parsed)
        susp = issues_of_type(issues, IssueType.SUSPICIOUS_VENUE)
        assert any(i.key == "k2024" for i in susp)

    def test_iclr_variant_standardized(self):
        bib = dedent("""
            @inproceedings{k2023,
              author    = {A, B},
              title     = {T},
              booktitle = {International Conference on Learning Representations},
              year      = {2023}
            }
        """)
        parsed = parse_bib_file(bib)
        checker = make_checker()
        fixed, issues = checker.check_entries(parsed)
        entry = next(e for e in fixed if e["__key__"] == "k2023")
        assert entry["booktitle"] == "ICLR"

    def test_neurips_variant_standardized(self):
        bib = dedent("""
            @article{k2022,
              author  = {A, B},
              title   = {T},
              journal = {Advances in Neural Information Processing Systems},
              year    = {2022}
            }
        """)
        parsed = parse_bib_file(bib)
        checker = make_checker()
        fixed, issues = checker.check_entries(parsed)
        entry = next(e for e in fixed if e["__key__"] == "k2022")
        assert entry["journal"] == "NIPS"


# ---------------------------------------------------------------------------
# Entry type inference
# ---------------------------------------------------------------------------

class TestEntryTypeInference:
    def test_misc_with_journal_becomes_article(self):
        bib = dedent("""
            @misc{k2024,
              author  = {A, B},
              title   = {A Paper},
              journal = {Some Journal},
              year    = {2024}
            }
        """)
        parsed = parse_bib_file(bib)
        checker = make_checker()
        fixed, issues = checker.check_entries(parsed)
        entry = next(e for e in fixed if e["__key__"] == "k2024")
        assert entry["__type__"] == "article"
        assert any(i.issue_type == IssueType.ENTRY_TYPE_FIXED for i in issues)

    def test_misc_with_booktitle_becomes_inproceedings(self):
        bib = dedent("""
            @misc{k2024,
              author    = {A, B},
              title     = {A Paper},
              booktitle = {Some Conference},
              year      = {2024}
            }
        """)
        parsed = parse_bib_file(bib)
        checker = make_checker()
        fixed, issues = checker.check_entries(parsed)
        entry = next(e for e in fixed if e["__key__"] == "k2024")
        assert entry["__type__"] == "inproceedings"

    def test_correct_type_not_changed(self):
        bib = dedent("""
            @article{k2024,
              author  = {A, B},
              title   = {T},
              journal = {J},
              year    = {2024}
            }
        """)
        parsed = parse_bib_file(bib)
        checker = make_checker()
        fixed, issues = checker.check_entries(parsed)
        entry = next(e for e in fixed if e["__key__"] == "k2024")
        assert entry["__type__"] == "article"
        assert not any(i.issue_type == IssueType.ENTRY_TYPE_FIXED for i in issues)


# ---------------------------------------------------------------------------
# Missing required fields
# ---------------------------------------------------------------------------

class TestMissingFields:
    def test_article_missing_year(self):
        bib = dedent("""
            @article{k2024,
              author  = {A, B},
              title   = {T},
              journal = {J}
            }
        """)
        parsed = parse_bib_file(bib)
        checker = make_checker()
        _, issues = checker.check_entries(parsed)
        missing = issues_of_type(issues, IssueType.MISSING_FIELD)
        assert any(i.key == "k2024" and "year" in i.message for i in missing)

    def test_article_missing_journal(self):
        bib = dedent("""
            @article{k2024,
              author = {A, B},
              title  = {T},
              year   = {2024}
            }
        """)
        parsed = parse_bib_file(bib)
        checker = make_checker()
        _, issues = checker.check_entries(parsed)
        missing = issues_of_type(issues, IssueType.MISSING_FIELD)
        assert any(i.key == "k2024" and "journal" in i.message for i in missing)

    def test_inproceedings_missing_booktitle(self):
        bib = dedent("""
            @inproceedings{k2024,
              author = {A, B},
              title  = {T},
              year   = {2024}
            }
        """)
        parsed = parse_bib_file(bib)
        checker = make_checker()
        _, issues = checker.check_entries(parsed)
        missing = issues_of_type(issues, IssueType.MISSING_FIELD)
        assert any("booktitle" in i.message for i in missing)

    def test_complete_entry_no_missing_field_warning(self):
        bib = dedent("""
            @article{k2024,
              author  = {A, B},
              title   = {T},
              journal = {J},
              year    = {2024}
            }
        """)
        parsed = parse_bib_file(bib)
        checker = make_checker()
        _, issues = checker.check_entries(parsed)
        missing = issues_of_type(issues, IssueType.MISSING_FIELD)
        assert not missing


# ---------------------------------------------------------------------------
# Duplicate key detection
# ---------------------------------------------------------------------------

class TestDuplicateKeys:
    def test_duplicate_key_flagged(self):
        bib = dedent("""
            @article{dup2024, author={A}, title={T1}, journal={J}, year={2024}}
            @article{dup2024, author={B}, title={T2}, journal={J}, year={2024}}
        """)
        parsed = parse_bib_file(bib)
        checker = make_checker()
        _, issues = checker.check_entries(parsed)
        dups = issues_of_type(issues, IssueType.DUPLICATE_KEY)
        assert any(i.key == "dup2024" for i in dups)

    def test_unique_keys_no_duplicate_error(self):
        bib = dedent("""
            @article{a2024, author={A}, title={T1}, journal={J}, year={2024}}
            @article{b2024, author={B}, title={T2}, journal={J}, year={2024}}
        """)
        parsed = parse_bib_file(bib)
        checker = make_checker()
        _, issues = checker.check_entries(parsed)
        dups = issues_of_type(issues, IssueType.DUPLICATE_KEY)
        assert not dups


# ---------------------------------------------------------------------------
# Undefined @String macro detection
# ---------------------------------------------------------------------------

class TestUndefinedStrings:
    def test_undefined_macro_flagged(self):
        # GHOSTMACRO is not defined as @String and not in CANONICAL_STRINGS
        bib = dedent("""
            @inproceedings{k2024,
              author    = {A, B},
              title     = {T},
              booktitle = GHOSTMACRO,
              year      = {2024}
            }
        """)
        parsed = parse_bib_file(bib)
        checker = make_checker()
        _, issues = checker.check_entries(parsed)
        undef = issues_of_type(issues, IssueType.UNDEFINED_STRING)
        assert any(i.key == "k2024" for i in undef)

    def test_defined_string_macro_not_flagged(self):
        bib = dedent("""
            @String{MYCONF = {My Conference}}
            @inproceedings{k2024,
              author    = {A, B},
              title     = {T},
              booktitle = MYCONF,
              year      = {2024}
            }
        """)
        parsed = parse_bib_file(bib)
        checker = make_checker()
        _, issues = checker.check_entries(parsed)
        undef = issues_of_type(issues, IssueType.UNDEFINED_STRING)
        assert not any(i.key == "k2024" for i in undef)

    def test_canonical_macro_not_flagged(self):
        # CVPR, ICCV etc. are in CANONICAL_STRINGS – should never be undefined
        bib = dedent("""
            @inproceedings{k2024,
              author    = {A, B},
              title     = {T},
              booktitle = CVPR,
              year      = {2024}
            }
        """)
        parsed = parse_bib_file(bib)
        checker = make_checker()
        _, issues = checker.check_entries(parsed)
        undef = issues_of_type(issues, IssueType.UNDEFINED_STRING)
        assert not any(i.key == "k2024" for i in undef)

    def test_month_macros_not_flagged(self):
        # Standard BibTeX month macros (jan, feb, ..., dec) must not trigger errors
        bib = dedent("""
            @article{k2024,
              author  = {A, B},
              title   = {T},
              journal = {J},
              year    = {2024},
              month   = aug
            }
        """)
        parsed = parse_bib_file(bib)
        checker = make_checker()
        _, issues = checker.check_entries(parsed)
        undef = issues_of_type(issues, IssueType.UNDEFINED_STRING)
        assert not any("month" in i.message for i in undef)

    @pytest.mark.parametrize("month", [
        "jan", "feb", "mar", "apr", "may", "jun",
        "jul", "aug", "sep", "oct", "nov", "dec",
    ])
    def test_all_month_macros_not_flagged(self, month):
        bib = (
            f"@article{{k2024, author={{A}}, title={{T}}, "
            f"journal={{J}}, year={{2024}}, month={month}}}"
        )
        parsed = parse_bib_file(bib)
        checker = make_checker()
        _, issues = checker.check_entries(parsed)
        undef = issues_of_type(issues, IssueType.UNDEFINED_STRING)
        assert not any("month" in i.message for i in undef), (
            f"Month macro '{month}' was incorrectly flagged as undefined"
        )


# ---------------------------------------------------------------------------
# arXiv detection (offline – no network calls)
# ---------------------------------------------------------------------------

class TestArxivDetection:
    def test_arxiv_journal_macro_detected(self):
        bib = dedent("""
            @String{ARXIV = {arXiv}}
            @article{k2026,
              author  = {A, B},
              title   = {A Preprint Paper},
              journal = ARXIV,
              eprint  = {2602.21195},
              year    = {2026}
            }
        """)
        parsed = parse_bib_file(bib)
        checker = make_checker()
        _, issues = checker.check_entries(parsed)
        # In offline mode should flag as arXiv-not-found
        arxiv_issues = issues_of_type(issues, IssueType.ARXIV_NOT_FOUND_PUBLISHED)
        assert any(i.key == "k2026" for i in arxiv_issues)

    def test_arxiv_url_detected(self):
        bib = dedent("""
            @misc{k2026,
              author = {A, B},
              title  = {A Preprint},
              url    = {https://arxiv.org/abs/2602.21196},
              year   = {2026}
            }
        """)
        parsed = parse_bib_file(bib)
        checker = make_checker()
        _, issues = checker.check_entries(parsed)
        arxiv_issues = issues_of_type(issues, IssueType.ARXIV_NOT_FOUND_PUBLISHED)
        assert any(i.key == "k2026" for i in arxiv_issues)

    def test_archiveprefix_eprint_detected(self):
        bib = dedent("""
            @misc{k2026,
              author        = {A, B},
              title         = {A Preprint},
              archiveprefix = {arXiv},
              eprint        = {2602.21185},
              year          = {2026}
            }
        """)
        parsed = parse_bib_file(bib)
        checker = make_checker()
        _, issues = checker.check_entries(parsed)
        arxiv_issues = issues_of_type(issues, IssueType.ARXIV_NOT_FOUND_PUBLISHED)
        assert any(i.key == "k2026" for i in arxiv_issues)

    def test_arxiv_inline_string_detected(self):
        # 'arXiv preprint arXiv:...' as raw journal string
        bib = dedent("""
            @article{k2026,
              author  = {Nobody, A},
              title   = {Imaginary Paper},
              journal = {arXiv preprint arXiv:2601.99999},
              year    = {2026}
            }
        """)
        parsed = parse_bib_file(bib)
        checker = make_checker()
        _, issues = checker.check_entries(parsed)
        arxiv_issues = issues_of_type(issues, IssueType.ARXIV_NOT_FOUND_PUBLISHED)
        assert any(i.key == "k2026" for i in arxiv_issues)

    def test_non_arxiv_entry_not_flagged(self):
        bib = dedent("""
            @inproceedings{k2025,
              author    = {A, B},
              title     = {A Published Paper},
              booktitle = CVPR,
              year      = {2025}
            }
        """)
        parsed = parse_bib_file(bib)
        checker = make_checker()
        _, issues = checker.check_entries(parsed)
        arxiv_issues = issues_of_type(issues, IssueType.ARXIV_NOT_FOUND_PUBLISHED)
        assert not any(i.key == "k2025" for i in arxiv_issues)


# ---------------------------------------------------------------------------
# Fixture file: bad.bib – all expected issues present
# ---------------------------------------------------------------------------

class TestBadBibFixture:
    @pytest.fixture(scope="class")
    def bad_result(self):
        text = (FIXTURES / "bad.bib").read_text()
        parsed = parse_bib_file(text)
        checker = make_checker()
        fixed, issues = checker.check_entries(parsed)
        return fixed, issues

    def test_duplicate_key_detected(self, bad_result):
        _, issues = bad_result
        dups = issues_of_type(issues, IssueType.DUPLICATE_KEY)
        assert any(i.key == "dupkey2026paper" for i in dups)

    def test_undefined_macro_detected(self, bad_result):
        _, issues = bad_result
        undef = issues_of_type(issues, IssueType.UNDEFINED_STRING)
        # ghost2026missing uses BADCONF which is not defined in bad.bib or CANONICAL_STRINGS
        assert any(i.key == "ghost2026missing" for i in undef)

    def test_misc_with_journal_fixed(self, bad_result):
        fixed, issues = bad_result
        entry = next(e for e in fixed if e["__key__"] == "misc2026wrongtype")
        assert entry["__type__"] == "article"

    def test_raw_venue_standardized(self, bad_result):
        fixed, issues = bad_result
        # rawvenue2026paper had the full CVPR long-form string
        entry = next(e for e in fixed if e["__key__"] == "rawvenue2026paper")
        assert entry["booktitle"] == "CVPR"

    def test_missing_year_detected(self, bad_result):
        _, issues = bad_result
        missing = issues_of_type(issues, IssueType.MISSING_FIELD)
        assert any(i.key == "noyear2026missing" and "year" in i.message
                   for i in missing)

    def test_arxiv_inline_string_detected(self, bad_result):
        _, issues = bad_result
        arxiv_issues = issues_of_type(issues, IssueType.ARXIV_NOT_FOUND_PUBLISHED)
        assert any(i.key == "fakearxiv2026preprint" for i in arxiv_issues)

    def test_no_false_positive_on_complete_entries(self, bad_result):
        _, issues = bad_result
        # dupkey2026paper entries are complete – no MISSING_FIELD errors for them
        missing = issues_of_type(issues, IssueType.MISSING_FIELD)
        assert not any(i.key == "dupkey2026paper" for i in missing)


# ---------------------------------------------------------------------------
# Fixture file: good.bib – minimal noise
# ---------------------------------------------------------------------------

class TestGoodBibFixture:
    @pytest.fixture(scope="class")
    def good_result(self):
        text = (FIXTURES / "good.bib").read_text()
        parsed = parse_bib_file(text)
        checker = make_checker()
        fixed, issues = checker.check_entries(parsed)
        return fixed, issues

    def test_no_errors(self, good_result):
        _, issues = good_result
        errors = [i for i in issues if i.level == IssueLevel.ERROR]
        assert not errors, f"Unexpected errors: {errors}"

    def test_no_duplicate_keys(self, good_result):
        _, issues = good_result
        assert not issues_of_type(issues, IssueType.DUPLICATE_KEY)

    def test_no_undefined_strings(self, good_result):
        _, issues = good_result
        assert not issues_of_type(issues, IssueType.UNDEFINED_STRING)

    def test_no_missing_fields(self, good_result):
        _, issues = good_result
        assert not issues_of_type(issues, IssueType.MISSING_FIELD)

    def test_published_entries_not_flagged_as_arxiv(self, good_result):
        _, issues = good_result
        # gaggion2026mask and barakat2026passk are @inproceedings – not arXiv
        arxiv_issues = issues_of_type(issues, IssueType.ARXIV_NOT_FOUND_PUBLISHED)
        arxiv_keys = {i.key for i in arxiv_issues}
        assert "gaggion2026mask" not in arxiv_keys
        assert "barakat2026passk" not in arxiv_keys
