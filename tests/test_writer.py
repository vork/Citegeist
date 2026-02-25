"""
Unit tests for bib_checker.writer – BibTeX serialization.
"""

import textwrap
from pathlib import Path

import pytest

from bib_checker.parser import parse_bib_file
from bib_checker.writer import (
    _collect_used_macros,
    _emit_entry,
    _serialize_value,
    write_bib,
)
from bib_checker.strings import CANONICAL_STRINGS

FIXTURES = Path(__file__).parent / "fixtures"


def dedent(s: str) -> str:
    return textwrap.dedent(s).strip()


# ---------------------------------------------------------------------------
# _serialize_value
# ---------------------------------------------------------------------------

class TestSerializeValue:
    def test_braced_value_unchanged(self):
        assert _serialize_value("{Hello World}") == "{Hello World}"

    def test_quoted_value_unchanged(self):
        assert _serialize_value('"Hello World"') == '"Hello World"'

    def test_bare_number_unchanged(self):
        assert _serialize_value("2024") == "2024"

    def test_bare_canonical_macro_unchanged(self):
        assert _serialize_value("CVPR") == "CVPR"
        assert _serialize_value("NIPS") == "NIPS"

    def test_bare_word_gets_braced(self):
        # A bare word that's not a number or macro gets wrapped
        result = _serialize_value("some text without braces")
        assert result == "{some text without braces}"

    def test_empty_string(self):
        assert _serialize_value("") == "{}"

    def test_whitespace_only(self):
        assert _serialize_value("   ") == "{}"


# ---------------------------------------------------------------------------
# _collect_used_macros
# ---------------------------------------------------------------------------

class TestCollectUsedMacros:
    def test_finds_macro_in_booktitle(self):
        entries = [{"__key__": "k", "__type__": "inproceedings", "booktitle": "CVPR"}]
        macros = _collect_used_macros(entries)
        assert "CVPR" in macros

    def test_finds_macro_in_journal(self):
        entries = [{"__key__": "k", "__type__": "article", "journal": "NIPS"}]
        macros = _collect_used_macros(entries)
        assert "NIPS" in macros

    def test_ignores_braced_values(self):
        entries = [{"__key__": "k", "__type__": "article",
                    "journal": "{Some Journal Name}"}]
        macros = _collect_used_macros(entries)
        assert not macros

    def test_ignores_internal_fields(self):
        entries = [{"__key__": "k", "__type__": "article",
                    "journal": "{J}", "year": "{2024}"}]
        macros = _collect_used_macros(entries)
        assert not macros

    def test_multiple_macros_collected(self):
        entries = [
            {"__key__": "a", "__type__": "inproceedings", "booktitle": "CVPR"},
            {"__key__": "b", "__type__": "inproceedings", "booktitle": "ICCV"},
            {"__key__": "c", "__type__": "article", "journal": "PAMI"},
        ]
        macros = _collect_used_macros(entries)
        assert "CVPR" in macros
        assert "ICCV" in macros
        assert "PAMI" in macros


# ---------------------------------------------------------------------------
# _emit_entry
# ---------------------------------------------------------------------------

class TestEmitEntry:
    def test_basic_article(self):
        entry = {
            "__key__": "smith2024",
            "__type__": "article",
            "author": "{Smith, John}",
            "title": "{A Test Paper}",
            "journal": "PAMI",
            "year": "{2024}",
        }
        out = _emit_entry(entry)
        assert out.startswith("@article{smith2024,")
        assert "author" in out
        assert "PAMI" in out
        assert out.endswith("}")

    def test_inproceedings(self):
        entry = {
            "__key__": "jones2025",
            "__type__": "inproceedings",
            "author": "{Jones, Alice}",
            "title": "{Conference Paper}",
            "booktitle": "CVPR",
            "year": "{2025}",
        }
        out = _emit_entry(entry)
        assert out.startswith("@inproceedings{jones2025,")
        assert "CVPR" in out

    def test_field_order_respected(self):
        """author should appear before title, title before booktitle, etc."""
        entry = {
            "__key__": "k",
            "__type__": "inproceedings",
            "year": "{2024}",
            "booktitle": "ICCV",
            "title": "{T}",
            "author": "{A}",
        }
        out = _emit_entry(entry)
        lines = out.splitlines()
        field_names = [l.strip().split()[0] for l in lines[1:-1]]
        author_idx = field_names.index("author")
        title_idx = field_names.index("title")
        booktitle_idx = field_names.index("booktitle")
        assert author_idx < title_idx < booktitle_idx

    def test_no_trailing_comma_on_last_field(self):
        entry = {
            "__key__": "k",
            "__type__": "article",
            "author": "{A}",
            "title": "{T}",
            "journal": "{J}",
            "year": "{2024}",
        }
        out = _emit_entry(entry)
        lines = [l for l in out.splitlines() if l.strip() and not l.startswith("@") and l != "}"]
        last_field_line = lines[-1]
        assert not last_field_line.rstrip().endswith(","), (
            f"Last field line should not end with comma: {last_field_line!r}"
        )

    def test_internal_fields_not_emitted(self):
        entry = {
            "__key__": "k",
            "__type__": "article",
            "author": "{A}",
            "title": "{T}",
            "journal": "{J}",
            "year": "{2024}",
        }
        out = _emit_entry(entry)
        assert "__key__" not in out
        assert "__type__" not in out

    def test_empty_fields_not_emitted(self):
        entry = {
            "__key__": "k",
            "__type__": "article",
            "author": "{A}",
            "title": "{T}",
            "journal": "{J}",
            "year": "{2024}",
            "note": "",      # empty – should be omitted
        }
        out = _emit_entry(entry)
        assert "note" not in out


# ---------------------------------------------------------------------------
# write_bib – full round-trip
# ---------------------------------------------------------------------------

class TestWriteBib:
    def _roundtrip(self, bib_text: str) -> str:
        parsed = parse_bib_file(bib_text)
        # Simulate checker output (no changes)
        return write_bib(parsed["entries"], parsed)

    def test_string_block_emitted(self):
        bib = dedent("""
            @inproceedings{k2024,
              author    = {A, B},
              title     = {T},
              booktitle = CVPR,
              year      = {2024}
            }
        """)
        # Entries already using CVPR macro
        parsed = parse_bib_file(bib)
        entries = parsed["entries"]
        entries[0]["booktitle"] = "CVPR"  # ensure bare macro
        out = write_bib(entries, parsed)
        assert "@String{CVPR" in out

    def test_only_used_macros_emitted(self):
        bib = dedent("""
            @inproceedings{k2024,
              author    = {A, B},
              title     = {T},
              booktitle = CVPR,
              year      = {2024}
            }
        """)
        parsed = parse_bib_file(bib)
        entries = list(parsed["entries"])
        entries[0]["booktitle"] = "CVPR"
        out = write_bib(entries, parsed)
        # ICCV is in CANONICAL_STRINGS but not used – must not appear in @String block
        string_block = out[:out.index("@inproceedings")]
        assert "ICCV" not in string_block
        assert "ECCV" not in string_block

    def test_all_entries_present(self):
        bib = dedent("""
            @article{a2024, author={A}, title={T1}, journal={J}, year={2024}}
            @inproceedings{b2025, author={B}, title={T2}, booktitle={C}, year={2025}}
        """)
        out = self._roundtrip(bib)
        assert "@article{a2024" in out
        assert "@inproceedings{b2025" in out

    def test_roundtrip_good_fixture(self):
        text = (FIXTURES / "good.bib").read_text()
        parsed = parse_bib_file(text)
        out = write_bib(parsed["entries"], parsed)
        # Re-parse the output and check all keys are present
        reparsed = parse_bib_file(out)
        original_keys = {e["__key__"] for e in parsed["entries"]}
        output_keys = {e["__key__"] for e in reparsed["entries"]}
        assert original_keys == output_keys

    def test_doi_field_preserved(self):
        bib = dedent("""
            @article{k2024,
              author  = {A},
              title   = {T},
              journal = {J},
              year    = {2024},
              doi     = {10.1234/test}
            }
        """)
        out = self._roundtrip(bib)
        assert "10.1234/test" in out

    def test_macro_written_bare_not_braced(self):
        """CVPR should appear as bare 'CVPR', not '{CVPR}'."""
        bib = dedent("""
            @inproceedings{k2024,
              author    = {A},
              title     = {T},
              booktitle = CVPR,
              year      = {2024}
            }
        """)
        parsed = parse_bib_file(bib)
        entries = list(parsed["entries"])
        entries[0]["booktitle"] = "CVPR"
        out = write_bib(entries, parsed)
        # The field line should say "= CVPR" not "= {CVPR}"
        for line in out.splitlines():
            if "booktitle" in line:
                assert "= CVPR" in line
                assert "= {CVPR}" not in line
                break
