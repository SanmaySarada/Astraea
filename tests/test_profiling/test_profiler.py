"""Tests for dataset profiler with EDC column detection.

Integration tests that profile real .sas7bdat files from the Fakedata/ directory.
"""

from pathlib import Path

import pytest

from astraea.io.sas_reader import read_sas_with_metadata
from astraea.models.profiling import DatasetProfile, VariableProfile
from astraea.profiling.profiler import detect_date_format, profile_dataset

FAKEDATA_DIR = Path(__file__).parent.parent.parent / "Fakedata"


@pytest.fixture
def dm_profile() -> DatasetProfile:
    """Profile of dm.sas7bdat."""
    df, meta = read_sas_with_metadata(FAKEDATA_DIR / "dm.sas7bdat")
    return profile_dataset(df, meta)


@pytest.fixture
def ae_profile() -> DatasetProfile:
    """Profile of ae.sas7bdat."""
    df, meta = read_sas_with_metadata(FAKEDATA_DIR / "ae.sas7bdat")
    return profile_dataset(df, meta)


class TestProfileDataset:
    """Tests for profile_dataset function."""

    def test_returns_dataset_profile(self, dm_profile: DatasetProfile) -> None:
        assert isinstance(dm_profile, DatasetProfile)

    def test_row_count_matches(self, dm_profile: DatasetProfile) -> None:
        df, meta = read_sas_with_metadata(FAKEDATA_DIR / "dm.sas7bdat")
        assert dm_profile.row_count == len(df)

    def test_col_count_matches(self, dm_profile: DatasetProfile) -> None:
        df, meta = read_sas_with_metadata(FAKEDATA_DIR / "dm.sas7bdat")
        assert dm_profile.col_count == meta.col_count

    def test_variables_populated(self, dm_profile: DatasetProfile) -> None:
        assert len(dm_profile.variables) > 0
        assert all(isinstance(v, VariableProfile) for v in dm_profile.variables)

    def test_n_total_equals_row_count(self, dm_profile: DatasetProfile) -> None:
        """Every variable should have n_total equal to the dataset row count."""
        for var in dm_profile.variables:
            assert var.n_total == dm_profile.row_count, (
                f"Variable {var.name} has n_total={var.n_total}, "
                f"expected {dm_profile.row_count}"
            )

    def test_missing_pct_in_range(self, dm_profile: DatasetProfile) -> None:
        """Missing percentage must be between 0 and 100 for all variables."""
        for var in dm_profile.variables:
            assert 0.0 <= var.missing_pct <= 100.0, (
                f"Variable {var.name} has missing_pct={var.missing_pct}"
            )

    def test_n_missing_consistent_with_pct(self, dm_profile: DatasetProfile) -> None:
        """n_missing / n_total * 100 should approximately equal missing_pct."""
        for var in dm_profile.variables:
            if var.n_total > 0:
                expected_pct = round(var.n_missing / var.n_total * 100, 2)
                assert abs(var.missing_pct - expected_pct) < 0.1, (
                    f"Variable {var.name}: missing_pct={var.missing_pct} vs "
                    f"expected={expected_pct}"
                )


class TestEDCColumnDetection:
    """Tests for EDC system column identification."""

    def test_edc_columns_detected(self, dm_profile: DatasetProfile) -> None:
        """DM dataset should have EDC system columns."""
        assert len(dm_profile.edc_columns) > 0

    def test_known_edc_columns_present(self, dm_profile: DatasetProfile) -> None:
        """Check that well-known EDC columns are detected (case-insensitive check)."""
        edc_lower = {c.lower() for c in dm_profile.edc_columns}
        # These columns exist in every Fakedata/ dataset
        expected_edc = {"projectid", "project", "studyid", "environmentname"}
        found = expected_edc & edc_lower
        assert len(found) >= 3, (
            f"Expected at least 3 of {expected_edc} but found {found}"
        )

    def test_clinical_columns_not_edc(self, dm_profile: DatasetProfile) -> None:
        """Clinical columns like SEX, AGE should NOT be flagged as EDC."""
        edc_lower = {c.lower() for c in dm_profile.edc_columns}
        clinical = {"sex", "age", "ethnic", "height"}
        overlap = clinical & edc_lower
        assert len(overlap) == 0, f"Clinical columns wrongly flagged as EDC: {overlap}"

    def test_variable_level_edc_flag(self, dm_profile: DatasetProfile) -> None:
        """Individual VariableProfile.is_edc_column should match aggregate list."""
        edc_from_vars = [v.name for v in dm_profile.variables if v.is_edc_column]
        assert set(edc_from_vars) == set(dm_profile.edc_columns)


class TestDateDetection:
    """Tests for date variable detection."""

    def test_dm_has_date_variables(self, dm_profile: DatasetProfile) -> None:
        """DM dataset has DATETIME format columns (RecordDate, MinCreated, etc.)."""
        assert len(dm_profile.date_variables) > 0

    def test_datetime_format_detected(self, dm_profile: DatasetProfile) -> None:
        """SAS DATETIME columns should be detected with SAS_DATETIME format."""
        datetime_vars = [
            v for v in dm_profile.variables
            if v.is_date and v.detected_date_format == "SAS_DATETIME"
        ]
        assert len(datetime_vars) > 0

    def test_ae_has_raw_string_dates(self, ae_profile: DatasetProfile) -> None:
        """AE dataset has _RAW date columns with 'DD Mon YYYY' format."""
        raw_date_vars = [
            v for v in ae_profile.variables
            if v.is_date and v.detected_date_format == "DD Mon YYYY"
        ]
        assert len(raw_date_vars) > 0, (
            "Expected at least one _RAW date column with 'DD Mon YYYY' format. "
            f"Date vars found: {ae_profile.date_variables}"
        )

    def test_ae_has_sas_datetime_columns(self, ae_profile: DatasetProfile) -> None:
        """AE dataset has SAS DATETIME columns (AESTDAT, AEENDAT, etc.)."""
        sas_dt_vars = [
            v for v in ae_profile.variables
            if v.is_date and v.detected_date_format == "SAS_DATETIME"
        ]
        assert len(sas_dt_vars) > 0

    def test_date_variables_aggregate_matches(self, ae_profile: DatasetProfile) -> None:
        """date_variables list should match variables with is_date=True."""
        date_from_vars = [v.name for v in ae_profile.variables if v.is_date]
        assert set(date_from_vars) == set(ae_profile.date_variables)


class TestDetectDateFormat:
    """Tests for the detect_date_format helper."""

    def test_dd_mon_yyyy(self) -> None:
        samples = ["30 Mar 2022", "24 May 2022", "23 Jul 2022"]
        assert detect_date_format(samples) == "DD Mon YYYY"

    def test_yyyy_mm_dd(self) -> None:
        samples = ["2022-03-30", "2022-05-24", "2022-07-23"]
        assert detect_date_format(samples) == "YYYY-MM-DD"

    def test_dd_mon_yyyy_with_dash(self) -> None:
        samples = ["30-Mar-2022", "24-May-2022", "23-Jul-2022"]
        assert detect_date_format(samples) == "DD-Mon-YYYY"

    def test_empty_samples_returns_none(self) -> None:
        assert detect_date_format([]) is None

    def test_non_date_returns_none(self) -> None:
        samples = ["hello", "world", "123abc"]
        assert detect_date_format(samples) is None

    def test_mixed_values_with_majority_dates(self) -> None:
        """If >50% match, should still detect."""
        samples = ["30 Mar 2022", "24 May 2022", "unknown"]
        assert detect_date_format(samples) == "DD Mon YYYY"


class TestSampleAndTopValues:
    """Tests for sample_values and top_values computation."""

    def test_sample_values_populated(self, dm_profile: DatasetProfile) -> None:
        """Variables with non-null data should have sample values."""
        non_missing_vars = [
            v for v in dm_profile.variables if v.n_missing < v.n_total
        ]
        for var in non_missing_vars:
            assert len(var.sample_values) > 0, (
                f"Variable {var.name} has data but no sample values"
            )

    def test_sample_values_max_ten(self, dm_profile: DatasetProfile) -> None:
        """Sample values should have at most 10 entries."""
        for var in dm_profile.variables:
            assert len(var.sample_values) <= 10

    def test_top_values_for_low_cardinality(self, dm_profile: DatasetProfile) -> None:
        """Variables with few unique values should have top_values."""
        low_card = [
            v for v in dm_profile.variables
            if 1 <= v.n_unique <= 10 and v.n_missing < v.n_total
        ]
        for var in low_card:
            assert len(var.top_values) > 0, (
                f"Variable {var.name} (n_unique={var.n_unique}) has no top_values"
            )
