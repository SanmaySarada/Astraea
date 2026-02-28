"""Tests for eCRF form-to-dataset matching by variable name overlap."""

from __future__ import annotations

import pytest

from astraea.models.ecrf import ECRFField, ECRFForm
from astraea.models.profiling import DatasetProfile, VariableProfile
from astraea.parsing.form_dataset_matcher import (
    get_unmatched_datasets,
    get_unmatched_forms,
    match_all_forms,
    match_form_to_datasets,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_field(name: str) -> ECRFField:
    """Create a minimal ECRFField for testing."""
    return ECRFField(
        field_number=1,
        field_name=name,
        data_type="$25",
        sas_label=f"Label for {name}",
    )


def _make_profile(
    filename: str,
    clinical_vars: list[str],
    edc_vars: list[str] | None = None,
) -> DatasetProfile:
    """Create a minimal DatasetProfile for testing."""
    variables: list[VariableProfile] = []
    for var in clinical_vars:
        variables.append(
            VariableProfile(
                name=var,
                dtype="character",
                n_total=100,
                n_missing=0,
                n_unique=50,
                missing_pct=0.0,
                is_edc_column=False,
            )
        )
    for var in edc_vars or []:
        variables.append(
            VariableProfile(
                name=var,
                dtype="character",
                n_total=100,
                n_missing=0,
                n_unique=1,
                missing_pct=0.0,
                is_edc_column=True,
            )
        )
    return DatasetProfile(
        filename=filename,
        row_count=100,
        col_count=len(variables),
        variables=variables,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def ae_form() -> ECRFForm:
    """eCRF form with AE-like field names."""
    return ECRFForm(
        form_name="Adverse Events",
        fields=[
            _make_field("AETERM"),
            _make_field("AESTDTC"),
            _make_field("AEENDTC"),
        ],
        page_numbers=[10, 11],
    )


@pytest.fixture()
def dm_form() -> ECRFForm:
    """eCRF form with DM-like field names."""
    return ECRFForm(
        form_name="Demographics",
        fields=[
            _make_field("BRTHDAT"),
            _make_field("SEX"),
            _make_field("RACE"),
        ],
        page_numbers=[5],
    )


@pytest.fixture()
def ae_profile() -> DatasetProfile:
    """Dataset profile matching AE form fields."""
    return _make_profile(
        filename="ae.sas7bdat",
        clinical_vars=["AETERM", "AESTDTC", "AEENDTC", "AESER"],
        edc_vars=["projectid", "DataPageId"],
    )


@pytest.fixture()
def dm_profile() -> DatasetProfile:
    """Dataset profile matching DM form fields."""
    return _make_profile(
        filename="dm.sas7bdat",
        clinical_vars=["BRTHDAT", "SEX", "RACE", "AGE"],
        edc_vars=["projectid"],
    )


@pytest.fixture()
def unrelated_profile() -> DatasetProfile:
    """Dataset profile with no overlap to AE or DM forms."""
    return _make_profile(
        filename="unknown.sas7bdat",
        clinical_vars=["XVAR1", "XVAR2"],
    )


# ---------------------------------------------------------------------------
# Tests: match_form_to_datasets
# ---------------------------------------------------------------------------


class TestMatchFormToDatasets:
    """Tests for match_form_to_datasets()."""

    def test_high_overlap_match(self, ae_form: ECRFForm, ae_profile: DatasetProfile) -> None:
        """AE form should score high against ae dataset."""
        results = match_form_to_datasets(ae_form, [ae_profile])
        assert len(results) == 1
        name, score = results[0]
        assert name == "ae.sas7bdat"
        assert score == pytest.approx(1.0)  # 3/3 fields match

    def test_no_overlap(self, ae_form: ECRFForm, unrelated_profile: DatasetProfile) -> None:
        """AE form should not match unrelated dataset."""
        results = match_form_to_datasets(ae_form, [unrelated_profile])
        assert len(results) == 0

    def test_sorting_by_score(
        self,
        ae_form: ECRFForm,
        ae_profile: DatasetProfile,
        dm_profile: DatasetProfile,
    ) -> None:
        """Results should be sorted by score descending."""
        results = match_form_to_datasets(ae_form, [dm_profile, ae_profile])
        assert len(results) == 1  # dm_profile has 0 overlap with AE form
        assert results[0][0] == "ae.sas7bdat"

    def test_edc_columns_excluded(self, ae_form: ECRFForm) -> None:
        """EDC columns should not count toward overlap."""
        # Create profile where AE fields exist only as EDC columns
        profile = _make_profile(
            filename="fake.sas7bdat",
            clinical_vars=["XVAR"],
            edc_vars=["AETERM", "AESTDTC", "AEENDTC"],
        )
        results = match_form_to_datasets(ae_form, [profile])
        assert len(results) == 0

    def test_case_insensitive_matching(self) -> None:
        """Field names and variable names should match case-insensitively."""
        form = ECRFForm(
            form_name="Test",
            fields=[_make_field("AETERM")],
            page_numbers=[1],
        )
        profile = _make_profile("test.sas7bdat", clinical_vars=["aeterm"])
        results = match_form_to_datasets(form, [profile])
        assert len(results) == 1
        assert results[0][1] == pytest.approx(1.0)

    def test_empty_form_fields(self) -> None:
        """Form with no fields should return empty results."""
        form = ECRFForm(form_name="Empty", fields=[], page_numbers=[1])
        profile = _make_profile("test.sas7bdat", clinical_vars=["VAR1"])
        results = match_form_to_datasets(form, [profile])
        assert results == []

    def test_partial_overlap(self) -> None:
        """Partial overlap should return fractional score."""
        form = ECRFForm(
            form_name="Test",
            fields=[_make_field("VAR1"), _make_field("VAR2"), _make_field("VAR3")],
            page_numbers=[1],
        )
        # Only VAR1 matches
        profile = _make_profile("test.sas7bdat", clinical_vars=["VAR1", "XVAR"])
        results = match_form_to_datasets(form, [profile])
        assert len(results) == 1
        assert results[0][1] == pytest.approx(1.0 / 3.0)


# ---------------------------------------------------------------------------
# Tests: match_all_forms
# ---------------------------------------------------------------------------


class TestMatchAllForms:
    """Tests for match_all_forms()."""

    def test_threshold_filtering(
        self,
        ae_form: ECRFForm,
        ae_profile: DatasetProfile,
    ) -> None:
        """Matches below threshold should be excluded."""
        # Create a form where only 1/10 fields match
        big_form = ECRFForm(
            form_name="BigForm",
            fields=[_make_field(f"F{i}") for i in range(10)],
            page_numbers=[1],
        )
        profile = _make_profile("test.sas7bdat", clinical_vars=["F0"])
        result = match_all_forms([big_form], [profile], threshold=0.2)
        # 1/10 = 0.1 < 0.2 threshold, should be filtered out
        assert result["BigForm"] == []

    def test_multiple_forms(
        self,
        ae_form: ECRFForm,
        dm_form: ECRFForm,
        ae_profile: DatasetProfile,
        dm_profile: DatasetProfile,
    ) -> None:
        """Multiple forms should each match their corresponding dataset."""
        result = match_all_forms([ae_form, dm_form], [ae_profile, dm_profile], threshold=0.2)
        assert len(result) == 2
        assert "Adverse Events" in result
        assert "Demographics" in result
        # AE form matches ae dataset
        assert any(n == "ae.sas7bdat" for n, _ in result["Adverse Events"])
        # DM form matches dm dataset
        assert any(n == "dm.sas7bdat" for n, _ in result["Demographics"])


# ---------------------------------------------------------------------------
# Tests: get_unmatched_datasets / get_unmatched_forms
# ---------------------------------------------------------------------------


class TestUnmatched:
    """Tests for get_unmatched_datasets() and get_unmatched_forms()."""

    def test_unmatched_datasets(self) -> None:
        """Datasets not appearing in any match should be returned."""
        form_matches = {
            "FormA": [("ds1.sas7bdat", 0.8)],
            "FormB": [("ds2.sas7bdat", 0.5)],
        }
        all_names = ["ds1.sas7bdat", "ds2.sas7bdat", "ds3.sas7bdat"]
        unmatched = get_unmatched_datasets(form_matches, all_names)
        assert unmatched == ["ds3.sas7bdat"]

    def test_all_datasets_matched(self) -> None:
        """When all datasets are matched, should return empty list."""
        form_matches = {"FormA": [("ds1.sas7bdat", 0.9)]}
        unmatched = get_unmatched_datasets(form_matches, ["ds1.sas7bdat"])
        assert unmatched == []

    def test_unmatched_forms(self) -> None:
        """Forms with empty match lists should be returned."""
        form_matches = {
            "FormA": [("ds1.sas7bdat", 0.8)],
            "FormB": [],
            "FormC": [],
        }
        unmatched = get_unmatched_forms(form_matches)
        assert unmatched == ["FormB", "FormC"]

    def test_no_unmatched_forms(self) -> None:
        """When all forms have matches, should return empty list."""
        form_matches = {
            "FormA": [("ds1.sas7bdat", 0.8)],
            "FormB": [("ds2.sas7bdat", 0.5)],
        }
        unmatched = get_unmatched_forms(form_matches)
        assert unmatched == []
