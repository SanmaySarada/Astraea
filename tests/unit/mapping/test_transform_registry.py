"""Tests for the transform registry module."""

from __future__ import annotations

import pytest

from astraea.mapping.transform_registry import (
    AVAILABLE_TRANSFORMS,
    get_transform,
    list_transforms,
)


class TestListTransforms:
    def test_returns_6_transforms(self):
        result = list_transforms()
        assert len(result) == 6

    def test_returns_sorted_list(self):
        result = list_transforms()
        assert result == sorted(result)

    def test_expected_names_present(self):
        result = list_transforms()
        expected = {
            "sas_date_to_iso",
            "sas_datetime_to_iso",
            "parse_string_date_to_iso",
            "format_partial_iso8601",
            "generate_usubjid",
            "generate_usubjid_column",
        }
        assert set(result) == expected


class TestGetTransform:
    def test_existing_transform_found(self):
        fn = get_transform("sas_date_to_iso")
        assert fn is not None

    def test_nonexistent_returns_none(self):
        assert get_transform("nonexistent_transform") is None

    def test_sas_date_to_iso_callable(self):
        fn = get_transform("sas_date_to_iso")
        assert callable(fn)
        assert fn(0.0) == "1960-01-01"

    def test_generate_usubjid_callable(self):
        fn = get_transform("generate_usubjid")
        assert callable(fn)
        result = fn("STUDY01", "SITE01", "001")
        assert result == "STUDY01-SITE01-001"

    @pytest.mark.parametrize("name", list(AVAILABLE_TRANSFORMS.keys()))
    def test_all_registered_transforms_callable(self, name: str):
        fn = get_transform(name)
        assert fn is not None
        assert callable(fn)
