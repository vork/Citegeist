"""
Publication lookup backends:

1. ArxivSearch            – queries the arXiv API by title
2. SemanticScholarSearch  – queries the Semantic Scholar API (free, no key needed)
3. CrossRefSearch         – queries the CrossRef REST API (free, no key needed)
4. PerplexitySearch       – uses Perplexity AI API (requires PERPLEXITY_API_KEY env var)
5. DuckDuckGoVerifier     – confirms paper existence via DuckDuckGo instant-answer API
                            (used to verify results from other backends, especially Perplexity)

All search backends implement find_by_title(title) -> Optional[Paper].
"""

import os
import re
import time
import json
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

from .datatypes import Paper


# ---------------------------------------------------------------------------
# Load .env file (stdlib-only, no python-dotenv required)
# ---------------------------------------------------------------------------

def _load_dotenv() -> None:
    """Load key=value pairs from .env (project root) into os.environ."""
    root = Path(__file__).parent.parent
    dotenv = root / ".env"
    if not dotenv.is_file():
        return
    with dotenv.open() as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # Don't override values already set in the environment
            if key and key not in os.environ:
                os.environ[key] = value


_load_dotenv()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LAST_REQUEST: dict[str, float] = {}


def _rate_limited_get(url: str, min_interval: float = 1.0, source: str = "default",
                       headers: dict | None = None) -> Optional[str]:
    """Fetch *url* with a per-source rate limit. Returns body or None on error."""
    now = time.time()
    since = now - _LAST_REQUEST.get(source, 0)
    if since < min_interval:
        time.sleep(min_interval - since)
    _LAST_REQUEST[source] = time.time()

    req = urllib.request.Request(url)
    req.add_header("User-Agent", "bib-checker/1.0 (mailto:user@example.com)")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode("utf-8")
    except Exception:
        return None


def _clean_title(title: str) -> str:
    """Strip LaTeX commands and special chars for use in search queries."""
    # Remove LaTeX commands like \emph{...}, {\em ...}, etc.
    title = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", title)
    title = re.sub(r"\{([^}]*)\}", r"\1", title)
    title = re.sub(r"[^A-Za-z0-9 ]+", " ", title)
    return re.sub(r" +", " ", title).strip()


def _title_similarity(a: str, b: str) -> float:
    """
    Simple word-overlap similarity (Jaccard on lowercased word sets).
    Returns 0..1.
    """
    wa = set(_clean_title(a).lower().split())
    wb = set(_clean_title(b).lower().split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


# ---------------------------------------------------------------------------
# arXiv backend
# ---------------------------------------------------------------------------

class ArxivSearch:
    """Query the arXiv API by paper title."""

    MIN_INTERVAL = 3.0  # seconds between requests (API policy)

    def _query(self, title: str, quoted: bool = True) -> Optional[str]:
        cleaned = _clean_title(title)
        encoded = urllib.parse.quote_plus(cleaned)
        if quoted:
            encoded = f"%22{encoded}%22"
        url = (
            "http://export.arxiv.org/api/query?search_query="
            f"ti:{encoded}&start=0&max_results=3"
        )
        return _rate_limited_get(url, self.MIN_INTERVAL, source="arxiv")

    def _parse(self, xml: str, original_title: str) -> Optional[Paper]:
        try:
            import xml.etree.ElementTree as ET
        except ImportError:
            return None

        ns = {"atom": "http://www.w3.org/2005/Atom",
              "arxiv": "http://arxiv.org/schemas/atom"}

        root = ET.fromstring(xml)
        entries = root.findall("atom:entry", ns)
        if not entries:
            return None

        best: Optional[Paper] = None
        best_sim = 0.0

        for entry in entries:
            title_el = entry.find("atom:title", ns)
            if title_el is None:
                continue
            found_title = re.sub(r"\s+", " ", title_el.text or "").strip()

            sim = _title_similarity(original_title, found_title)
            if sim < 0.6:
                continue
            if sim <= best_sim:
                continue
            best_sim = sim

            id_el = entry.find("atom:id", ns)
            arxiv_url = (id_el.text or "").strip()
            arxiv_id_match = re.search(r"abs/(\d{4}\.\d+)", arxiv_url)
            arxiv_id = arxiv_id_match.group(1) if arxiv_id_match else None

            published_el = entry.find("atom:published", ns)
            date = (published_el.text or "")[:10] if published_el is not None else None

            authors = []
            for author_el in entry.findall("atom:author", ns):
                name_el = author_el.find("atom:name", ns)
                if name_el is not None and name_el.text:
                    authors.append(name_el.text.strip())

            # Check for DOI link (journal_ref)
            doi = None
            doi_el = entry.find("arxiv:doi", ns)
            if doi_el is not None and doi_el.text:
                doi = doi_el.text.strip()

            journal_ref = None
            jr_el = entry.find("arxiv:journal_ref", ns)
            if jr_el is not None and jr_el.text:
                journal_ref = jr_el.text.strip()

            best = Paper(
                title=found_title,
                authors=authors,
                url=arxiv_url,
                date=date,
                doi=doi,
                venue=journal_ref,
                arxiv_id=arxiv_id,
            )

        return best

    def find_by_title(self, title: str) -> Optional[Paper]:
        xml = self._query(title, quoted=True)
        if xml:
            result = self._parse(xml, title)
            if result:
                return result
        # Try without quotes
        xml = self._query(title, quoted=False)
        if xml:
            return self._parse(xml, title)
        return None


# ---------------------------------------------------------------------------
# Semantic Scholar backend
# ---------------------------------------------------------------------------

class SemanticScholarSearch:
    """
    Query the Semantic Scholar Graph API (no API key required for basic use).
    Can find papers published in venues even if they started as arXiv preprints.
    """

    BASE = "https://api.semanticscholar.org/graph/v1/paper/search"
    FIELDS = "title,authors,year,venue,externalIds,publicationVenue,journal,publicationTypes"
    MIN_INTERVAL = 1.0

    def find_by_title(self, title: str) -> Optional[Paper]:
        cleaned = _clean_title(title)
        params = urllib.parse.urlencode({
            "query": cleaned,
            "limit": 3,
            "fields": self.FIELDS,
        })
        url = f"{self.BASE}?{params}"
        body = _rate_limited_get(url, self.MIN_INTERVAL, source="semanticscholar")
        if not body:
            return None

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return None

        papers = data.get("data", [])
        best: Optional[Paper] = None
        best_sim = 0.0

        for p in papers:
            found_title = p.get("title", "")
            sim = _title_similarity(title, found_title)
            if sim < 0.6 or sim <= best_sim:
                continue
            best_sim = sim

            ext_ids = p.get("externalIds", {}) or {}
            doi = ext_ids.get("DOI")
            arxiv_id = ext_ids.get("ArXiv")

            venue = p.get("venue") or ""
            pub_venue = p.get("publicationVenue") or {}
            if not venue and pub_venue:
                venue = pub_venue.get("name", "")

            authors = [a.get("name", "") for a in (p.get("authors") or [])]
            year = p.get("year")

            best = Paper(
                title=found_title,
                authors=authors,
                doi=doi,
                venue=venue,
                year=year,
                arxiv_id=arxiv_id,
                url=f"https://doi.org/{doi}" if doi else None,
            )

        return best


# ---------------------------------------------------------------------------
# CrossRef backend (title search)
# ---------------------------------------------------------------------------

class CrossRefSearch:
    """
    Query the CrossRef REST API by title.
    Returns DOI, venue, year when a strong match is found.
    """

    BASE = "https://api.crossref.org/works"
    MIN_INTERVAL = 1.0

    def find_by_title(self, title: str) -> Optional[Paper]:
        cleaned = _clean_title(title)
        params = urllib.parse.urlencode({
            "query.title": cleaned,
            "rows": 3,
            "select": "title,author,DOI,container-title,published,type",
        })
        url = f"{self.BASE}?{params}"
        body = _rate_limited_get(url, self.MIN_INTERVAL, source="crossref")
        if not body:
            return None

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return None

        items = data.get("message", {}).get("items", [])
        best: Optional[Paper] = None
        best_sim = 0.0

        for item in items:
            titles = item.get("title", [])
            found_title = titles[0] if titles else ""
            sim = _title_similarity(title, found_title)
            if sim < 0.65 or sim <= best_sim:
                continue
            best_sim = sim

            doi = item.get("DOI", "")
            container = item.get("container-title", [])
            venue = container[0] if container else ""

            pub = item.get("published", {})
            date_parts = pub.get("date-parts", [[]])[0]
            year = date_parts[0] if date_parts else None

            raw_authors = item.get("author", [])
            authors = []
            for a in raw_authors:
                given = a.get("given", "")
                family = a.get("family", "")
                authors.append(f"{given} {family}".strip())

            best = Paper(
                title=found_title,
                authors=authors,
                doi=doi,
                venue=venue,
                year=year,
                url=f"https://doi.org/{doi}" if doi else None,
            )

        return best


# ---------------------------------------------------------------------------
# Perplexity AI backend (requires PERPLEXITY_API_KEY env var)
# ---------------------------------------------------------------------------

class PerplexitySearch:
    """
    Use the Perplexity AI API to find publication metadata for a paper.

    Set the PERPLEXITY_API_KEY environment variable to enable this backend.
    The API key can be obtained at https://www.perplexity.ai/settings/api.

    Perplexity searches the live web (including Google Scholar, Semantic
    Scholar, publisher sites, DBLP, etc.) and can find venue/DOI info for
    papers that other structured APIs miss.

    Because LLMs can hallucinate, every result from this backend is passed
    through DuckDuckGoVerifier before being accepted.
    """

    API_URL = "https://api.perplexity.ai/chat/completions"
    MODEL = "sonar"  # web-search enabled model
    MIN_INTERVAL = 2.0

    def __init__(self):
        self.api_key: Optional[str] = os.environ.get("PERPLEXITY_API_KEY")

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def find_by_title(self, title: str) -> Optional[Paper]:
        if not self.api_key:
            return None

        prompt = (
            f'Find the published venue for this academic paper: "{_clean_title(title)}"\n\n'
            "Return ONLY a JSON object with these fields (use null for unknown):\n"
            '{"title": "...", "venue": "...", "year": 1234, "doi": "...", '
            '"authors": ["Last, First", ...], "arxiv_id": "2401.12345"}\n\n'
            "The venue should be the conference name or journal name where it was "
            "formally published. If it is only on arXiv, set venue to null. "
            "Do not include any explanation, just the JSON."
        )

        payload = json.dumps({
            "model": self.MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": 300,
        }).encode("utf-8")

        req = urllib.request.Request(
            self.API_URL,
            data=payload,
            method="POST",
        )
        req.add_header("Authorization", f"Bearer {self.api_key}")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        req.add_header("User-Agent", "bib-checker/1.0")

        # Rate limit
        now = time.time()
        since = now - _LAST_REQUEST.get("perplexity", 0)
        if since < self.MIN_INTERVAL:
            time.sleep(self.MIN_INTERVAL - since)
        _LAST_REQUEST["perplexity"] = time.time()

        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = resp.read().decode("utf-8")
        except Exception:
            return None

        try:
            data = json.loads(body)
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, json.JSONDecodeError):
            return None

        # Extract JSON from content (may have markdown fences)
        json_match = re.search(r"\{[\s\S]+\}", content)
        if not json_match:
            return None
        try:
            info = json.loads(json_match.group(0))
        except json.JSONDecodeError:
            return None

        found_title = info.get("title") or ""
        if found_title and _title_similarity(title, found_title) < 0.5:
            return None  # likely hallucinated

        venue = info.get("venue") or ""
        doi = info.get("doi") or ""
        year = info.get("year")
        arxiv_id = info.get("arxiv_id") or ""
        authors = info.get("authors") or []

        # doi sometimes comes back as a full URL
        if doi.startswith("https://doi.org/"):
            doi = doi[len("https://doi.org/"):]

        return Paper(
            title=found_title or title,
            authors=authors if isinstance(authors, list) else [],
            doi=doi or None,
            venue=venue or None,
            year=int(year) if year else None,
            arxiv_id=arxiv_id or None,
            url=f"https://doi.org/{doi}" if doi else None,
        )


# ---------------------------------------------------------------------------
# DuckDuckGo verification – confirm a paper actually exists on the web
# ---------------------------------------------------------------------------

class DuckDuckGoVerifier:
    """
    Use DuckDuckGo's Instant Answer API to verify that a paper (title + venue)
    actually appears in search results.  This is a lightweight sanity check
    to guard against hallucinations from Perplexity or other LLM backends.

    The Instant Answer API is free and requires no API key.
    If we get zero results we fall back to a raw HTML scrape of the first
    DuckDuckGo results page (limited, but better than nothing).
    """

    IA_URL = "https://api.duckduckgo.com/"
    MIN_INTERVAL = 1.5

    def _ia_query(self, query: str) -> Optional[str]:
        params = urllib.parse.urlencode({
            "q": query,
            "format": "json",
            "no_redirect": "1",
            "no_html": "1",
            "skip_disambig": "1",
        })
        url = f"{self.IA_URL}?{params}"
        return _rate_limited_get(url, self.MIN_INTERVAL, source="ddg_ia")

    def _html_query(self, query: str) -> Optional[str]:
        """Fallback: fetch plain DuckDuckGo HTML results page."""
        params = urllib.parse.urlencode({"q": query, "kl": "us-en"})
        url = f"https://html.duckduckgo.com/html/?{params}"
        return _rate_limited_get(url, self.MIN_INTERVAL, source="ddg_html")

    def verify(self, title: str, doi: Optional[str] = None,
               venue: Optional[str] = None) -> bool:
        """
        Return True if the paper is found via DuckDuckGo, False otherwise.

        Strategy:
        1. Search by DOI (most precise).
        2. Search by title + venue.
        3. Search by title alone.
        """
        cleaned = _clean_title(title)

        queries: list[str] = []
        if doi:
            queries.append(doi)
        if venue:
            queries.append(f"{cleaned} {venue}")
        queries.append(cleaned)

        for query in queries:
            body = self._ia_query(query)
            if body:
                try:
                    data = json.loads(body)
                    # DuckDuckGo returns results in RelatedTopics or AbstractURL
                    if data.get("AbstractURL") or data.get("RelatedTopics"):
                        abstract_text = data.get("AbstractText", "")
                        abstract_url = data.get("AbstractURL", "")
                        related = data.get("RelatedTopics", [])
                        if abstract_url or related:
                            return True
                except json.JSONDecodeError:
                    pass

            # HTML fallback: look for title words in raw results
            html = self._html_query(query)
            if html:
                title_words = [w.lower() for w in cleaned.split() if len(w) > 4]
                found = sum(1 for w in title_words if w in html.lower())
                if found >= max(2, len(title_words) // 2):
                    return True

        return False


# ---------------------------------------------------------------------------
# Combined lookup
# ---------------------------------------------------------------------------

class PublicationLookup:
    """
    Try multiple backends in order. Returns the best result with venue info,
    favouring results that have a DOI (published) over arXiv-only.

    Pipeline:
    1. Semantic Scholar  (structured API, reliable, free)
    2. CrossRef          (DOI database, very reliable for published papers)
    3. arXiv             (preprint server; also has journal_ref / DOI sometimes)
    4. Perplexity AI     (web search + LLM, great recall; requires API key)
       └→ DuckDuckGo     (verifies Perplexity results to catch hallucinations)
    """

    def __init__(self, verbose: bool = False, perplexity_api_key: Optional[str] = None):
        self.arxiv = ArxivSearch()
        self.s2 = SemanticScholarSearch()
        self.crossref = CrossRefSearch()
        self.perplexity = PerplexitySearch()
        self.ddg = DuckDuckGoVerifier()
        self.verbose = verbose

        # Allow explicit key override (e.g. from CLI --perplexity-key flag)
        if perplexity_api_key:
            self.perplexity.api_key = perplexity_api_key

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(f"  [search] {msg}")

    def _is_published(self, paper: Optional[Paper]) -> bool:
        """Return True if the Paper represents a formally published work."""
        if not paper:
            return False
        if paper.doi:
            return True
        if paper.venue and "arxiv" not in paper.venue.lower():
            return True
        return False

    def find_published(self, title: str) -> dict:
        """
        Return a dict with keys:
          - arxiv_result: Paper or None
          - published_result: Paper or None  (has DOI / non-arXiv venue)
          - best: Paper or None
          - verified: bool  (True if published_result was confirmed by DuckDuckGo)
        """
        arxiv_result: Optional[Paper] = None
        published_result: Optional[Paper] = None
        verified = False

        # 1. Semantic Scholar (most likely to know about final venue)
        self._log(f"Semantic Scholar: '{title[:60]}'")
        ss = self.s2.find_by_title(title)
        if ss:
            self._log(f"  -> found: '{ss.title}' venue={ss.venue} doi={ss.doi}")
            if self._is_published(ss):
                published_result = ss
            elif ss.arxiv_id:
                arxiv_result = ss

        # 2. CrossRef for DOI confirmation
        if not published_result:
            self._log(f"CrossRef: '{title[:60]}'")
            cr = self.crossref.find_by_title(title)
            if cr and cr.doi:
                self._log(f"  -> found: '{cr.title}' doi={cr.doi}")
                published_result = cr

        # 3. arXiv as fallback / extra info
        if not arxiv_result:
            self._log(f"arXiv: '{title[:60]}'")
            ax = self.arxiv.find_by_title(title)
            if ax:
                self._log(f"  -> found: arxiv:{ax.arxiv_id} doi={ax.doi}")
                arxiv_result = ax
                if ax.doi and not published_result:
                    published_result = ax

        # 4. Perplexity AI (web search + LLM) – only if no published result yet
        if not published_result and self.perplexity.available:
            self._log(f"Perplexity: '{title[:60]}'")
            px = self.perplexity.find_by_title(title)
            if px:
                self._log(
                    f"  -> Perplexity: title='{px.title[:50]}' "
                    f"venue={px.venue} doi={px.doi}"
                )
                if self._is_published(px):
                    # Verify via DuckDuckGo before accepting
                    self._log(
                        f"  -> Verifying via DuckDuckGo: doi={px.doi} venue={px.venue}"
                    )
                    ok = self.ddg.verify(title, doi=px.doi, venue=px.venue)
                    self._log(f"  -> DuckDuckGo verification: {'PASS ✓' if ok else 'FAIL ✗'}")
                    if ok:
                        published_result = px
                        verified = True
                    else:
                        self._log(
                            "  -> Perplexity result NOT verified by DuckDuckGo – discarding"
                        )
                elif px.arxiv_id and not arxiv_result:
                    # Even if not published, useful arXiv info
                    # Still verify the arxiv id makes sense
                    ok = self.ddg.verify(title)
                    if ok:
                        arxiv_result = px
        elif not self.perplexity.available:
            self._log("Perplexity: skipped (PERPLEXITY_API_KEY not set)")

        # 5. DuckDuckGo verify the non-Perplexity published result if not yet verified
        if published_result and not verified:
            self._log(
                f"DuckDuckGo verify: '{title[:50]}' doi={published_result.doi}"
            )
            ok = self.ddg.verify(
                title, doi=published_result.doi, venue=published_result.venue
            )
            verified = ok
            self._log(f"  -> DuckDuckGo: {'PASS ✓' if ok else 'soft fail (kept)'}")
            # We keep non-Perplexity results even on DDG failure because structured
            # APIs (S2, CrossRef) are already trustworthy. DDG is best-effort here.

        best = published_result or arxiv_result
        return {
            "arxiv_result": arxiv_result,
            "published_result": published_result,
            "best": best,
            "verified": verified,
        }
