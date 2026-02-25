"""
Test configuration: isolate venues.json writes so tests don't mutate
the real venues.json or pollute each other via in-memory CANONICAL_STRINGS /
VENUE_ALIASES state.
"""

import copy
import pytest
import bib_checker.strings as _strings


# Take a snapshot of the original tables *before* any test modifies them.
_ORIG_CANONICAL = copy.copy(_strings.CANONICAL_STRINGS)
_ORIG_ALIASES = copy.copy(_strings.VENUE_ALIASES)


@pytest.fixture(autouse=True)
def _reset_venue_tables():
    """Restore the canonical venue tables to their original state after each test."""
    yield
    _strings.CANONICAL_STRINGS.clear()
    _strings.CANONICAL_STRINGS.update(_ORIG_CANONICAL)
    _strings.VENUE_ALIASES.clear()
    _strings.VENUE_ALIASES.update(_ORIG_ALIASES)
