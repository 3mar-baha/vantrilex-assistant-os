"""Scaffold smoke tests: the documentation contract holds."""

import scripts.docs_guard as dg


def test_all_canonical_files_present():
    assert dg.missing_files() == []


def test_canonical_set_is_exactly_16():
    assert len(dg.CANONICAL_FILES) == 16
