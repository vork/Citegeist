"""
Tests for bib_checker.search – all network calls are mocked so no real
HTTP requests are made.

Real papers from arXiv (2026-02-25) are used as test fixtures:
  - FOUND cases: real titles + authors that *would* resolve correctly
  - NOT FOUND cases: completely fabricated titles + authors that should return None

The fabricated "fail" papers use plausible-looking but nonsensical titles so
the similarity checks cannot accidentally match a real paper.
"""

import json
import textwrap
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from bib_checker.datatypes import Paper
from bib_checker.search import (
    ArxivSearch,
    CrossRefSearch,
    DuckDuckGoVerifier,
    PerplexitySearch,
    PublicationLookup,
    SemanticScholarSearch,
    _clean_title,
    _title_similarity,
)


# ---------------------------------------------------------------------------
# Real papers (cs.CV / cs.LG, 2026-02-25) -- used as expected-FOUND fixtures
# ---------------------------------------------------------------------------

REAL_PAPERS = [
    {
        "title": "Human Video Generation from a Single Image with 3D Pose and View Control",
        "arxiv_id": "2602.21188",
        "authors": ["Tiantian Wang", "Chun-Han Yao", "Tao Hu",
                    "Mallikarjun Byrasandra Ramalinga Reddy",
                    "Ming-Hsuan Yang", "Varun Jampani"],
    },
    {
        "title": "Test-Time Training with KV Binding Is Secretly Linear Attention",
        "arxiv_id": "2602.21204",
        "authors": ["Junhao Liu", "Simon Elflein", "Or Litany",
                    "Zan Gojcic", "Rui Li"],
    },
    {
        "title": "Statistical Query Lower Bounds for Smoothed Agnostic Learning",
        "arxiv_id": "2602.21191",
        "authors": ["Ilias Diakonikolas", "Daniel M. Kane"],
    },
    {
        "title": "Untied Ulysses: Memory-Efficient Context Parallelism via Headwise Chunking",
        "arxiv_id": "2602.21196",
        "authors": ["Rahul Ghadia", "Mathew Abraham", "Sergey Vorobyov", "Max Ryabinin"],
    },
]

# Completely fabricated titles that should never match real papers
FAKE_PAPERS = [
    "Hyperbolically Optimal Unicorn Diffusion via Quantum Spaghetti Networks",
    "Revolutionary Attention Mechanism That Does Not Exist in Any Database",
    "Invented Gradient Descent on Imaginary Non-Euclidean Manifolds with Fictional Loss",
    "Nonexistent Zero-Shot Learning Framework for Papers That Were Never Written",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean(s: str) -> str:
    return textwrap.dedent(s).strip()


def _make_s2_response(title: str, arxiv_id: str, venue: str = "",
                       doi: str = "") -> dict:
    return {
        "data": [{
            "title": title,
            "authors": [{"name": "Test Author"}],
            "year": 2026,
            "venue": venue,
            "externalIds": {
                "ArXiv": arxiv_id,
                "DOI": doi or None,
            },
            "publicationVenue": None,
            "journal": None,
            "publicationTypes": ["JournalArticle"],
        }]
    }


def _make_crossref_response(title: str, doi: str, venue: str = "") -> dict:
    return {
        "message": {
            "items": [{
                "title": [title],
                "author": [{"given": "Test", "family": "Author"}],
                "DOI": doi,
                "container-title": [venue] if venue else [],
                "published": {"date-parts": [[2026]]},
                "type": "proceedings-article",
            }]
        }
    }


def _make_arxiv_xml(title: str, arxiv_id: str, doi: str = "",
                    journal_ref: str = "") -> str:
    doi_elem = f"<arxiv:doi>{doi}</arxiv:doi>" if doi else ""
    jr_elem = f"<arxiv:journal_ref>{journal_ref}</arxiv:journal_ref>" if journal_ref else ""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/{arxiv_id}v1</id>
    <title>{title}</title>
    <summary>Abstract text.</summary>
    <published>2026-02-25T00:00:00Z</published>
    <author><name>Test Author</name></author>
    {doi_elem}
    {jr_elem}
  </entry>
</feed>"""


# ---------------------------------------------------------------------------
# _clean_title / _title_similarity helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_clean_title_strips_latex(self):
        raw = r"\emph{Diffusion} Models for {3D} Generation"
        cleaned = _clean_title(raw)
        assert "{" not in cleaned
        assert "Diffusion" in cleaned
        assert "3D" in cleaned

    def test_clean_title_strips_special_chars(self):
        assert _clean_title("A: B, C!") == "A B C"

    @pytest.mark.parametrize("a,b,expected_ge", [
        ("Test-Time Training with KV Binding",
         "Test-Time Training with KV Binding Is Secretly Linear Attention", 0.5),
        ("Statistical Query Lower Bounds for Smoothed Agnostic Learning",
         "Statistical Query Lower Bounds for Smoothed Agnostic Learning", 1.0),
        ("Unicorn Spaghetti Networks",
         "Statistical Query Lower Bounds for Smoothed Agnostic Learning", 0.0),
    ])
    def test_title_similarity(self, a, b, expected_ge):
        sim = _title_similarity(a, b)
        assert sim >= expected_ge, f"Expected sim >= {expected_ge}, got {sim}"

    def test_similarity_symmetric(self):
        a = "Human Video Generation from a Single Image"
        b = "Single Image Human Video Generation Framework"
        assert abs(_title_similarity(a, b) - _title_similarity(b, a)) < 1e-9

    def test_similarity_empty(self):
        assert _title_similarity("", "anything") == 0.0
        assert _title_similarity("anything", "") == 0.0


# ---------------------------------------------------------------------------
# ArxivSearch (mocked)
# ---------------------------------------------------------------------------

class TestArxivSearch:
    def _search_with_xml(self, xml: str, title: str) -> Optional[Paper]:
        searcher = ArxivSearch()
        with patch.object(searcher, "_query", return_value=xml):
            return searcher.find_by_title(title)

    @pytest.mark.parametrize("paper", REAL_PAPERS)
    def test_real_paper_found(self, paper):
        xml = _make_arxiv_xml(paper["title"], paper["arxiv_id"])
        result = self._search_with_xml(xml, paper["title"])
        assert result is not None
        assert result.arxiv_id == paper["arxiv_id"]

    @pytest.mark.parametrize("fake_title", FAKE_PAPERS)
    def test_fake_paper_not_found(self, fake_title):
        # Return a real paper XML that won't match the fake title
        xml = _make_arxiv_xml(
            "Test-Time Training with KV Binding Is Secretly Linear Attention",
            "2602.21204"
        )
        result = self._search_with_xml(xml, fake_title)
        assert result is None, (
            f"Fake paper '{fake_title}' should not match a real paper"
        )

    def test_arxiv_doi_extracted(self):
        xml = _make_arxiv_xml(
            "Human Video Generation from a Single Image with 3D Pose and View Control",
            "2602.21188",
            doi="10.1145/1234.5678",
        )
        result = self._search_with_xml(
            xml,
            "Human Video Generation from a Single Image with 3D Pose and View Control"
        )
        assert result is not None
        assert result.doi == "10.1145/1234.5678"

    def test_arxiv_journal_ref_extracted(self):
        xml = _make_arxiv_xml(
            "Statistical Query Lower Bounds for Smoothed Agnostic Learning",
            "2602.21191",
            journal_ref="ICML 2026",
        )
        result = self._search_with_xml(
            xml,
            "Statistical Query Lower Bounds for Smoothed Agnostic Learning"
        )
        assert result is not None
        assert result.venue == "ICML 2026"

    def test_empty_feed_returns_none(self):
        xml = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>"""
        result = self._search_with_xml(xml, "Any Title")
        assert result is None

    def test_network_error_returns_none(self):
        searcher = ArxivSearch()
        with patch.object(searcher, "_query", return_value=None):
            result = searcher.find_by_title("Any Title")
        assert result is None


# ---------------------------------------------------------------------------
# SemanticScholarSearch (mocked)
# ---------------------------------------------------------------------------

class TestSemanticScholarSearch:
    def _search_with_body(self, body: dict, title: str) -> Optional[Paper]:
        searcher = SemanticScholarSearch()
        with patch("bib_checker.search._rate_limited_get",
                   return_value=json.dumps(body)):
            return searcher.find_by_title(title)

    @pytest.mark.parametrize("paper", REAL_PAPERS)
    def test_real_paper_found(self, paper):
        body = _make_s2_response(paper["title"], paper["arxiv_id"])
        result = self._search_with_body(body, paper["title"])
        assert result is not None
        assert result.arxiv_id == paper["arxiv_id"]

    @pytest.mark.parametrize("fake_title", FAKE_PAPERS)
    def test_fake_paper_not_found(self, fake_title):
        # The S2 response contains a real paper that won't match the fake title
        body = _make_s2_response(
            "Test-Time Training with KV Binding Is Secretly Linear Attention",
            "2602.21204"
        )
        result = self._search_with_body(body, fake_title)
        assert result is None

    def test_published_paper_doi_returned(self):
        body = _make_s2_response(
            "Statistical Query Lower Bounds for Smoothed Agnostic Learning",
            "2602.21191",
            venue="ICML",
            doi="10.5555/9876.5432",
        )
        result = self._search_with_body(
            body, "Statistical Query Lower Bounds for Smoothed Agnostic Learning"
        )
        assert result is not None
        assert result.doi == "10.5555/9876.5432"
        assert result.venue == "ICML"

    def test_network_error_returns_none(self):
        searcher = SemanticScholarSearch()
        with patch("bib_checker.search._rate_limited_get", return_value=None):
            result = searcher.find_by_title("Any Title")
        assert result is None

    def test_empty_results_returns_none(self):
        body = {"data": []}
        result = self._search_with_body(body, "Any Title")
        assert result is None


# ---------------------------------------------------------------------------
# CrossRefSearch (mocked)
# ---------------------------------------------------------------------------

class TestCrossRefSearch:
    def _search_with_body(self, body: dict, title: str) -> Optional[Paper]:
        searcher = CrossRefSearch()
        with patch("bib_checker.search._rate_limited_get",
                   return_value=json.dumps(body)):
            return searcher.find_by_title(title)

    @pytest.mark.parametrize("paper", REAL_PAPERS)
    def test_real_paper_found_with_doi(self, paper):
        doi = f"10.9999/{paper['arxiv_id']}"
        body = _make_crossref_response(paper["title"], doi)
        result = self._search_with_body(body, paper["title"])
        assert result is not None
        assert result.doi == doi

    @pytest.mark.parametrize("fake_title", FAKE_PAPERS)
    def test_fake_paper_not_found(self, fake_title):
        body = _make_crossref_response(
            "Test-Time Training with KV Binding Is Secretly Linear Attention",
            "10.9999/2602.21204"
        )
        result = self._search_with_body(body, fake_title)
        assert result is None

    def test_venue_extracted(self):
        body = _make_crossref_response(
            "Statistical Query Lower Bounds for Smoothed Agnostic Learning",
            "10.5555/test",
            venue="International Conference on Machine Learning",
        )
        result = self._search_with_body(
            body, "Statistical Query Lower Bounds for Smoothed Agnostic Learning"
        )
        assert result is not None
        assert "Machine Learning" in result.venue


# ---------------------------------------------------------------------------
# PerplexitySearch (mocked)
# ---------------------------------------------------------------------------

class TestPerplexitySearch:
    def _make_response(self, info: dict) -> str:
        content = json.dumps(info)
        return json.dumps({
            "choices": [{"message": {"content": content}}]
        })

    @pytest.mark.parametrize("paper", REAL_PAPERS[:2])
    def test_real_paper_found(self, paper):
        searcher = PerplexitySearch()
        searcher.api_key = "fake-key"
        response_body = self._make_response({
            "title": paper["title"],
            "venue": "ICML",
            "year": 2026,
            "doi": "10.9999/test",
            "authors": paper["authors"],
            "arxiv_id": paper["arxiv_id"],
        })
        with patch("urllib.request.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.read.return_value = response_body.encode()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_resp
            with patch("time.sleep"):
                result = searcher.find_by_title(paper["title"])
        assert result is not None
        assert result.doi == "10.9999/test"

    @pytest.mark.parametrize("fake_title", FAKE_PAPERS)
    def test_hallucinated_title_rejected(self, fake_title):
        searcher = PerplexitySearch()
        searcher.api_key = "fake-key"
        # Perplexity "hallucinates" a completely different title
        response_body = self._make_response({
            "title": "Completely Different Real Paper About Computer Vision",
            "venue": "CVPR",
            "year": 2025,
            "doi": "10.1109/CVPR.2025.123",
            "authors": ["Author One"],
            "arxiv_id": None,
        })
        with patch("urllib.request.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.read.return_value = response_body.encode()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_resp
            with patch("time.sleep"):
                result = searcher.find_by_title(fake_title)
        # Similarity < 0.5, so result should be rejected
        assert result is None, (
            f"Should reject hallucinated title for fake paper '{fake_title}'"
        )

    def test_no_api_key_returns_none(self):
        searcher = PerplexitySearch()
        searcher.api_key = None
        result = searcher.find_by_title("Any Paper Title")
        assert result is None

    def test_not_available_without_key(self):
        searcher = PerplexitySearch()
        searcher.api_key = None
        assert not searcher.available

    def test_available_with_key(self):
        searcher = PerplexitySearch()
        searcher.api_key = "pplx-fake"
        assert searcher.available

    def test_doi_url_stripped(self):
        searcher = PerplexitySearch()
        searcher.api_key = "fake-key"
        response_body = self._make_response({
            "title": "Test-Time Training with KV Binding Is Secretly Linear Attention",
            "venue": "ICML",
            "year": 2026,
            "doi": "https://doi.org/10.9999/stripped",
            "authors": [],
            "arxiv_id": "2602.21204",
        })
        with patch("urllib.request.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.read.return_value = response_body.encode()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_resp
            with patch("time.sleep"):
                result = searcher.find_by_title(
                    "Test-Time Training with KV Binding Is Secretly Linear Attention"
                )
        assert result is not None
        assert result.doi == "10.9999/stripped"

    def test_network_error_returns_none(self):
        searcher = PerplexitySearch()
        searcher.api_key = "fake-key"
        with patch("urllib.request.urlopen", side_effect=Exception("network error")):
            with patch("time.sleep"):
                result = searcher.find_by_title("Any Title")
        assert result is None


# ---------------------------------------------------------------------------
# DuckDuckGoVerifier (mocked)
# ---------------------------------------------------------------------------

class TestDuckDuckGoVerifier:
    def test_found_via_abstract_url(self):
        verifier = DuckDuckGoVerifier()
        ia_response = json.dumps({
            "AbstractURL": "https://example.com/paper",
            "AbstractText": "Some abstract",
            "RelatedTopics": [],
        })
        with patch("bib_checker.search._rate_limited_get", return_value=ia_response):
            result = verifier.verify("Any Paper Title", doi="10.1234/test")
        assert result is True

    def test_found_via_related_topics(self):
        verifier = DuckDuckGoVerifier()
        ia_response = json.dumps({
            "AbstractURL": "",
            "AbstractText": "",
            "RelatedTopics": [{"Text": "Some topic", "FirstURL": "https://example.com"}],
        })
        with patch("bib_checker.search._rate_limited_get", return_value=ia_response):
            result = verifier.verify("Any Paper Title")
        assert result is True

    def test_not_found_returns_false(self):
        verifier = DuckDuckGoVerifier()
        ia_response = json.dumps({
            "AbstractURL": "",
            "AbstractText": "",
            "RelatedTopics": [],
        })
        # HTML fallback also returns nothing useful
        with patch("bib_checker.search._rate_limited_get", return_value=ia_response):
            result = verifier.verify("Hyperbolically Optimal Unicorn Diffusion Networks")
        assert result is False

    def test_network_error_returns_false(self):
        verifier = DuckDuckGoVerifier()
        with patch("bib_checker.search._rate_limited_get", return_value=None):
            result = verifier.verify("Any Title")
        assert result is False

    def test_html_fallback_title_words_match(self):
        verifier = DuckDuckGoVerifier()
        # IA returns empty, HTML contains title words
        ia_empty = json.dumps({"AbstractURL": "", "RelatedTopics": []})
        html_with_words = (
            "<html><body>statistical query lower bounds smoothed agnostic</body></html>"
        )
        call_count = 0

        def mock_get(url, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if "api.duckduckgo" in url:
                return ia_empty
            return html_with_words

        with patch("bib_checker.search._rate_limited_get", side_effect=mock_get):
            result = verifier.verify(
                "Statistical Query Lower Bounds for Smoothed Agnostic Learning"
            )
        assert result is True


# ---------------------------------------------------------------------------
# PublicationLookup orchestration (mocked)
# ---------------------------------------------------------------------------

class TestPublicationLookup:
    def _make_lookup(self, verbose: bool = False) -> PublicationLookup:
        lookup = PublicationLookup(verbose=verbose)
        # Disable Perplexity by default (no key)
        lookup.perplexity.api_key = None
        return lookup

    def test_published_result_from_s2(self):
        """S2 returns a published result → used directly."""
        lookup = self._make_lookup()
        published = Paper(
            title="Test-Time Training with KV Binding Is Secretly Linear Attention",
            authors=["Liu, Junhao"],
            doi="10.9999/icml2026",
            venue="ICML",
            year=2026,
            arxiv_id="2602.21204",
        )
        with patch.object(lookup.s2, "find_by_title", return_value=published):
            with patch.object(lookup.ddg, "verify", return_value=True):
                result = lookup.find_published(
                    "Test-Time Training with KV Binding Is Secretly Linear Attention"
                )
        assert result["published_result"] is not None
        assert result["published_result"].doi == "10.9999/icml2026"
        assert result["verified"] is True

    def test_crossref_fallback_when_s2_none(self):
        """S2 returns nothing; CrossRef picks it up."""
        lookup = self._make_lookup()
        published = Paper(
            title="Statistical Query Lower Bounds for Smoothed Agnostic Learning",
            authors=["Diakonikolas, Ilias"],
            doi="10.5555/crossref",
            venue="ICML",
            year=2026,
        )
        with patch.object(lookup.s2, "find_by_title", return_value=None):
            with patch.object(lookup.crossref, "find_by_title", return_value=published):
                with patch.object(lookup.ddg, "verify", return_value=True):
                    result = lookup.find_published(
                        "Statistical Query Lower Bounds for Smoothed Agnostic Learning"
                    )
        assert result["published_result"] is not None
        assert result["published_result"].doi == "10.5555/crossref"

    def test_arxiv_only_result_when_no_published(self):
        """No published result found → arxiv_result is returned as best."""
        lookup = self._make_lookup()
        arxiv_only = Paper(
            title="Untied Ulysses Memory-Efficient Context Parallelism",
            authors=["Ghadia, Rahul"],
            arxiv_id="2602.21196",
        )
        with patch.object(lookup.s2, "find_by_title", return_value=None):
            with patch.object(lookup.crossref, "find_by_title", return_value=None):
                with patch.object(lookup.arxiv, "find_by_title", return_value=arxiv_only):
                    with patch.object(lookup.ddg, "verify", return_value=False):
                        result = lookup.find_published("Untied Ulysses")
        assert result["published_result"] is None
        assert result["arxiv_result"] is not None
        assert result["best"] is result["arxiv_result"]

    def test_perplexity_used_when_no_other_result(self):
        """When S2/CrossRef/arXiv all fail, Perplexity is called (if key set)."""
        lookup = self._make_lookup()
        lookup.perplexity.api_key = "pplx-fake"

        px_result = Paper(
            title="Statistical Query Lower Bounds for Smoothed Agnostic Learning",
            authors=["Diakonikolas, Ilias"],
            doi="10.9999/perplexity",
            venue="ICML",
            year=2026,
            arxiv_id="2602.21191",
        )
        with patch.object(lookup.s2, "find_by_title", return_value=None):
            with patch.object(lookup.crossref, "find_by_title", return_value=None):
                with patch.object(lookup.arxiv, "find_by_title", return_value=None):
                    with patch.object(lookup.perplexity, "find_by_title",
                                      return_value=px_result):
                        with patch.object(lookup.ddg, "verify", return_value=True):
                            result = lookup.find_published(
                                "Statistical Query Lower Bounds for Smoothed Agnostic Learning"
                            )
        assert result["published_result"] is not None
        assert result["published_result"].doi == "10.9999/perplexity"
        assert result["verified"] is True

    def test_perplexity_result_discarded_when_ddg_fails(self):
        """If Perplexity finds something but DDG cannot verify → discard it."""
        lookup = self._make_lookup()
        lookup.perplexity.api_key = "pplx-fake"

        hallucinated = Paper(
            title="Unicorn Spaghetti Diffusion Networks",
            authors=["Ghost, Author"],
            doi="10.9999/hallucinated",
            venue="CVPR",
            year=2024,
        )
        with patch.object(lookup.s2, "find_by_title", return_value=None):
            with patch.object(lookup.crossref, "find_by_title", return_value=None):
                with patch.object(lookup.arxiv, "find_by_title", return_value=None):
                    with patch.object(lookup.perplexity, "find_by_title",
                                      return_value=hallucinated):
                        # DDG cannot verify the hallucinated result
                        with patch.object(lookup.ddg, "verify", return_value=False):
                            result = lookup.find_published(
                                "Hyperbolically Optimal Unicorn Diffusion"
                            )
        # Hallucinated result must be discarded
        assert result["published_result"] is None
        assert result["verified"] is False

    def test_nothing_found_for_fake_title(self):
        """All backends return None → best is None."""
        lookup = self._make_lookup()
        with patch.object(lookup.s2, "find_by_title", return_value=None):
            with patch.object(lookup.crossref, "find_by_title", return_value=None):
                with patch.object(lookup.arxiv, "find_by_title", return_value=None):
                    result = lookup.find_published(
                        "Invented Gradient Descent on Imaginary Non-Euclidean Manifolds"
                    )
        assert result["best"] is None
        assert result["published_result"] is None
        assert result["arxiv_result"] is None
