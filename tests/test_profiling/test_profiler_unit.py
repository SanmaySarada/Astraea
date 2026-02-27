"""Unit tests for profiler EDC column detection (no Fakedata dependency)."""

from __future__ import annotations

from astraea.profiling.profiler import EDC_SYSTEM_COLUMNS, _is_edc_column


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
