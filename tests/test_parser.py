"""
Unit tests for bib_checker.parser
"""

import pytest
from pathlib import Path

from bib_checker.parser import (
    parse_bib_file,
    strip_braces,
    get_field,
    is_macro,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# strip_braces
# ---------------------------------------------------------------------------

class TestStripBraces:
    def test_braced(self):
        assert strip_braces("{hello}") == "hello"

    def test_quoted(self):
        assert strip_braces('"hello"') == "hello"

    def test_bare(self):
        assert strip_braces("cvpr") == "cvpr"

    def test_nested_braces_preserved(self):
        # Only outermost braces are stripped
        assert strip_braces("{{nested}}") == "{nested}"

    def test_empty(self):
        assert strip_braces("") == ""

    def test_whitespace(self):
        assert strip_braces("  {hello}  ") == "hello"

    def test_number(self):
        assert strip_braces("{2024}") == "2024"


# ---------------------------------------------------------------------------
# parse_bib_file – basic structure
# ---------------------------------------------------------------------------

class TestParseBibFileBasic:
    def test_parses_string_defs(self):
        bib = "@String{CVPR = {CVPR}}\n@String{ICCV = {ICCV}}\n"
        result = parse_bib_file(bib)
        assert "CVPR" in result["strings"]
        assert "ICCV" in result["strings"]
        assert result["strings"]["CVPR"]["value"] == "CVPR"

    def test_parses_string_with_quotes(self):
        bib = '@String{FOO = "bar baz"}\n'
        result = parse_bib_file(bib)
        assert result["strings"]["FOO"]["value"] == "bar baz"

    def test_parses_article(self):
        bib = textwrap("""
            @article{smith2024test,
              author = {Smith, John},
              title  = {A Test Paper},
              journal = {Nature},
              year   = {2024}
            }
        """)
        result = parse_bib_file(bib)
        assert len(result["entries"]) == 1
        e = result["entries"][0]
        assert e["__key__"] == "smith2024test"
        assert e["__type__"] == "article"
        assert strip_braces(e["author"]) == "Smith, John"
        assert strip_braces(e["year"]) == "2024"

    def test_parses_inproceedings(self):
        bib = textwrap("""
            @inproceedings{jones2025conf,
              author    = {Jones, Alice},
              title     = {A Conference Paper},
              booktitle = {CVPR},
              year      = {2025}
            }
        """)
        result = parse_bib_file(bib)
        e = result["entries"][0]
        assert e["__type__"] == "inproceedings"
        assert e["__key__"] == "jones2025conf"

    def test_parses_multiple_entries(self):
        bib = textwrap("""
            @article{a2024, author={A}, title={T}, journal={J}, year={2024}}
            @inproceedings{b2025, author={B}, title={T2}, booktitle={C}, year={2025}}
        """)
        result = parse_bib_file(bib)
        assert len(result["entries"]) == 2
        assert result["entries"][0]["__key__"] == "a2024"
        assert result["entries"][1]["__key__"] == "b2025"

    def test_entry_type_lowercased(self):
        bib = textwrap("""
            @InProceedings{key2024,
              author    = {Foo, Bar},
              title     = {Title},
              booktitle = {Conference},
              year      = {2024}
            }
        """)
        result = parse_bib_file(bib)
        assert result["entries"][0]["__type__"] == "inproceedings"

    def test_parses_bare_macro_value(self):
        # booktitle = CVPR  (bare word, no braces)
        bib = "@String{CVPR={CVPR}}\n@inproceedings{k,author={A},title={T},booktitle=CVPR,year={2024}}"
        result = parse_bib_file(bib)
        e = result["entries"][0]
        assert e["booktitle"].strip() == "CVPR"

    def test_preamble_parsed(self):
        bib = "@preamble{This is a preamble}\n@article{k,author={A},title={T},journal={J},year={2024}}"
        result = parse_bib_file(bib)
        assert len(result["preambles"]) == 1

    def test_empty_file(self):
        result = parse_bib_file("")
        assert result["entries"] == []
        assert result["strings"] == {}

    def test_comment_only(self):
        result = parse_bib_file("% just a comment\n")
        assert result["entries"] == []

    def test_parenthesis_delimiter(self):
        # BibTeX allows @article(key, ...) with parentheses
        bib = "@article(paren2024, author={A}, title={T}, journal={J}, year={2024})"
        result = parse_bib_file(bib)
        assert len(result["entries"]) == 1
        assert result["entries"][0]["__key__"] == "paren2024"

    def test_field_names_lowercased(self):
        bib = "@article{k, Author={Alice}, Title={T}, Journal={J}, Year={2024}}"
        result = parse_bib_file(bib)
        e = result["entries"][0]
        assert "author" in e
        assert "Author" not in e

    def test_special_characters_in_braces(self):
        bib = r"@article{k, author={Sch\"{o}n, Hans}, title={T}, journal={J}, year={2024}}"
        result = parse_bib_file(bib)
        e = result["entries"][0]
        assert "author" in e
        assert r"Sch\"{o}n" in e["author"]

    def test_multiline_entry(self):
        bib = textwrap("""
            @article{multi2024,
              author  = {One, Author
                         and Two, Author},
              title   = {A Multi-Line
                         Title},
              journal = {Some Journal},
              year    = {2024}
            }
        """)
        result = parse_bib_file(bib)
        assert len(result["entries"]) == 1


# ---------------------------------------------------------------------------
# parse_bib_file – fixture files
# ---------------------------------------------------------------------------

class TestParseBibFixtures:
    def test_good_bib_parses_all_entries(self):
        text = (FIXTURES / "good.bib").read_text()
        result = parse_bib_file(text)
        # 9 actual entries (6 articles + 3 inproceedings in good.bib)
        assert len(result["entries"]) == 8
        keys = [e["__key__"] for e in result["entries"]]
        assert "cheng2026cryo" in keys
        assert "liu2026ttt" in keys
        assert "gaggion2026mask" in keys

    def test_good_bib_has_strings(self):
        text = (FIXTURES / "good.bib").read_text()
        result = parse_bib_file(text)
        assert "CVPR" in result["strings"]
        assert "ARXIV" in result["strings"]

    def test_bad_bib_parses_without_crash(self):
        text = (FIXTURES / "bad.bib").read_text()
        result = parse_bib_file(text)
        # Should parse all 9 entries even though they have semantic issues
        assert len(result["entries"]) == 9

    def test_arxiv_upgrade_bib_parses(self):
        text = (FIXTURES / "arxiv_upgrade.bib").read_text()
        result = parse_bib_file(text)
        assert len(result["entries"]) == 4
        keys = [e["__key__"] for e in result["entries"]]
        assert "ghadia2026ulysses" in keys
        assert "lu2026seeing" in keys


# ---------------------------------------------------------------------------
# get_field
# ---------------------------------------------------------------------------

class TestGetField:
    def test_braced_value(self):
        entry = {"title": "{A Test Paper}"}
        assert get_field(entry, "title") == "A Test Paper"

    def test_quoted_value(self):
        entry = {"title": '"A Test Paper"'}
        assert get_field(entry, "title") == "A Test Paper"

    def test_bare_macro_resolved(self):
        strings = {"CVPR": {"value": "CVPR", "raw": "{CVPR}"}}
        entry = {"booktitle": "CVPR"}
        assert get_field(entry, "booktitle", strings) == "CVPR"

    def test_missing_field(self):
        entry = {}
        assert get_field(entry, "year") == ""

    def test_bare_macro_not_in_strings(self):
        entry = {"booktitle": "ICCV"}
        assert get_field(entry, "booktitle") == "ICCV"


# ---------------------------------------------------------------------------
# is_macro
# ---------------------------------------------------------------------------

class TestIsMacro:
    def test_bare_word_in_strings(self):
        strings = {"CVPR": {"value": "CVPR", "raw": "{CVPR}"}}
        assert is_macro("CVPR", strings) == "CVPR"

    def test_braced_value_not_macro(self):
        strings = {"CVPR": {"value": "CVPR", "raw": "{CVPR}"}}
        assert is_macro("{CVPR}", strings) is None

    def test_quoted_value_not_macro(self):
        strings = {"CVPR": {"value": "CVPR", "raw": "{CVPR}"}}
        assert is_macro('"CVPR"', strings) is None

    def test_unknown_bare_word(self):
        strings = {"CVPR": {"value": "CVPR", "raw": "{CVPR}"}}
        assert is_macro("ICCV", strings) is None

    def test_empty_string(self):
        assert is_macro("", {}) is None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def textwrap(s: str) -> str:
    """Strip leading/trailing whitespace from each line of a triple-quoted string."""
    import textwrap as tw
    return tw.dedent(s).strip()
