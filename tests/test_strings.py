"""
Unit tests for bib_checker.strings – venue alias lookup and canonicalization.
"""

import pytest

from bib_checker.strings import (
    CANONICAL_STRINGS,
    VENUE_ALIASES,
    lookup_venue,
    normalize_venue_key,
)


# ---------------------------------------------------------------------------
# normalize_venue_key
# ---------------------------------------------------------------------------

class TestNormalizeVenueKey:
    def test_lowercased(self):
        assert normalize_venue_key("CVPR") == "cvpr"

    def test_collapses_whitespace(self):
        assert normalize_venue_key("  IEEE   TPAMI  ") == "ieee tpami"

    def test_already_normalized(self):
        assert normalize_venue_key("iccv") == "iccv"


# ---------------------------------------------------------------------------
# lookup_venue – canonical key matches
# ---------------------------------------------------------------------------

class TestLookupVenueCanonicalKeys:
    """Bare canonical keys should resolve to themselves."""

    @pytest.mark.parametrize("key", [
        "CVPR", "ICCV", "ECCV", "NIPS", "ICML", "ICLR",
        "AAAI", "IJCAI", "AISTATS", "PAMI", "IJCV", "TIP",
        "TVCG", "TMM", "TCSVT", "TOG", "CGF", "WACV",
        "SIGGRAPH", "SIGGRAPHASIA", "EGSR", "ACMMM",
        "ICASSP", "ICIP", "BMVC", "ICPR", "TDV", "ARXIV",
    ])
    def test_canonical_key_resolves(self, key):
        canonical_key, display = lookup_venue(key)
        assert canonical_key == key
        assert display == CANONICAL_STRINGS[key]


# ---------------------------------------------------------------------------
# lookup_venue – alias variants
# ---------------------------------------------------------------------------

class TestLookupVenueAliases:
    """Long-form / variant spellings should map to a canonical key."""

    @pytest.mark.parametrize("raw,expected_key", [
        # CVPR variants
        ("IEEE Conf. Comput. Vis. Pattern Recog.", "CVPR"),
        ("IEEE Conference on Computer Vision and Pattern Recognition", "CVPR"),
        ("Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition", "CVPR"),
        ("Computer Vision and Pattern Recognition", "CVPR"),
        # ICCV variants
        ("Int. Conf. Comput. Vis.", "ICCV"),
        ("International Conference on Computer Vision", "ICCV"),
        ("Proceedings of the IEEE/CVF International Conference on Computer Vision", "ICCV"),
        # ECCV variants
        ("Eur. Conf. Comput. Vis.", "ECCV"),
        ("European Conference on Computer Vision", "ECCV"),
        ("Proceedings of the European Conference on Computer Vision", "ECCV"),
        # NeurIPS variants
        ("Adv. Neural Inform. Process. Syst.", "NIPS"),
        ("Advances in Neural Information Processing Systems", "NIPS"),
        ("NeurIPS", "NIPS"),
        ("nips", "NIPS"),
        # ICML variants
        ("International Conference on Machine Learning", "ICML"),
        # ICLR variants
        ("International Conference on Learning Representations", "ICLR"),
        ("Int. Conf. Learn. Represent.", "ICLR"),
        # AAAI variants
        ("AAAI Conference on Artificial Intelligence", "AAAI"),
        ("Proceedings of the AAAI Conference on Artificial Intelligence", "AAAI"),
        # PAMI variants
        ("IEEE Trans. Pattern Anal. Mach. Intell.", "PAMI"),
        ("IEEE Transactions on Pattern Analysis and Machine Intelligence", "PAMI"),
        ("IEEE TPAMI", "PAMI"),
        # IJCV variants
        ("Int. J. Comput. Vis.", "IJCV"),
        ("International Journal of Computer Vision", "IJCV"),
        # WACV variants
        ("Proceedings of the IEEE/CVF Winter Conference on Applications of Computer Vision", "WACV"),
        ("IEEE/CVF Winter Conference on Applications of Computer Vision", "WACV"),
        # AISTATS
        ("International Conference on Artificial Intelligence and Statistics", "AISTATS"),
        # TOG / SIGGRAPH
        ("ACM Transactions on Graphics", "TOG"),
        ("ACM Transactions on Graphics (SIGGRAPH)", "SIGGRAPH"),
        ("ACM Transactions on Graphics (SIGGRAPH Asia)", "SIGGRAPHASIA"),
        # TIP
        ("IEEE Trans. Image Process.", "TIP"),
        ("IEEE Transactions on Image Processing", "TIP"),
        # TVCG
        ("IEEE Transactions on Visualization and Computer Graphics", "TVCG"),
        # Pattern Recognition
        ("Pattern Recognition", "PR"),
        # arXiv
        ("arxiv", "ARXIV"),
        ("arXiv preprint", "ARXIV"),
        # CGF
        ("Computer Graphics Forum", "CGF"),
    ])
    def test_alias_resolves(self, raw, expected_key):
        canonical_key, display = lookup_venue(raw)
        assert canonical_key == expected_key, (
            f"Expected '{expected_key}' for '{raw}', got '{canonical_key}'"
        )
        assert display == CANONICAL_STRINGS[expected_key]

    @pytest.mark.parametrize("raw,expected_key", [
        # Case-insensitive alias matching
        ("ieee conference on computer vision and pattern recognition", "CVPR"),
        ("EUROPEAN CONFERENCE ON COMPUTER VISION", "ECCV"),
        ("international conference on machine learning", "ICML"),
    ])
    def test_alias_case_insensitive(self, raw, expected_key):
        canonical_key, _ = lookup_venue(raw)
        assert canonical_key == expected_key


# ---------------------------------------------------------------------------
# lookup_venue – no match for completely unknown venues
# ---------------------------------------------------------------------------

class TestLookupVenueNoMatch:
    @pytest.mark.parametrize("raw", [
        "Journal of Imaginary Science",
        "Annual Conference on Papers That Were Never Written",
        "Biometrika",
        "SIAM Journal on Imaging Sciences",
        "Some Completely Unknown Workshop",
    ])
    def test_unknown_venue_returns_none(self, raw):
        key, display = lookup_venue(raw)
        assert key is None
        assert display is None


# ---------------------------------------------------------------------------
# CANONICAL_STRINGS completeness
# ---------------------------------------------------------------------------

class TestCanonicalStrings:
    def test_all_aliases_point_to_existing_canonical_keys(self):
        """Every alias target must exist in CANONICAL_STRINGS."""
        for raw, target in VENUE_ALIASES.items():
            assert target in CANONICAL_STRINGS, (
                f"Alias '{raw}' → '{target}' but '{target}' not in CANONICAL_STRINGS"
            )

    def test_canonical_keys_are_uppercase(self):
        for key in CANONICAL_STRINGS:
            assert key == key.upper(), f"Canonical key '{key}' should be uppercase"

    def test_no_empty_display_values(self):
        for key, display in CANONICAL_STRINGS.items():
            assert display, f"Canonical key '{key}' has empty display value"
