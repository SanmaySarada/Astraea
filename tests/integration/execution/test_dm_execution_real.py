"""End-to-end DM domain execution against real Fakedata/dm.sas7bdat.

This is the Phase 11 acceptance test: proves the LLM-to-executor contract
works on real data. The Master Audit found 10/18 columns ALL NULL; this
test verifies that derivation rule handlers (GENERATE_USUBJID, RACE_CHECKBOX,
ISO8601_PARTIAL_DATE, etc.) produce populated columns.

Skipped gracefully in CI or any environment without Fakedata/.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import pytest

from astraea.execution.executor import DatasetExecutor
from astraea.models.mapping import (
    ConfidenceLevel,
    DomainMappingSpec,
    MappingPattern,
    VariableMapping,
)
from astraea.models.sdtm import CoreDesignation
from astraea.reference import load_ct_reference, load_sdtm_reference

# -----------------------------------------------------------------------
# Skip guard: require Fakedata directory
# -----------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_FAKEDATA_DIR = _PROJECT_ROOT / "Fakedata"
_DM_SAS = _FAKEDATA_DIR / "dm.sas7bdat"
_DM_MAPPING_JSON = _PROJECT_ROOT / "output" / "DM_mapping.json"

pytestmark = pytest.mark.integration


def _skip_unless_fakedata() -> None:
    if not _DM_SAS.exists():
        pytest.skip("Fakedata/dm.sas7bdat not found -- skipping real-data test")


# -----------------------------------------------------------------------
# Helper: build a test-local DM mapping spec using correct vocabulary
# -----------------------------------------------------------------------

def _vm(
    *,
    var: str,
    pattern: MappingPattern,
    label: str,
    source: str | None = None,
    assigned: str | None = None,
    derivation: str | None = None,
    codelist: str | None = None,
    order: int,
    core: CoreDesignation = CoreDesignation.REQ,
    dtype: str = "Char",
) -> VariableMapping:
    """Shorthand for constructing a VariableMapping."""
    return VariableMapping(
        sdtm_variable=var,
        sdtm_label=label,
        sdtm_data_type=dtype,
        core=core,
        source_variable=source,
        mapping_pattern=pattern,
        mapping_logic="test mapping",
        assigned_value=assigned,
        derivation_rule=derivation,
        codelist_code=codelist,
        confidence=0.9,
        confidence_level=ConfidenceLevel.HIGH,
        confidence_rationale="test",
        order=order,
    )


def _build_dm_spec() -> DomainMappingSpec:
    """Build a DM mapping spec using the Phase 11 derivation rule vocabulary.

    This exercises:
    - ASSIGN for STUDYID, DOMAIN, AGEU
    - GENERATE_USUBJID for USUBJID
    - DIRECT for SUBJID, SITEID, AGE
    - RENAME for SEX (SEX_STD -> SEX), ETHNIC (ETHNIC_STD -> ETHNIC)
    - RACE_CHECKBOX for RACE (from RACEAME, RACEASI, RACEBLA, RACENAT, RACEWHI, RACENTRE)
    - ISO8601_PARTIAL_DATE for BRTHDTC (from BRTHYR_YYYY)
    - LOOKUP_RECODE for SEX via codelist C66731
    """
    mappings = [
        _vm(
            var="STUDYID",
            pattern=MappingPattern.ASSIGN,
            label="Study Identifier",
            assigned="PHA022121-C301",
            order=1,
        ),
        _vm(
            var="DOMAIN",
            pattern=MappingPattern.ASSIGN,
            label="Domain Abbreviation",
            assigned="DM",
            order=2,
        ),
        _vm(
            var="USUBJID",
            pattern=MappingPattern.DERIVATION,
            label="Unique Subject Identifier",
            derivation="GENERATE_USUBJID(PHA022121-C301)",
            order=3,
        ),
        _vm(
            var="SUBJID",
            pattern=MappingPattern.DIRECT,
            label="Subject Identifier for the Study",
            source="Subject",
            order=4,
        ),
        _vm(
            var="SITEID",
            pattern=MappingPattern.DIRECT,
            label="Study Site Identifier",
            source="SiteNumber",
            order=5,
        ),
        _vm(
            var="BRTHDTC",
            pattern=MappingPattern.REFORMAT,
            label="Date/Time of Birth",
            source="BRTHYR_YYYY",
            derivation="ISO8601_PARTIAL_DATE(BRTHYR_YYYY)",
            order=6,
            core=CoreDesignation.EXP,
        ),
        _vm(
            var="AGE",
            pattern=MappingPattern.DIRECT,
            label="Age",
            source="AGE",
            order=7,
            core=CoreDesignation.EXP,
            dtype="Num",
        ),
        _vm(
            var="AGEU",
            pattern=MappingPattern.ASSIGN,
            label="Age Units",
            assigned="YEARS",
            order=8,
            core=CoreDesignation.EXP,
        ),
        _vm(
            var="SEX",
            pattern=MappingPattern.RENAME,
            label="Sex",
            source="SEX_STD",
            codelist="C66731",
            order=9,
        ),
        _vm(
            var="RACE",
            pattern=MappingPattern.DERIVATION,
            label="Race",
            derivation="RACE_CHECKBOX(RACEAME, RACEASI, RACEBLA, RACENAT, RACEWHI, RACENTRE)",
            order=10,
            core=CoreDesignation.EXP,
        ),
        _vm(
            var="ETHNIC",
            pattern=MappingPattern.RENAME,
            label="Ethnicity",
            source="ETHNIC_STD",
            codelist="C66790",
            order=11,
            core=CoreDesignation.EXP,
        ),
        # Cross-domain dates -- these will be NULL without EX/DS data,
        # but they should exist as columns
        _vm(
            var="RFSTDTC",
            pattern=MappingPattern.DERIVATION,
            label="Subject Reference Start Date/Time",
            derivation="MIN_DATE_PER_SUBJECT(EXDAT_INT)",
            order=12,
            core=CoreDesignation.EXP,
        ),
        _vm(
            var="RFENDTC",
            pattern=MappingPattern.DERIVATION,
            label="Subject Reference End Date/Time",
            derivation="MAX_DATE_PER_SUBJECT(EXDAT_INT)",
            order=13,
            core=CoreDesignation.EXP,
        ),
        _vm(
            var="ARMCD",
            pattern=MappingPattern.ASSIGN,
            label="Planned Arm Code",
            assigned="TRT",
            order=14,
            core=CoreDesignation.REQ,
        ),
        _vm(
            var="ARM",
            pattern=MappingPattern.ASSIGN,
            label="Description of Planned Arm",
            assigned="Treatment",
            order=15,
            core=CoreDesignation.REQ,
        ),
        _vm(
            var="COUNTRY",
            pattern=MappingPattern.ASSIGN,
            label="Country",
            assigned="GBR",
            order=16,
            core=CoreDesignation.REQ,
        ),
        _vm(
            var="DMDTC",
            pattern=MappingPattern.DIRECT,
            label="Date/Time of Collection",
            source="RecordDate",
            order=17,
            core=CoreDesignation.PERM,
        ),
        _vm(
            var="DMDY",
            pattern=MappingPattern.ASSIGN,
            label="Study Day of Collection",
            assigned=None,
            order=18,
            core=CoreDesignation.PERM,
        ),
    ]
    return DomainMappingSpec(
        domain="DM",
        domain_label="Demographics",
        domain_class="Special Purpose",
        structure="One record per subject",
        study_id="PHA022121-C301",
        source_datasets=["dm"],
        variable_mappings=mappings,
        total_variables=len(mappings),
        required_mapped=7,
        expected_mapped=7,
        high_confidence_count=len(mappings),
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-28T00:00:00",
        model_used="test-fixture",
    )


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------

@pytest.fixture()
def dm_raw_df() -> pd.DataFrame:
    """Load real Fakedata/dm.sas7bdat."""
    _skip_unless_fakedata()
    import pyreadstat

    df, _meta = pyreadstat.read_sas7bdat(str(_DM_SAS))
    return df


@pytest.fixture()
def dm_spec_fixture() -> DomainMappingSpec:
    """Load DM spec from output/DM_mapping.json if available, else build fixture."""
    if _DM_MAPPING_JSON.exists():
        with open(_DM_MAPPING_JSON) as f:
            data = json.load(f)
        return DomainMappingSpec(**data)
    return _build_dm_spec()


@pytest.fixture()
def dm_spec_local() -> DomainMappingSpec:
    """Always use the test-local spec with correct vocabulary."""
    return _build_dm_spec()


@pytest.fixture()
def sdtm_ref():
    return load_sdtm_reference()


@pytest.fixture()
def ct_ref():
    return load_ct_reference()


# -----------------------------------------------------------------------
# Tests using the test-local spec (guaranteed correct vocabulary)
# -----------------------------------------------------------------------

class TestDMExecutionReal:
    """Execute DM mapping on real Fakedata and verify SDTM output."""

    def test_row_count_matches_source(
        self, dm_raw_df: pd.DataFrame, dm_spec_local: DomainMappingSpec,
        sdtm_ref, ct_ref,
    ) -> None:
        """Output should have the same number of rows as dm.sas7bdat (3)."""
        executor = DatasetExecutor(sdtm_ref=sdtm_ref, ct_ref=ct_ref)
        result = executor.execute(
            dm_spec_local,
            {"dm": dm_raw_df},
            study_id="PHA022121-C301",
        )
        assert len(result) == len(dm_raw_df), (
            f"Expected {len(dm_raw_df)} rows, got {len(result)}"
        )

    def test_studyid_constant_for_all_rows(
        self, dm_raw_df: pd.DataFrame, dm_spec_local: DomainMappingSpec,
        sdtm_ref, ct_ref,
    ) -> None:
        """STUDYID must be 'PHA022121-C301' for all rows."""
        executor = DatasetExecutor(sdtm_ref=sdtm_ref, ct_ref=ct_ref)
        result = executor.execute(
            dm_spec_local,
            {"dm": dm_raw_df},
            study_id="PHA022121-C301",
        )
        assert result["STUDYID"].notna().all()
        assert (result["STUDYID"] == "PHA022121-C301").all()

    def test_domain_is_dm_for_all_rows(
        self, dm_raw_df: pd.DataFrame, dm_spec_local: DomainMappingSpec,
        sdtm_ref, ct_ref,
    ) -> None:
        """DOMAIN must be 'DM' for all rows."""
        executor = DatasetExecutor(sdtm_ref=sdtm_ref, ct_ref=ct_ref)
        result = executor.execute(
            dm_spec_local,
            {"dm": dm_raw_df},
            study_id="PHA022121-C301",
        )
        assert result["DOMAIN"].notna().all()
        assert (result["DOMAIN"] == "DM").all()

    def test_usubjid_non_null_for_all_rows(
        self, dm_raw_df: pd.DataFrame, dm_spec_local: DomainMappingSpec,
        sdtm_ref, ct_ref,
    ) -> None:
        """USUBJID must be non-NULL for all rows (CRIT-02 fix)."""
        executor = DatasetExecutor(sdtm_ref=sdtm_ref, ct_ref=ct_ref)
        result = executor.execute(
            dm_spec_local,
            {"dm": dm_raw_df},
            study_id="PHA022121-C301",
        )
        assert result["USUBJID"].notna().all(), (
            f"USUBJID has NULLs: {result['USUBJID'].tolist()}"
        )

    def test_usubjid_follows_pattern(
        self, dm_raw_df: pd.DataFrame, dm_spec_local: DomainMappingSpec,
        sdtm_ref, ct_ref,
    ) -> None:
        """USUBJID must follow pattern PHA022121-C301-*-*."""
        executor = DatasetExecutor(sdtm_ref=sdtm_ref, ct_ref=ct_ref)
        result = executor.execute(
            dm_spec_local,
            {"dm": dm_raw_df},
            study_id="PHA022121-C301",
        )
        pattern = re.compile(r"^PHA022121-C301-.+-.+$")
        for val in result["USUBJID"]:
            assert pattern.match(str(val)), (
                f"USUBJID '{val}' does not match expected pattern"
            )

    def test_usubjid_no_nan_strings(
        self, dm_raw_df: pd.DataFrame, dm_spec_local: DomainMappingSpec,
        sdtm_ref, ct_ref,
    ) -> None:
        """USUBJID should not contain 'nan' or 'None' as string values."""
        executor = DatasetExecutor(sdtm_ref=sdtm_ref, ct_ref=ct_ref)
        result = executor.execute(
            dm_spec_local,
            {"dm": dm_raw_df},
            study_id="PHA022121-C301",
        )
        for val in result["USUBJID"]:
            assert "nan" not in str(val).lower(), (
                f"USUBJID contains 'nan': {val}"
            )
            assert "None" not in str(val), (
                f"USUBJID contains 'None': {val}"
            )

    def test_brthdtc_iso8601_format(
        self, dm_raw_df: pd.DataFrame, dm_spec_local: DomainMappingSpec,
        sdtm_ref, ct_ref,
    ) -> None:
        """BRTHDTC must contain ISO 8601 year-only values, not raw numerics."""
        executor = DatasetExecutor(sdtm_ref=sdtm_ref, ct_ref=ct_ref)
        result = executor.execute(
            dm_spec_local,
            {"dm": dm_raw_df},
            study_id="PHA022121-C301",
        )
        iso_year_pattern = re.compile(r"^\d{4}$")
        iso_full_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}")

        non_null = result["BRTHDTC"].dropna()
        non_empty = non_null[non_null != ""]
        assert len(non_empty) > 0, "BRTHDTC is all empty/NULL"

        for val in non_empty:
            val_str = str(val)
            assert iso_year_pattern.match(val_str) or iso_full_pattern.match(val_str), (
                f"BRTHDTC value '{val_str}' is not ISO 8601"
            )
            # Must NOT be raw numeric like "1960.0"
            assert "." not in val_str, (
                f"BRTHDTC value '{val_str}' looks like raw numeric, not ISO 8601"
            )

    def test_race_derived_from_checkboxes(
        self, dm_raw_df: pd.DataFrame, dm_spec_local: DomainMappingSpec,
        sdtm_ref, ct_ref,
    ) -> None:
        """RACE must be derived from checkbox columns, not NULL."""
        executor = DatasetExecutor(sdtm_ref=sdtm_ref, ct_ref=ct_ref)
        result = executor.execute(
            dm_spec_local,
            {"dm": dm_raw_df},
            study_id="PHA022121-C301",
        )
        non_null = result["RACE"].dropna()
        assert len(non_null) > 0, "RACE is all NULL"
        # All 3 subjects in dm.sas7bdat have RACEWHI=1, so all should be WHITE
        for val in non_null:
            assert val in {
                "AMERICAN INDIAN OR ALASKA NATIVE",
                "ASIAN",
                "BLACK OR AFRICAN AMERICAN",
                "NATIVE HAWAIIAN OR OTHER PACIFIC ISLANDER",
                "WHITE",
                "OTHER",
                "NOT REPORTED",
                "MULTIPLE",
            }, f"Unexpected RACE value: {val}"

    def test_sex_populated(
        self, dm_raw_df: pd.DataFrame, dm_spec_local: DomainMappingSpec,
        sdtm_ref, ct_ref,
    ) -> None:
        """SEX must be populated with CT values (F, M)."""
        executor = DatasetExecutor(sdtm_ref=sdtm_ref, ct_ref=ct_ref)
        result = executor.execute(
            dm_spec_local,
            {"dm": dm_raw_df},
            study_id="PHA022121-C301",
        )
        non_null = result["SEX"].dropna()
        assert len(non_null) == len(result), "SEX has NULL values"
        assert set(non_null.unique()) <= {"M", "F", "U", "UNDIFFERENTIATED"}

    def test_ethnic_populated(
        self, dm_raw_df: pd.DataFrame, dm_spec_local: DomainMappingSpec,
        sdtm_ref, ct_ref,
    ) -> None:
        """ETHNIC must be populated."""
        executor = DatasetExecutor(sdtm_ref=sdtm_ref, ct_ref=ct_ref)
        result = executor.execute(
            dm_spec_local,
            {"dm": dm_raw_df},
            study_id="PHA022121-C301",
        )
        non_null = result["ETHNIC"].dropna()
        assert len(non_null) == len(result), "ETHNIC has NULL values"

    def test_age_populated(
        self, dm_raw_df: pd.DataFrame, dm_spec_local: DomainMappingSpec,
        sdtm_ref, ct_ref,
    ) -> None:
        """AGE must be populated with numeric values."""
        executor = DatasetExecutor(sdtm_ref=sdtm_ref, ct_ref=ct_ref)
        result = executor.execute(
            dm_spec_local,
            {"dm": dm_raw_df},
            study_id="PHA022121-C301",
        )
        non_null = result["AGE"].dropna()
        assert len(non_null) == len(result), "AGE has NULL values"
        # All ages should be positive integers
        for val in non_null:
            assert float(val) > 0, f"AGE value {val} is not positive"

    def test_at_least_14_columns_populated(
        self, dm_raw_df: pd.DataFrame, dm_spec_local: DomainMappingSpec,
        sdtm_ref, ct_ref,
    ) -> None:
        """At least 14 of 18 columns should be populated (not all-NULL)."""
        executor = DatasetExecutor(sdtm_ref=sdtm_ref, ct_ref=ct_ref)
        result = executor.execute(
            dm_spec_local,
            {"dm": dm_raw_df},
            study_id="PHA022121-C301",
        )
        populated = sum(
            1 for col in result.columns
            if result[col].notna().any() and not (result[col] == "").all()
        )
        # Without cross-domain data (EX, DS, IE), RFSTDTC/RFENDTC/RFXSTDTC/RFXENDTC/
        # RFICDTC/RFPENDTC may be NULL. But the core 14 should be populated.
        assert populated >= 14, (
            f"Only {populated}/{len(result.columns)} columns populated (expected >= 14). "
            f"NULL columns: {[c for c in result.columns if not result[c].notna().any() or (result[c] == '').all()]}"
        )

    def test_no_raw_sas_numeric_dates(
        self, dm_raw_df: pd.DataFrame, dm_spec_local: DomainMappingSpec,
        sdtm_ref, ct_ref,
    ) -> None:
        """No column should contain raw SAS numeric dates (e.g. 22738.0)."""
        executor = DatasetExecutor(sdtm_ref=sdtm_ref, ct_ref=ct_ref)
        result = executor.execute(
            dm_spec_local,
            {"dm": dm_raw_df},
            study_id="PHA022121-C301",
        )
        # Check date columns specifically
        date_cols = [c for c in result.columns if c.endswith("DTC")]
        for col in date_cols:
            for val in result[col].dropna():
                val_str = str(val)
                if val_str and val_str != "":
                    # Should not look like a raw SAS number
                    assert not re.match(r"^\d{4,5}\.\d+$", val_str), (
                        f"Column {col} has raw numeric date: {val_str}"
                    )

    def test_no_edc_columns_leak(
        self, dm_raw_df: pd.DataFrame, dm_spec_local: DomainMappingSpec,
        sdtm_ref, ct_ref,
    ) -> None:
        """EDC system columns must not appear in the output."""
        executor = DatasetExecutor(sdtm_ref=sdtm_ref, ct_ref=ct_ref)
        result = executor.execute(
            dm_spec_local,
            {"dm": dm_raw_df},
            study_id="PHA022121-C301",
        )
        edc_cols = {"projectid", "project", "studyid", "environmentName",
                    "subjectId", "StudySiteId", "instanceId", "InstanceName",
                    "folderid", "Folder", "DataPageId", "DataPageName",
                    "RecordId", "RecordPosition", "MinCreated", "MaxUpdated"}
        leaked = set(result.columns) & edc_cols
        assert not leaked, f"EDC columns leaked into output: {leaked}"


class TestDMExecutionFromJSON:
    """Execute DM mapping using the LLM-generated DM_mapping.json spec."""

    def test_dm_mapping_json_execution(
        self, dm_raw_df: pd.DataFrame, dm_spec_fixture: DomainMappingSpec,
        sdtm_ref, ct_ref,
    ) -> None:
        """DM_mapping.json should produce a valid SDTM DataFrame.

        This tests the actual LLM-generated spec, not just the fixture.
        """
        if not _DM_MAPPING_JSON.exists():
            pytest.skip("output/DM_mapping.json not found")

        executor = DatasetExecutor(sdtm_ref=sdtm_ref, ct_ref=ct_ref)
        result = executor.execute(
            dm_spec_fixture,
            {"dm": dm_raw_df},
            study_id="PHA022121-C301",
        )

        # Basic sanity checks
        assert len(result) == len(dm_raw_df)
        assert result["STUDYID"].notna().all()
        assert result["DOMAIN"].notna().all()
        assert (result["DOMAIN"] == "DM").all()

        # Count populated columns
        populated = sum(
            1 for col in result.columns
            if result[col].notna().any() and not (result[col] == "").all()
        )
        # Log the result for debugging
        null_cols = [
            c for c in result.columns
            if not result[c].notna().any() or (result[c] == "").all()
        ]
        assert populated >= 10, (
            f"Only {populated}/{len(result.columns)} columns populated. "
            f"NULL/empty: {null_cols}"
        )
