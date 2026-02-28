"""Tests for pre-mapped SDTM dataset detection (MED-29).

Validates that detect_sdtm_format() correctly identifies datasets
that are already in SDTM Findings format (e.g., lab_results, ecg_results).
"""

from __future__ import annotations

import pytest

from astraea.models.profiling import DatasetProfile, VariableProfile
from astraea.profiling.profiler import detect_sdtm_format


def _make_profile(
    col_names: list[str],
    *,
    edc_cols: set[str] | None = None,
    domain_samples: list[str] | None = None,
) -> DatasetProfile:
    """Create a minimal DatasetProfile for testing.

    Args:
        col_names: List of column names to include.
        edc_cols: Set of column names that are EDC system columns.
        domain_samples: Sample values for the DOMAIN column (if present).
    """
    edc_cols = edc_cols or set()
    variables = []
    for name in col_names:
        sample_vals: list[str] = []
        if name.upper() == "DOMAIN" and domain_samples:
            sample_vals = domain_samples
        variables.append(
            VariableProfile(
                name=name,
                label="",
                dtype="character",
                n_total=100,
                n_missing=0,
                n_unique=10,
                missing_pct=0.0,
                sample_values=sample_vals,
                is_edc_column=name in edc_cols,
            )
        )
    return DatasetProfile(
        filename="test.sas7bdat",
        row_count=100,
        col_count=len(col_names),
        variables=variables,
    )


class TestDetectSDTMFormat:
    """Tests for detect_sdtm_format()."""

    def test_detects_sdtm_lb_format(self):
        """LB Findings columns should be detected as SDTM."""
        profile = _make_profile(
            ["LBTESTCD", "LBTEST", "LBORRES", "LBSTRESC", "LBSTRESN", "LBORRESU"]
        )
        assert detect_sdtm_format(profile) is True

    def test_detects_sdtm_eg_format(self):
        """EG Findings columns should be detected as SDTM."""
        profile = _make_profile(
            ["EGTESTCD", "EGTEST", "EGORRES", "EGSTRESC", "EGSTRESN"]
        )
        assert detect_sdtm_format(profile) is True

    def test_detects_sdtm_vs_format(self):
        """VS Findings columns should be detected as SDTM."""
        profile = _make_profile(
            ["VSTESTCD", "VSTEST", "VSORRES", "VSSTRESC", "VSSTRESN"]
        )
        assert detect_sdtm_format(profile) is True

    def test_detects_by_domain_column(self):
        """DOMAIN column with valid SDTM code triggers detection."""
        profile = _make_profile(
            ["DOMAIN", "USUBJID", "AETERM"],
            domain_samples=["AE"],
        )
        assert detect_sdtm_format(profile) is True

    def test_false_for_raw_edc_data(self):
        """Raw EDC data without SDTM patterns should return False."""
        profile = _make_profile(
            ["projectid", "SubjectId", "AETERM", "AESTDAT", "AEENDAT"],
            edc_cols={"projectid", "SubjectId"},
        )
        assert detect_sdtm_format(profile) is False

    def test_false_when_only_two_indicators(self):
        """Below threshold (< 3 matches) should return False."""
        profile = _make_profile(["LBTESTCD", "LBTEST", "RESULT", "UNITS"])
        assert detect_sdtm_format(profile) is False

    def test_ignores_edc_columns(self):
        """EDC columns should not count toward SDTM detection."""
        profile = _make_profile(
            ["LBTESTCD", "LBTEST", "LBORRES", "LBSTRESC", "LBSTRESN"],
            edc_cols={"LBTESTCD", "LBTEST", "LBORRES", "LBSTRESC", "LBSTRESN"},
        )
        assert detect_sdtm_format(profile) is False

    def test_domain_column_with_invalid_code(self):
        """DOMAIN column with non-SDTM values should not trigger detection."""
        profile = _make_profile(
            ["DOMAIN", "USUBJID", "VALUE"],
            domain_samples=["CUSTOM_FORM", "OTHER"],
        )
        assert detect_sdtm_format(profile) is False

    def test_three_matches_is_threshold(self):
        """Exactly 3 matches should trigger detection."""
        profile = _make_profile(["LBTESTCD", "LBTEST", "LBORRES"])
        assert detect_sdtm_format(profile) is True

    def test_model_has_preformatted_field(self):
        """DatasetProfile should have is_sdtm_preformatted field."""
        profile = DatasetProfile(
            filename="test.sas7bdat",
            row_count=0,
            col_count=0,
        )
        assert hasattr(profile, "is_sdtm_preformatted")
        assert profile.is_sdtm_preformatted is False
