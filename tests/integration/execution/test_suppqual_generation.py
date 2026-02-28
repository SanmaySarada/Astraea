"""SUPPQUAL generation integration tests for LB and EG parent domains.

Verifies that generate_suppqual produces referentially-intact supplemental
datasets from parent domain DataFrames, with correct null handling,
orphan detection, and duplicate QNAM validation.
"""

from __future__ import annotations

import pandas as pd
import pytest

from astraea.execution.suppqual import generate_suppqual, validate_suppqual_integrity
from astraea.models.suppqual import SuppVariable

# ---------------------------------------------------------------------------
# Fixtures: LB parent data and SUPPLB variables
# ---------------------------------------------------------------------------


@pytest.fixture()
def lb_parent_df() -> pd.DataFrame:
    """Realistic LB parent DataFrame: 10 rows, 3 subjects."""
    return pd.DataFrame(
        {
            "STUDYID": ["PHA022121-C301"] * 10,
            "DOMAIN": ["LB"] * 10,
            "USUBJID": [
                "PHA022121-C301-101-001",
                "PHA022121-C301-101-001",
                "PHA022121-C301-101-001",
                "PHA022121-C301-101-001",
                "PHA022121-C301-101-002",
                "PHA022121-C301-101-002",
                "PHA022121-C301-101-002",
                "PHA022121-C301-102-003",
                "PHA022121-C301-102-003",
                "PHA022121-C301-102-003",
            ],
            "LBSEQ": [1, 2, 3, 4, 1, 2, 3, 1, 2, 3],
            "LBTESTCD": [
                "ALT",
                "AST",
                "BILI",
                "CREAT",
                "ALT",
                "AST",
                "BILI",
                "ALT",
                "AST",
                "BILI",
            ],
            "LBORRES": [
                "25",
                "30",
                "0.8",
                "1.1",
                "40",
                "35",
                "1.2",
                "22",
                "28",
                "0.7",
            ],
            "LBORRESU": [
                "U/L",
                "U/L",
                "mg/dL",
                "mg/dL",
                "U/L",
                "U/L",
                "mg/dL",
                "U/L",
                "U/L",
                "mg/dL",
            ],
            # Supplemental candidate columns
            "LBFAST": [
                "Y",
                "Y",
                "N",
                "N",
                "Y",
                "Y",
                "N",
                "Y",
                "N",
                "N",
            ],
            "LBMETHOD": [
                "Enzymatic",
                "Enzymatic",
                "Turbidimetric",
                "Enzymatic",
                "Enzymatic",
                "Enzymatic",
                "Turbidimetric",
                "Enzymatic",
                "Enzymatic",
                "Turbidimetric",
            ],
            "LBTOX": [
                None,
                "Grade 1",
                None,
                "Grade 2",
                "Grade 1",
                None,
                None,
                None,
                None,
                "Grade 1",
            ],
        }
    )


@pytest.fixture()
def supplb_variables() -> list[SuppVariable]:
    """SUPPLB variable definitions: LBFAST and LBTOX."""
    return [
        SuppVariable(
            qnam="LBFAST",
            qlabel="Fasting Status",
            source_col="LBFAST",
            qorig="CRF",
        ),
        SuppVariable(
            qnam="LBTOX",
            qlabel="Toxicity Grade",
            source_col="LBTOX",
            qorig="CRF",
        ),
    ]


# ---------------------------------------------------------------------------
# Fixtures: EG parent data and SUPPEG variables
# ---------------------------------------------------------------------------


@pytest.fixture()
def eg_parent_df() -> pd.DataFrame:
    """Realistic EG parent DataFrame: 8 rows, 2 subjects."""
    return pd.DataFrame(
        {
            "STUDYID": ["PHA022121-C301"] * 8,
            "DOMAIN": ["EG"] * 8,
            "USUBJID": [
                "PHA022121-C301-101-001",
                "PHA022121-C301-101-001",
                "PHA022121-C301-101-001",
                "PHA022121-C301-101-001",
                "PHA022121-C301-101-002",
                "PHA022121-C301-101-002",
                "PHA022121-C301-101-002",
                "PHA022121-C301-101-002",
            ],
            "EGSEQ": [1, 2, 3, 4, 1, 2, 3, 4],
            "EGTESTCD": [
                "INTP",
                "PRMEAN",
                "QRSDUR",
                "QTMEAN",
                "INTP",
                "PRMEAN",
                "QRSDUR",
                "QTMEAN",
            ],
            "EGORRES": [
                "NORMAL",
                "162",
                "88",
                "402",
                "ABNORMAL",
                "180",
                "96",
                "440",
            ],
            # Supplemental candidate columns
            "EGCLSIG": [
                "N",
                "N",
                None,
                None,
                "Y",
                "N",
                None,
                None,
            ],
            "EGABS": [
                None,
                None,
                None,
                None,
                "Prolonged PR",
                None,
                None,
                None,
            ],
        }
    )


@pytest.fixture()
def suppeg_variables() -> list[SuppVariable]:
    """SUPPEG variable definitions: EGCLSIG and EGABS."""
    return [
        SuppVariable(
            qnam="EGCLSIG",
            qlabel="Clinically Significant",
            source_col="EGCLSIG",
            qorig="CRF",
        ),
        SuppVariable(
            qnam="EGABS",
            qlabel="Abnormality Description",
            source_col="EGABS",
            qorig="CRF",
        ),
    ]


# ===========================================================================
# Test class: SUPPLB generation
# ===========================================================================


class TestSUPPLBGeneration:
    """Tests for SUPPLB generation from LB parent domain."""

    def test_supplb_generation(
        self,
        lb_parent_df: pd.DataFrame,
        supplb_variables: list[SuppVariable],
    ) -> None:
        """SUPPLB has correct RDOMAIN, IDVAR, and QNAM values."""
        supplb = generate_suppqual(
            lb_parent_df,
            "LB",
            "PHA022121-C301",
            supplb_variables,
        )

        assert not supplb.empty
        assert (supplb["RDOMAIN"] == "LB").all()
        assert (supplb["IDVAR"] == "LBSEQ").all()
        assert set(supplb["QNAM"].unique()) == {"LBFAST", "LBTOX"}

    def test_supplb_null_skipped(
        self,
        lb_parent_df: pd.DataFrame,
        supplb_variables: list[SuppVariable],
    ) -> None:
        """Null LBTOX values do NOT produce SUPPQUAL records."""
        supplb = generate_suppqual(
            lb_parent_df,
            "LB",
            "PHA022121-C301",
            supplb_variables,
        )

        # LBTOX has 4 non-null values out of 10 rows
        lbtox_records = supplb[supplb["QNAM"] == "LBTOX"]
        assert len(lbtox_records) == 4

    def test_supplb_referential_integrity(
        self,
        lb_parent_df: pd.DataFrame,
        supplb_variables: list[SuppVariable],
    ) -> None:
        """validate_suppqual_integrity returns 0 errors for correctly generated SUPPLB."""
        supplb = generate_suppqual(
            lb_parent_df,
            "LB",
            "PHA022121-C301",
            supplb_variables,
        )

        errors = validate_suppqual_integrity(supplb, lb_parent_df, "LB")
        assert errors == []

    def test_supplb_row_count(
        self,
        lb_parent_df: pd.DataFrame,
        supplb_variables: list[SuppVariable],
    ) -> None:
        """Row count = non-null LBFAST records + non-null LBTOX records."""
        supplb = generate_suppqual(
            lb_parent_df,
            "LB",
            "PHA022121-C301",
            supplb_variables,
        )

        # LBFAST: all 10 rows are non-null
        # LBTOX: 4 rows are non-null (indices 1, 3, 4, 9)
        expected_count = 10 + 4
        assert len(supplb) == expected_count


# ===========================================================================
# Test class: SUPPEG generation
# ===========================================================================


class TestSUPPEGGeneration:
    """Tests for SUPPEG generation from EG parent domain."""

    def test_suppeg_generation(
        self,
        eg_parent_df: pd.DataFrame,
        suppeg_variables: list[SuppVariable],
    ) -> None:
        """SUPPEG has correct RDOMAIN and IDVAR."""
        suppeg = generate_suppqual(
            eg_parent_df,
            "EG",
            "PHA022121-C301",
            suppeg_variables,
        )

        assert not suppeg.empty
        assert (suppeg["RDOMAIN"] == "EG").all()
        assert (suppeg["IDVAR"] == "EGSEQ").all()

    def test_suppeg_sparse_data(
        self,
        eg_parent_df: pd.DataFrame,
        suppeg_variables: list[SuppVariable],
    ) -> None:
        """Mostly-null EGABS produces very few SUPPEG records for that QNAM."""
        suppeg = generate_suppqual(
            eg_parent_df,
            "EG",
            "PHA022121-C301",
            suppeg_variables,
        )

        # EGABS: only 1 non-null value ("Prolonged PR" for subject 002, seq 1)
        egabs_records = suppeg[suppeg["QNAM"] == "EGABS"]
        assert len(egabs_records) == 1
        assert egabs_records.iloc[0]["QVAL"] == "Prolonged PR"

    def test_suppeg_referential_integrity(
        self,
        eg_parent_df: pd.DataFrame,
        suppeg_variables: list[SuppVariable],
    ) -> None:
        """validate_suppqual_integrity returns 0 errors for SUPPEG."""
        suppeg = generate_suppqual(
            eg_parent_df,
            "EG",
            "PHA022121-C301",
            suppeg_variables,
        )

        errors = validate_suppqual_integrity(suppeg, eg_parent_df, "EG")
        assert errors == []


# ===========================================================================
# Test class: Validation edge cases
# ===========================================================================


class TestSUPPQUALValidation:
    """Tests for SUPPQUAL referential integrity validation edge cases."""

    def test_suppqual_orphan_detection(
        self,
        lb_parent_df: pd.DataFrame,
    ) -> None:
        """Validation catches IDVARVAL pointing to non-existent parent record."""
        # Create a SUPPQUAL with an orphan IDVARVAL=99 (no LBSEQ=99 in parent)
        orphan_supp = pd.DataFrame(
            {
                "STUDYID": ["PHA022121-C301"],
                "RDOMAIN": ["LB"],
                "USUBJID": ["PHA022121-C301-101-001"],
                "IDVAR": ["LBSEQ"],
                "IDVARVAL": ["99"],  # Does not exist in parent
                "QNAM": ["LBFAST"],
                "QLABEL": ["Fasting Status"],
                "QVAL": ["Y"],
                "QORIG": ["CRF"],
                "QEVAL": [""],
            }
        )

        errors = validate_suppqual_integrity(orphan_supp, lb_parent_df, "LB")
        assert len(errors) == 1
        assert "Orphaned" in errors[0]
        assert "99" in errors[0]

    def test_suppqual_duplicate_qnam_detection(
        self,
        lb_parent_df: pd.DataFrame,
    ) -> None:
        """Validation catches duplicate QNAM for same (USUBJID, IDVARVAL)."""
        # Create a SUPPQUAL with duplicate QNAM for same subject/seq
        dup_supp = pd.DataFrame(
            {
                "STUDYID": ["PHA022121-C301", "PHA022121-C301"],
                "RDOMAIN": ["LB", "LB"],
                "USUBJID": [
                    "PHA022121-C301-101-001",
                    "PHA022121-C301-101-001",
                ],
                "IDVAR": ["LBSEQ", "LBSEQ"],
                "IDVARVAL": ["1", "1"],
                "QNAM": ["LBFAST", "LBFAST"],  # Duplicate QNAM
                "QLABEL": ["Fasting Status", "Fasting Status"],
                "QVAL": ["Y", "N"],
                "QORIG": ["CRF", "CRF"],
                "QEVAL": ["", ""],
            }
        )

        errors = validate_suppqual_integrity(dup_supp, lb_parent_df, "LB")
        assert len(errors) == 1
        assert "Duplicate" in errors[0]
        assert "LBFAST" in errors[0]
