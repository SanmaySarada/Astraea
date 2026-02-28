"""Unit tests for SUPPQUAL generator and referential integrity validation."""

from __future__ import annotations

import pandas as pd
import pytest

from astraea.execution.suppqual import generate_suppqual, validate_suppqual_integrity
from astraea.models.suppqual import SuppVariable

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def parent_ae_df() -> pd.DataFrame:
    """Parent AE DataFrame with 3 rows."""
    return pd.DataFrame(
        {
            "STUDYID": ["STUDY1", "STUDY1", "STUDY1"],
            "USUBJID": ["S01", "S01", "S02"],
            "AESEQ": [1, 2, 1],
            "AETERM": ["Headache", "Nausea", "Fatigue"],
            "AESEV": ["MILD", "MODERATE", "SEVERE"],
            "AEACNOTH": ["None", "Medication given", ""],
        }
    )


@pytest.fixture()
def supp_vars() -> list[SuppVariable]:
    """Two supplemental variables for AE domain."""
    return [
        SuppVariable(
            qnam="AESEV",
            qlabel="Severity/Intensity",
            source_col="AESEV",
            qorig="CRF",
        ),
        SuppVariable(
            qnam="AEACNOTH",
            qlabel="Other Action Taken",
            source_col="AEACNOTH",
            qorig="CRF",
        ),
    ]


# ---------------------------------------------------------------------------
# Tests: generate_suppqual
# ---------------------------------------------------------------------------


class TestGenerateSuppqual:
    """Tests for generate_suppqual()."""

    def test_basic_generation(
        self, parent_ae_df: pd.DataFrame, supp_vars: list[SuppVariable]
    ) -> None:
        """3 parent rows x 2 supp variables, minus 1 empty value = 5 records."""
        result = generate_suppqual(parent_ae_df, "AE", "STUDY1", supp_vars)

        # Row 1 (S01, SEQ=1): AESEV="MILD", AEACNOTH="None" -> 2 records
        # Row 2 (S01, SEQ=2): AESEV="MODERATE", AEACNOTH="Medication given" -> 2 records
        # Row 3 (S02, SEQ=1): AESEV="SEVERE", AEACNOTH="" -> 1 record (empty skipped)
        assert len(result) == 5

    def test_correct_columns(
        self, parent_ae_df: pd.DataFrame, supp_vars: list[SuppVariable]
    ) -> None:
        """Result has the standard SUPPQUAL columns."""
        result = generate_suppqual(parent_ae_df, "AE", "STUDY1", supp_vars)

        expected_cols = [
            "STUDYID",
            "RDOMAIN",
            "USUBJID",
            "IDVAR",
            "IDVARVAL",
            "QNAM",
            "QLABEL",
            "QVAL",
            "QORIG",
            "QEVAL",
        ]
        assert list(result.columns) == expected_cols

    def test_rdomain_set_correctly(
        self, parent_ae_df: pd.DataFrame, supp_vars: list[SuppVariable]
    ) -> None:
        """RDOMAIN is set to the parent domain."""
        result = generate_suppqual(parent_ae_df, "AE", "STUDY1", supp_vars)

        assert all(result["RDOMAIN"] == "AE")

    def test_idvar_set_to_seq(
        self, parent_ae_df: pd.DataFrame, supp_vars: list[SuppVariable]
    ) -> None:
        """IDVAR is {domain}SEQ."""
        result = generate_suppqual(parent_ae_df, "AE", "STUDY1", supp_vars)

        assert all(result["IDVAR"] == "AESEQ")

    def test_idvarval_is_string_int(
        self, parent_ae_df: pd.DataFrame, supp_vars: list[SuppVariable]
    ) -> None:
        """IDVARVAL is string representation of integer SEQ value."""
        result = generate_suppqual(parent_ae_df, "AE", "STUDY1", supp_vars)

        assert all(v in ("1", "2") for v in result["IDVARVAL"])

    def test_null_values_skipped(self) -> None:
        """Null source values do not produce SUPPQUAL records."""
        parent_df = pd.DataFrame(
            {
                "USUBJID": ["S01", "S02"],
                "CMSEQ": [1, 2],
                "EXTRA": [None, "some value"],
            }
        )
        supp_vars = [
            SuppVariable(
                qnam="EXTRA",
                qlabel="Extra Field",
                source_col="EXTRA",
                qorig="CRF",
            ),
        ]
        result = generate_suppqual(parent_df, "CM", "STUDY1", supp_vars)

        # Only S02 has non-null EXTRA
        assert len(result) == 1
        assert result.iloc[0]["USUBJID"] == "S02"

    def test_empty_string_skipped(self) -> None:
        """Empty string source values do not produce SUPPQUAL records."""
        parent_df = pd.DataFrame(
            {
                "USUBJID": ["S01"],
                "AESEQ": [1],
                "NOTES": [""],
            }
        )
        supp_vars = [
            SuppVariable(
                qnam="NOTES",
                qlabel="Notes",
                source_col="NOTES",
                qorig="CRF",
            ),
        ]
        result = generate_suppqual(parent_df, "AE", "STUDY1", supp_vars)

        assert result.empty

    def test_qnam_truncation(self) -> None:
        """QNAM is truncated to 8 characters in output."""
        # SuppVariable validation enforces max 8, but test truncation in generate
        parent_df = pd.DataFrame(
            {
                "USUBJID": ["S01"],
                "LBSEQ": [1],
                "LONGCOL": ["value"],
            }
        )
        supp_vars = [
            SuppVariable(
                qnam="LONGVAL",  # 7 chars, valid
                qlabel="Long Value Name",
                source_col="LONGCOL",
                qorig="CRF",
            ),
        ]
        result = generate_suppqual(parent_df, "LB", "STUDY1", supp_vars)

        assert len(result) == 1
        assert len(result.iloc[0]["QNAM"]) <= 8

    def test_qlabel_truncation(self) -> None:
        """QLABEL is truncated to 40 characters in output."""
        parent_df = pd.DataFrame(
            {
                "USUBJID": ["S01"],
                "AESEQ": [1],
                "COL": ["val"],
            }
        )
        # Label is exactly 40 chars (SuppVariable max_length=40)
        label = "A" * 40
        supp_vars = [
            SuppVariable(
                qnam="COL",
                qlabel=label,
                source_col="COL",
                qorig="CRF",
            ),
        ]
        result = generate_suppqual(parent_df, "AE", "STUDY1", supp_vars)

        assert len(result.iloc[0]["QLABEL"]) <= 40

    def test_empty_parent_df(self, supp_vars: list[SuppVariable]) -> None:
        """Empty parent DataFrame produces empty SUPPQUAL."""
        parent_df = pd.DataFrame(columns=["USUBJID", "AESEQ", "AESEV", "AEACNOTH"])
        result = generate_suppqual(parent_df, "AE", "STUDY1", supp_vars)

        assert result.empty
        assert "QNAM" in result.columns

    def test_study_id_propagated(
        self, parent_ae_df: pd.DataFrame, supp_vars: list[SuppVariable]
    ) -> None:
        """STUDYID is set to the provided study_id."""
        result = generate_suppqual(parent_ae_df, "AE", "MY-STUDY-123", supp_vars)

        assert all(result["STUDYID"] == "MY-STUDY-123")

    def test_qeval_propagated(self) -> None:
        """QEVAL is set from the SuppVariable."""
        parent_df = pd.DataFrame(
            {
                "USUBJID": ["S01"],
                "AESEQ": [1],
                "RATING": ["HIGH"],
            }
        )
        supp_vars = [
            SuppVariable(
                qnam="RATING",
                qlabel="Severity Rating",
                source_col="RATING",
                qorig="CRF",
                qeval="INVESTIGATOR",
            ),
        ]
        result = generate_suppqual(parent_df, "AE", "STUDY1", supp_vars)

        assert result.iloc[0]["QEVAL"] == "INVESTIGATOR"


# ---------------------------------------------------------------------------
# Tests: validate_suppqual_integrity
# ---------------------------------------------------------------------------


class TestValidateSuppqualIntegrity:
    """Tests for validate_suppqual_integrity()."""

    def test_valid_data_no_errors(
        self, parent_ae_df: pd.DataFrame, supp_vars: list[SuppVariable]
    ) -> None:
        """Valid SUPPQUAL data passes integrity check."""
        supp_df = generate_suppqual(parent_ae_df, "AE", "STUDY1", supp_vars)
        errors = validate_suppqual_integrity(supp_df, parent_ae_df, "AE")

        assert errors == []

    def test_orphaned_idvarval(self) -> None:
        """Detects IDVARVAL not found in parent SEQ."""
        parent_df = pd.DataFrame(
            {
                "USUBJID": ["S01"],
                "AESEQ": [1],
            }
        )
        # Manually create SUPPQUAL with orphan reference
        supp_df = pd.DataFrame(
            {
                "STUDYID": ["STUDY1"],
                "RDOMAIN": ["AE"],
                "USUBJID": ["S01"],
                "IDVAR": ["AESEQ"],
                "IDVARVAL": ["999"],  # Does not exist in parent
                "QNAM": ["EXTRA"],
                "QLABEL": ["Extra"],
                "QVAL": ["value"],
                "QORIG": ["CRF"],
                "QEVAL": [""],
            }
        )
        errors = validate_suppqual_integrity(supp_df, parent_df, "AE")

        assert len(errors) == 1
        assert "999" in errors[0]
        assert "Orphaned" in errors[0]

    def test_rdomain_mismatch(self) -> None:
        """Detects RDOMAIN not matching expected domain."""
        parent_df = pd.DataFrame(
            {
                "USUBJID": ["S01"],
                "AESEQ": [1],
            }
        )
        supp_df = pd.DataFrame(
            {
                "STUDYID": ["STUDY1"],
                "RDOMAIN": ["CM"],  # Wrong domain
                "USUBJID": ["S01"],
                "IDVAR": ["AESEQ"],
                "IDVARVAL": ["1"],
                "QNAM": ["EXTRA"],
                "QLABEL": ["Extra"],
                "QVAL": ["value"],
                "QORIG": ["CRF"],
                "QEVAL": [""],
            }
        )
        errors = validate_suppqual_integrity(supp_df, parent_df, "AE")

        assert any("RDOMAIN mismatch" in e for e in errors)

    def test_idvar_mismatch(self) -> None:
        """Detects IDVAR not matching {domain}SEQ."""
        parent_df = pd.DataFrame(
            {
                "USUBJID": ["S01"],
                "AESEQ": [1],
            }
        )
        supp_df = pd.DataFrame(
            {
                "STUDYID": ["STUDY1"],
                "RDOMAIN": ["AE"],
                "USUBJID": ["S01"],
                "IDVAR": ["CMSEQ"],  # Wrong IDVAR
                "IDVARVAL": ["1"],
                "QNAM": ["EXTRA"],
                "QLABEL": ["Extra"],
                "QVAL": ["value"],
                "QORIG": ["CRF"],
                "QEVAL": [""],
            }
        )
        errors = validate_suppqual_integrity(supp_df, parent_df, "AE")

        assert any("IDVAR mismatch" in e for e in errors)

    def test_duplicate_qnam_detected(self) -> None:
        """Detects duplicate QNAM for same USUBJID+IDVARVAL."""
        parent_df = pd.DataFrame(
            {
                "USUBJID": ["S01"],
                "AESEQ": [1],
            }
        )
        supp_df = pd.DataFrame(
            {
                "STUDYID": ["STUDY1", "STUDY1"],
                "RDOMAIN": ["AE", "AE"],
                "USUBJID": ["S01", "S01"],
                "IDVAR": ["AESEQ", "AESEQ"],
                "IDVARVAL": ["1", "1"],
                "QNAM": ["EXTRA", "EXTRA"],  # Duplicate
                "QLABEL": ["Extra", "Extra"],
                "QVAL": ["val1", "val2"],
                "QORIG": ["CRF", "CRF"],
                "QEVAL": ["", ""],
            }
        )
        errors = validate_suppqual_integrity(supp_df, parent_df, "AE")

        assert any("Duplicate QNAM" in e for e in errors)

    def test_empty_supp_df_no_errors(self) -> None:
        """Empty SUPPQUAL DataFrame produces no errors."""
        parent_df = pd.DataFrame(
            {
                "USUBJID": ["S01"],
                "AESEQ": [1],
            }
        )
        supp_df = pd.DataFrame(
            columns=[
                "STUDYID",
                "RDOMAIN",
                "USUBJID",
                "IDVAR",
                "IDVARVAL",
                "QNAM",
                "QLABEL",
                "QVAL",
                "QORIG",
                "QEVAL",
            ]
        )
        errors = validate_suppqual_integrity(supp_df, parent_df, "AE")

        assert errors == []


# ---------------------------------------------------------------------------
# Tests: SuppVariable model validation
# ---------------------------------------------------------------------------


class TestSuppVariable:
    """Tests for SuppVariable Pydantic model."""

    def test_valid_suppvariable(self) -> None:
        """Valid SuppVariable passes validation."""
        sv = SuppVariable(
            qnam="AESEV",
            qlabel="Severity",
            source_col="AESEV",
            qorig="CRF",
        )
        assert sv.qnam == "AESEV"
        assert sv.qorig == "CRF"

    def test_qnam_too_long(self) -> None:
        """QNAM over 8 chars raises ValidationError."""
        with pytest.raises(Exception):  # noqa: B017
            SuppVariable(
                qnam="TOOLONGVAR",  # 10 chars
                qlabel="Label",
                source_col="col",
                qorig="CRF",
            )

    def test_qnam_non_alphanumeric(self) -> None:
        """QNAM with special characters raises ValidationError."""
        with pytest.raises(Exception):  # noqa: B017
            SuppVariable(
                qnam="AB_CD",  # underscore not allowed
                qlabel="Label",
                source_col="col",
                qorig="CRF",
            )

    def test_qnam_uppercased(self) -> None:
        """QNAM is uppercased by validator."""
        sv = SuppVariable(
            qnam="aesev",
            qlabel="Severity",
            source_col="AESEV",
            qorig="CRF",
        )
        assert sv.qnam == "AESEV"

    def test_qorig_validated(self) -> None:
        """Invalid QORIG raises ValidationError."""
        with pytest.raises(Exception):  # noqa: B017
            SuppVariable(
                qnam="VAR1",
                qlabel="Label",
                source_col="col",
                qorig="INVALID",
            )

    def test_qorig_uppercased(self) -> None:
        """QORIG is uppercased by validator."""
        sv = SuppVariable(
            qnam="VAR1",
            qlabel="Label",
            source_col="col",
            qorig="crf",
        )
        assert sv.qorig == "CRF"

    def test_qlabel_too_long(self) -> None:
        """QLABEL over 40 chars raises ValidationError."""
        with pytest.raises(Exception):  # noqa: B017
            SuppVariable(
                qnam="VAR1",
                qlabel="A" * 41,
                source_col="col",
                qorig="CRF",
            )

    def test_qeval_defaults_empty(self) -> None:
        """QEVAL defaults to empty string."""
        sv = SuppVariable(
            qnam="VAR1",
            qlabel="Label",
            source_col="col",
            qorig="CRF",
        )
        assert sv.qeval == ""
