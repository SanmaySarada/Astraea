"""Cross-domain validation, --DY derivation, EPOCH assignment, and origin metadata tests.

Validates that domains work TOGETHER:
- USUBJID consistency across domains (orphan detection)
- --DY calculation with cross-domain RFSTDTC lookup
- EPOCH derivation from SE domain data
- Variable origin metadata populated on all mapping patterns
"""

from __future__ import annotations

import pandas as pd
import pytest

from astraea.execution.executor import CrossDomainContext, DatasetExecutor
from astraea.models.mapping import (
    ConfidenceLevel,
    DomainMappingSpec,
    MappingPattern,
    VariableMapping,
    VariableOrigin,
)
from astraea.models.sdtm import CoreDesignation
from astraea.reference import load_ct_reference, load_sdtm_reference

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _mapping(
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
    origin: VariableOrigin | None = None,
    dtype: str = "Char",
) -> VariableMapping:
    return VariableMapping(
        sdtm_variable=var,
        sdtm_label=label,
        sdtm_data_type=dtype,
        core=core,
        source_variable=source,
        mapping_pattern=pattern,
        mapping_logic="test",
        assigned_value=assigned,
        derivation_rule=derivation,
        codelist_code=codelist,
        confidence=0.9,
        confidence_level=ConfidenceLevel.HIGH,
        confidence_rationale="test",
        order=order,
        origin=origin,
    )


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def dm_df() -> pd.DataFrame:
    """Pre-built DM DataFrame with 3 subjects."""
    return pd.DataFrame({
        "STUDYID": ["PHA022121-C301"] * 3,
        "DOMAIN": ["DM"] * 3,
        "USUBJID": [
            "PHA022121-C301-101-001",
            "PHA022121-C301-101-002",
            "PHA022121-C301-102-003",
        ],
        "RFSTDTC": ["2022-01-01", "2022-01-15", "2022-02-01"],
    })


@pytest.fixture()
def cross_domain() -> CrossDomainContext:
    """CrossDomainContext with rfstdtc_lookup AND se_data."""
    return CrossDomainContext(
        rfstdtc_lookup={
            "PHA022121-C301-101-001": "2022-01-01",
            "PHA022121-C301-101-002": "2022-01-15",
            "PHA022121-C301-102-003": "2022-02-01",
        },
        se_data=pd.DataFrame({
            "USUBJID": [
                "PHA022121-C301-101-001", "PHA022121-C301-101-001",
                "PHA022121-C301-101-002", "PHA022121-C301-101-002",
                "PHA022121-C301-102-003", "PHA022121-C301-102-003",
            ],
            "EPOCH": [
                "SCREENING", "TREATMENT",
                "SCREENING", "TREATMENT",
                "SCREENING", "TREATMENT",
            ],
            "SESTDTC": [
                "2021-12-15", "2022-01-01",
                "2021-12-20", "2022-01-15",
                "2022-01-10", "2022-02-01",
            ],
            "SEENDTC": [
                "2021-12-31", "2022-06-30",
                "2022-01-14", "2022-06-30",
                "2022-01-31", "2022-06-30",
            ],
        }),
    )


@pytest.fixture()
def raw_ae_df() -> pd.DataFrame:
    """Minimal raw AE data for 3 subjects with ISO dates."""
    return pd.DataFrame({
        "Subject": ["001", "002", "003"],
        "SiteNumber": ["101", "101", "102"],
        "AETERM": ["Headache", "Nausea", "Fatigue"],
        "AESTDTC": ["2022-01-15", "2022-02-01", "2022-03-15"],
    })


@pytest.fixture()
def ae_with_orphan_df() -> pd.DataFrame:
    """AE data with an orphan subject 999 not in DM."""
    return pd.DataFrame({
        "Subject": ["001", "002", "003", "999"],
        "SiteNumber": ["101", "101", "102", "999"],
        "AETERM": ["Headache", "Nausea", "Fatigue", "Dizziness"],
        "AESTDTC": ["2022-01-15", "2022-02-01", "2022-03-15", "2022-04-01"],
    })


def _ae_base_spec(*, include_dy: bool = False, include_epoch: bool = False) -> DomainMappingSpec:
    """Build an AE spec with optional --DY and EPOCH mappings."""
    mappings = [
        _mapping(
            var="STUDYID", pattern=MappingPattern.ASSIGN,
            label="Study Identifier", assigned="PHA022121-C301",
            order=1, origin=VariableOrigin.ASSIGNED,
        ),
        _mapping(
            var="DOMAIN", pattern=MappingPattern.ASSIGN,
            label="Domain Abbreviation", assigned="AE",
            order=2, origin=VariableOrigin.ASSIGNED,
        ),
        _mapping(
            var="USUBJID", pattern=MappingPattern.DERIVATION,
            label="Unique Subject Identifier", derivation="generate_usubjid",
            order=3, origin=VariableOrigin.DERIVED,
        ),
        _mapping(
            var="AESEQ", pattern=MappingPattern.DERIVATION,
            label="Sequence Number", derivation="generate_seq",
            order=4, dtype="Num", origin=VariableOrigin.DERIVED,
        ),
        _mapping(
            var="AETERM", pattern=MappingPattern.DIRECT,
            label="Reported Term for the Adverse Event", source="AETERM",
            order=5, origin=VariableOrigin.CRF,
        ),
        _mapping(
            var="AESTDTC", pattern=MappingPattern.DIRECT,
            label="Start Date/Time of Adverse Event", source="AESTDTC",
            order=6, origin=VariableOrigin.CRF,
        ),
    ]

    if include_dy:
        mappings.append(_mapping(
            var="AESTDY", pattern=MappingPattern.DERIVATION,
            label="Study Day of Start of Adverse Event", derivation="calculate_study_day",
            order=7, dtype="Num", origin=VariableOrigin.DERIVED,
        ))

    if include_epoch:
        mappings.append(_mapping(
            var="EPOCH", pattern=MappingPattern.DERIVATION,
            label="Epoch", derivation="assign_epoch",
            order=8, origin=VariableOrigin.DERIVED,
        ))

    return DomainMappingSpec(
        domain="AE",
        domain_label="Adverse Events",
        domain_class="Events",
        structure="One record per adverse event per subject",
        study_id="PHA022121-C301",
        source_datasets=["ae"],
        variable_mappings=mappings,
        total_variables=len(mappings),
        required_mapped=4,
        expected_mapped=1,
        high_confidence_count=len(mappings),
        medium_confidence_count=0,
        low_confidence_count=0,
        mapping_timestamp="2026-02-27T00:00:00",
        model_used="test",
    )


@pytest.fixture()
def executor() -> DatasetExecutor:
    return DatasetExecutor(
        sdtm_ref=load_sdtm_reference(),
        ct_ref=load_ct_reference(),
    )


# ===========================================================================
# Test class: Cross-domain USUBJID validation
# ===========================================================================


class TestCrossDomainValidation:
    """Validate that cross-domain USUBJID checks detect orphan subjects."""

    def test_all_subjects_in_dm_passes(
        self, dm_df: pd.DataFrame, executor: DatasetExecutor, raw_ae_df: pd.DataFrame
    ) -> None:
        """No errors when all AE subjects exist in DM."""
        spec = _ae_base_spec()
        result = executor.execute(spec, {"ae": raw_ae_df})

        errors = DatasetExecutor.validate_cross_domain_usubjid(
            dm_df, {"AE": result}
        )
        assert errors == []

    def test_orphan_subject_detected(
        self, dm_df: pd.DataFrame, executor: DatasetExecutor, ae_with_orphan_df: pd.DataFrame
    ) -> None:
        """Orphan subject 999 not in DM is detected."""
        spec = _ae_base_spec()
        result = executor.execute(spec, {"ae": ae_with_orphan_df})

        errors = DatasetExecutor.validate_cross_domain_usubjid(
            dm_df, {"AE": result}
        )
        assert len(errors) == 1
        assert "999" in errors[0]
        assert "AE" in errors[0]
        assert "not found in DM" in errors[0]

    def test_multiple_domains_validated(
        self, dm_df: pd.DataFrame, executor: DatasetExecutor, raw_ae_df: pd.DataFrame
    ) -> None:
        """Validate across AE and CM domains together."""
        ae_spec = _ae_base_spec()
        ae_result = executor.execute(ae_spec, {"ae": raw_ae_df})

        # Build a CM-like DataFrame with same 3 subjects
        cm_result = pd.DataFrame({
            "STUDYID": ["PHA022121-C301"] * 3,
            "DOMAIN": ["CM"] * 3,
            "USUBJID": [
                "PHA022121-C301-101-001",
                "PHA022121-C301-101-002",
                "PHA022121-C301-102-003",
            ],
        })

        errors = DatasetExecutor.validate_cross_domain_usubjid(
            dm_df, {"AE": ae_result, "CM": cm_result}
        )
        assert errors == []


# ===========================================================================
# Test class: --DY derivation from cross-domain RFSTDTC
# ===========================================================================


class TestStudyDayDerivation:
    """Verify --DY calculation uses cross-domain RFSTDTC from DM."""

    def test_aestdy_derived_from_rfstdtc(
        self, executor: DatasetExecutor, raw_ae_df: pd.DataFrame, cross_domain: CrossDomainContext
    ) -> None:
        """AESTDY correctly computed for 3 subjects.

        Subject 001: AESTDTC="2022-01-15", RFSTDTC="2022-01-01" -> AESTDY=15
        Subject 002: AESTDTC="2022-02-01", RFSTDTC="2022-01-15" -> AESTDY=18
        Subject 003: AESTDTC="2022-03-15", RFSTDTC="2022-02-01" -> AESTDY=43
        """
        spec = _ae_base_spec(include_dy=True)
        result = executor.execute(
            spec, {"ae": raw_ae_df}, cross_domain=cross_domain,
        )

        assert "AESTDY" in result.columns
        # Sort by USUBJID to get deterministic order
        result = result.sort_values("USUBJID").reset_index(drop=True)

        # Subject 001: 15 Jan - 01 Jan = 14 days -> day 15
        assert result.loc[0, "AESTDY"] == 15
        # Subject 002: 01 Feb - 15 Jan = 17 days -> day 18
        assert result.loc[1, "AESTDY"] == 18
        # Subject 003: 15 Mar - 01 Feb = 42 days -> day 43
        assert result.loc[2, "AESTDY"] == 43

    def test_dy_without_cross_domain_context(
        self, executor: DatasetExecutor, raw_ae_df: pd.DataFrame
    ) -> None:
        """AESTDY not derived when no cross-domain context is provided."""
        spec = _ae_base_spec(include_dy=True)
        result = executor.execute(spec, {"ae": raw_ae_df})

        # AESTDY should either not be present or be all NaN
        if "AESTDY" in result.columns:
            assert result["AESTDY"].isna().all()


# ===========================================================================
# Test class: EPOCH derivation from SE data
# ===========================================================================


class TestEpochDerivation:
    """Verify EPOCH assignment from SE domain element dates."""

    def test_epoch_assigned_from_se_data(
        self, executor: DatasetExecutor, raw_ae_df: pd.DataFrame, cross_domain: CrossDomainContext
    ) -> None:
        """All 3 subjects' AE dates fall in TREATMENT epoch.

        Subject 001: AESTDTC="2022-01-15" within TREATMENT (2022-01-01 to 2022-06-30)
        Subject 002: AESTDTC="2022-02-01" within TREATMENT (2022-01-15 to 2022-06-30)
        Subject 003: AESTDTC="2022-03-15" within TREATMENT (2022-02-01 to 2022-06-30)
        """
        spec = _ae_base_spec(include_epoch=True)
        result = executor.execute(
            spec, {"ae": raw_ae_df}, cross_domain=cross_domain,
        )

        assert "EPOCH" in result.columns
        assert (result["EPOCH"] == "TREATMENT").all()

    def test_epoch_without_se_data(
        self, executor: DatasetExecutor, raw_ae_df: pd.DataFrame
    ) -> None:
        """EPOCH gracefully handles missing SE data."""
        spec = _ae_base_spec(include_epoch=True)
        # CrossDomainContext with no se_data
        cross_domain_no_se = CrossDomainContext(
            rfstdtc_lookup={
                "PHA022121-C301-101-001": "2022-01-01",
            },
        )
        result = executor.execute(
            spec, {"ae": raw_ae_df}, cross_domain=cross_domain_no_se,
        )

        # EPOCH should either not be present or be empty/NaN
        if "EPOCH" in result.columns:
            assert result["EPOCH"].isna().all() or (result["EPOCH"] == "").all()


# ===========================================================================
# Test class: Variable origin metadata
# ===========================================================================


class TestVariableOriginMetadata:
    """Verify origin metadata is populated on VariableMapping for define.xml traceability."""

    def test_origin_populated_on_assign(self) -> None:
        """ASSIGN pattern -> VariableOrigin.ASSIGNED."""
        spec = _ae_base_spec()
        studyid_mapping = next(
            m for m in spec.variable_mappings if m.sdtm_variable == "STUDYID"
        )
        assert studyid_mapping.origin == VariableOrigin.ASSIGNED

    def test_origin_populated_on_direct(self) -> None:
        """DIRECT pattern -> VariableOrigin.CRF."""
        spec = _ae_base_spec()
        aeterm_mapping = next(
            m for m in spec.variable_mappings if m.sdtm_variable == "AETERM"
        )
        assert aeterm_mapping.origin == VariableOrigin.CRF

    def test_origin_populated_on_derivation(self) -> None:
        """DERIVATION pattern -> VariableOrigin.DERIVED."""
        spec = _ae_base_spec(include_dy=True)
        aestdy_mapping = next(
            m for m in spec.variable_mappings if m.sdtm_variable == "AESTDY"
        )
        assert aestdy_mapping.origin == VariableOrigin.DERIVED

    def test_origin_accessible_after_execution(
        self, executor: DatasetExecutor, raw_ae_df: pd.DataFrame
    ) -> None:
        """Origin metadata survives the execution pipeline."""
        spec = _ae_base_spec()
        # Execute modifies result_df but should not mutate spec.variable_mappings
        executor.execute(spec, {"ae": raw_ae_df})

        for m in spec.variable_mappings:
            assert m.origin is not None, f"Origin lost for {m.sdtm_variable}"

    def test_all_mappings_have_origin(self) -> None:
        """Every mapping in the AE spec has a non-None origin value."""
        spec = _ae_base_spec(include_dy=True, include_epoch=True)
        for m in spec.variable_mappings:
            assert m.origin is not None, (
                f"VariableMapping {m.sdtm_variable} has origin=None"
            )
