"""Unit tests for profiler EDC column detection and date disambiguation (no Fakedata dependency)."""

from __future__ import annotations

from astraea.profiling.profiler import (
    EDC_SYSTEM_COLUMNS,
    _is_edc_column,
    _is_potential_string_date_column,
    detect_date_format,
)


class TestEDCColumnSet:

    def test_edc_columns_count(self):
        assert len(EDC_SYSTEM_COLUMNS) == 29

    def test_edc_correct_spelling(self):
        assert "studyenvsitenumber" in EDC_SYSTEM_COLUMNS


class TestIsEDCColumn:

    def test_subject_detected(self):
        assert _is_edc_column("Subject") is True

    def test_subject_lowercase(self):
        assert _is_edc_column("subject") is True

    def test_sitenumber_detected(self):
        assert _is_edc_column("SiteNumber") is True

    def test_site_detected(self):
        assert _is_edc_column("Site") is True

    def test_sitegroup_detected(self):
        assert _is_edc_column("SiteGroup") is True

    def test_studysiteid_detected(self):
        assert _is_edc_column("StudySiteId") is True

    def test_foldername_detected(self):
        assert _is_edc_column("FolderName") is True

    def test_clinical_column_not_edc(self):
        assert _is_edc_column("AETERM") is False


class TestDetectDateFormatDisambiguation:
    """Tests for slash date DD/MM/YYYY vs MM/DD/YYYY disambiguation."""

    def test_dd_mm_yyyy_first_exceeds_12(self):
        """First field > 12 unambiguously identifies DD/MM/YYYY."""
        assert detect_date_format(["15/03/2022", "25/12/2021"]) == "DD/MM/YYYY"

    def test_mm_dd_yyyy_second_exceeds_12(self):
        """Second field > 12 unambiguously identifies MM/DD/YYYY."""
        assert detect_date_format(["03/15/2022", "12/25/2021"]) == "MM/DD/YYYY"

    def test_ambiguous_defaults_dd_mm_yyyy(self):
        """When both fields <= 12, default to DD/MM/YYYY per project convention."""
        assert detect_date_format(["03/04/2022", "01/02/2021"]) == "DD/MM/YYYY"

    def test_non_slash_patterns_still_work(self):
        """DD Mon YYYY and other patterns should be unaffected."""
        assert detect_date_format(["30 Mar 2022"]) == "DD Mon YYYY"


class TestIsPotentialStringDateColumn:
    """Tests for broadened _RAW column detection."""

    def test_visit_raw_detected(self):
        """_RAW columns without DAT should now be detected."""
        assert _is_potential_string_date_column("VISIT_RAW") is True

    def test_enrl_raw_detected(self):
        assert _is_potential_string_date_column("ENRL_RAW") is True

    def test_brthdat_raw_still_works(self):
        """Original DAT+_RAW columns should still work."""
        assert _is_potential_string_date_column("BRTHDAT_RAW") is True

    def test_age_not_detected(self):
        """Non _RAW columns should not be detected."""
        assert _is_potential_string_date_column("AGE") is False

    def test_rawdata_not_detected(self):
        """RAWDATA has RAW but not _RAW (no underscore prefix)."""
        assert _is_potential_string_date_column("RAWDATA") is False

    def test_case_insensitive(self):
        """Detection should be case insensitive."""
        assert _is_potential_string_date_column("visit_raw") is True
