"""XPT file output integration tests for Findings domains (LB, EG, PE, VS).

Verifies that Findings domain DataFrames survive XPT write-read roundtrip
with correct column counts, labels, variable name constraints, and date
imputation flag preservation. Also tests SUPPLB XPT output and cross-domain
USUBJID validation across all Findings domains.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyreadstat
import pytest

from astraea.execution.executor import DatasetExecutor
from astraea.io.xpt_writer import write_xpt_v5

# ---------------------------------------------------------------------------
# Fixtures: minimal SDTM DataFrames for each Findings domain
# ---------------------------------------------------------------------------


@pytest.fixture()
def lb_df() -> pd.DataFrame:
    """LB DataFrame: 6 rows with date imputation flags."""
    return pd.DataFrame(
        {
            "STUDYID": ["PHA022121-C301"] * 6,
            "DOMAIN": ["LB"] * 6,
            "USUBJID": [
                "PHA022121-C301-101-001",
                "PHA022121-C301-101-001",
                "PHA022121-C301-101-001",
                "PHA022121-C301-101-002",
                "PHA022121-C301-101-002",
                "PHA022121-C301-101-002",
            ],
            "LBSEQ": [1.0, 2.0, 3.0, 1.0, 2.0, 3.0],
            "LBTESTCD": ["ALT", "AST", "BILI", "ALT", "AST", "BILI"],
            "LBTEST": [
                "Alanine Aminotransferase",
                "Aspartate Aminotransferase",
                "Bilirubin",
                "Alanine Aminotransferase",
                "Aspartate Aminotransferase",
                "Bilirubin",
            ],
            "LBORRES": ["25", "30", "0.8", "40", "35", "1.2"],
            "LBORRESU": ["U/L", "U/L", "mg/dL", "U/L", "U/L", "mg/dL"],
            "LBSTRESC": ["25", "30", "0.8", "40", "35", "1.2"],
            "LBSTRESN": [25.0, 30.0, 0.8, 40.0, 35.0, 1.2],
            "LBSTRESU": ["U/L", "U/L", "mg/dL", "U/L", "U/L", "mg/dL"],
            "LBNRIND": ["NORMAL", "NORMAL", "NORMAL", "HIGH", "NORMAL", "HIGH"],
            "LBDTC": [
                "2022-03-15",
                "2022-03",  # partial date (day imputed)
                "2022-03-15",
                "2022-04-01",
                "2022-04",  # partial date (day imputed)
                "2022-04-01",
            ],
            "LBDTF": ["", "D", "", "", "D", ""],
        }
    )


@pytest.fixture()
def eg_df() -> pd.DataFrame:
    """EG DataFrame: 4 rows with date imputation flag."""
    return pd.DataFrame(
        {
            "STUDYID": ["PHA022121-C301"] * 4,
            "DOMAIN": ["EG"] * 4,
            "USUBJID": [
                "PHA022121-C301-101-001",
                "PHA022121-C301-101-001",
                "PHA022121-C301-101-002",
                "PHA022121-C301-101-002",
            ],
            "EGSEQ": [1.0, 2.0, 1.0, 2.0],
            "EGTESTCD": ["INTP", "PRMEAN", "INTP", "PRMEAN"],
            "EGTEST": [
                "Interpretation",
                "PR Duration Mean",
                "Interpretation",
                "PR Duration Mean",
            ],
            "EGORRES": ["NORMAL", "162", "ABNORMAL", "180"],
            "EGORRESU": ["", "ms", "", "ms"],
            "EGSTRESC": ["NORMAL", "162", "ABNORMAL", "180"],
            "EGSTRESN": [float("nan"), 162.0, float("nan"), 180.0],
            "EGDTC": [
                "2022-03-15",
                "2022-03-15",
                "2022-04",  # partial date (day imputed)
                "2022-04-01",
            ],
            "EGTPT": ["Pre-dose", "Pre-dose", "Post-dose", "Post-dose"],
            "EGDTF": ["", "", "D", ""],
        }
    )


@pytest.fixture()
def pe_df() -> pd.DataFrame:
    """PE DataFrame: 3 rows."""
    return pd.DataFrame(
        {
            "STUDYID": ["PHA022121-C301"] * 3,
            "DOMAIN": ["PE"] * 3,
            "USUBJID": [
                "PHA022121-C301-101-001",
                "PHA022121-C301-101-001",
                "PHA022121-C301-101-002",
            ],
            "PESEQ": [1.0, 2.0, 1.0],
            "PETESTCD": ["BDSYS1", "BDSYS2", "BDSYS1"],
            "PETEST": ["Body System 1", "Body System 2", "Body System 1"],
            "PEORRES": ["NORMAL", "ABNORMAL", "NORMAL"],
            "PEDTC": ["2022-03-15", "2022-03-15", "2022-04-01"],
        }
    )


@pytest.fixture()
def vs_df() -> pd.DataFrame:
    """VS DataFrame: 4 rows with VSPOS."""
    return pd.DataFrame(
        {
            "STUDYID": ["PHA022121-C301"] * 4,
            "DOMAIN": ["VS"] * 4,
            "USUBJID": [
                "PHA022121-C301-101-001",
                "PHA022121-C301-101-001",
                "PHA022121-C301-101-002",
                "PHA022121-C301-101-002",
            ],
            "VSSEQ": [1.0, 2.0, 1.0, 2.0],
            "VSTESTCD": ["SYSBP", "DIABP", "SYSBP", "DIABP"],
            "VSTEST": [
                "Systolic Blood Pressure",
                "Diastolic Blood Pressure",
                "Systolic Blood Pressure",
                "Diastolic Blood Pressure",
            ],
            "VSORRES": ["120", "80", "135", "90"],
            "VSORRESU": ["mmHg", "mmHg", "mmHg", "mmHg"],
            "VSSTRESC": ["120", "80", "135", "90"],
            "VSSTRESN": [120.0, 80.0, 135.0, 90.0],
            "VSSTRESU": ["mmHg", "mmHg", "mmHg", "mmHg"],
            "VSPOS": ["SITTING", "SITTING", "STANDING", "STANDING"],
            "VSDTC": [
                "2022-03-15",
                "2022-03-15",
                "2022-04-01",
                "2022-04-01",
            ],
        }
    )


@pytest.fixture()
def supplb_df() -> pd.DataFrame:
    """SUPPLB DataFrame: 4 rows."""
    return pd.DataFrame(
        {
            "STUDYID": ["PHA022121-C301"] * 4,
            "RDOMAIN": ["LB"] * 4,
            "USUBJID": [
                "PHA022121-C301-101-001",
                "PHA022121-C301-101-001",
                "PHA022121-C301-101-002",
                "PHA022121-C301-101-002",
            ],
            "IDVAR": ["LBSEQ"] * 4,
            "IDVARVAL": ["1", "2", "1", "2"],
            "QNAM": ["LBFAST", "LBFAST", "LBFAST", "LBTOX"],
            "QLABEL": [
                "Fasting Status",
                "Fasting Status",
                "Fasting Status",
                "Toxicity Grade",
            ],
            "QVAL": ["Y", "Y", "Y", "Grade 1"],
            "QORIG": ["CRF"] * 4,
            "QEVAL": [""] * 4,
        }
    )


# ---------------------------------------------------------------------------
# Helper: labels for each domain
# ---------------------------------------------------------------------------

LB_LABELS = {
    "STUDYID": "Study Identifier",
    "DOMAIN": "Domain Abbreviation",
    "USUBJID": "Unique Subject Identifier",
    "LBSEQ": "Sequence Number",
    "LBTESTCD": "Lab Test or Examination Short Name",
    "LBTEST": "Lab Test or Examination Name",
    "LBORRES": "Result or Finding in Original Units",
    "LBORRESU": "Original Units",
    "LBSTRESC": "Character Result/Finding in Std Format",
    "LBSTRESN": "Numeric Result/Finding in Std Units",
    "LBSTRESU": "Standard Units",
    "LBNRIND": "Reference Range Indicator",
    "LBDTC": "Date/Time of Specimen Collection",
    "LBDTF": "Date Imputation Flag",
}

EG_LABELS = {
    "STUDYID": "Study Identifier",
    "DOMAIN": "Domain Abbreviation",
    "USUBJID": "Unique Subject Identifier",
    "EGSEQ": "Sequence Number",
    "EGTESTCD": "ECG Test or Examination Short Name",
    "EGTEST": "ECG Test or Examination Name",
    "EGORRES": "Result or Finding in Original Units",
    "EGORRESU": "Original Units",
    "EGSTRESC": "Character Result/Finding in Std Format",
    "EGSTRESN": "Numeric Result/Finding in Std Units",
    "EGDTC": "Date/Time of ECG",
    "EGTPT": "Planned Time Point Name",
    "EGDTF": "Date Imputation Flag",
}

PE_LABELS = {
    "STUDYID": "Study Identifier",
    "DOMAIN": "Domain Abbreviation",
    "USUBJID": "Unique Subject Identifier",
    "PESEQ": "Sequence Number",
    "PETESTCD": "PE Test or Exam Short Name",
    "PETEST": "PE Test or Examination Name",
    "PEORRES": "Result or Finding in Original Units",
    "PEDTC": "Date/Time of Exam",
}

VS_LABELS = {
    "STUDYID": "Study Identifier",
    "DOMAIN": "Domain Abbreviation",
    "USUBJID": "Unique Subject Identifier",
    "VSSEQ": "Sequence Number",
    "VSTESTCD": "Vital Signs Test Short Name",
    "VSTEST": "Vital Signs Test Name",
    "VSORRES": "Result or Finding in Original Units",
    "VSORRESU": "Original Units",
    "VSSTRESC": "Character Result/Finding in Std Format",
    "VSSTRESN": "Numeric Result/Finding in Std Units",
    "VSSTRESU": "Standard Units",
    "VSPOS": "Position of Subject",
    "VSDTC": "Date/Time of Measurements",
}

SUPPLB_LABELS = {
    "STUDYID": "Study Identifier",
    "RDOMAIN": "Related Domain Abbreviation",
    "USUBJID": "Unique Subject Identifier",
    "IDVAR": "Identifying Variable",
    "IDVARVAL": "Identifying Variable Value",
    "QNAM": "Qualifier Variable Name",
    "QLABEL": "Qualifier Variable Label",
    "QVAL": "Data Value",
    "QORIG": "Origin",
    "QEVAL": "Evaluator",
}


# ===========================================================================
# Test class: XPT roundtrip tests
# ===========================================================================


class TestFindingsXPTRoundtrip:
    """Verify Findings domain DataFrames survive XPT write-read roundtrip."""

    def test_lb_xpt_roundtrip(
        self,
        lb_df: pd.DataFrame,
        tmp_path: Path,
    ) -> None:
        """LB DataFrame survives XPT write-read with correct columns and rows."""
        xpt_path = tmp_path / "lb.xpt"
        write_xpt_v5(lb_df, xpt_path, table_name="LB", column_labels=LB_LABELS)

        df_read, meta = pyreadstat.read_xport(str(xpt_path))
        assert df_read.shape[0] == 6
        assert set(df_read.columns) == {c.upper() for c in lb_df.columns}

    def test_eg_xpt_roundtrip(
        self,
        eg_df: pd.DataFrame,
        tmp_path: Path,
    ) -> None:
        """EG DataFrame survives XPT write-read roundtrip."""
        xpt_path = tmp_path / "eg.xpt"
        write_xpt_v5(eg_df, xpt_path, table_name="EG", column_labels=EG_LABELS)

        df_read, meta = pyreadstat.read_xport(str(xpt_path))
        assert df_read.shape[0] == 4
        assert set(df_read.columns) == {c.upper() for c in eg_df.columns}

    def test_pe_xpt_roundtrip(
        self,
        pe_df: pd.DataFrame,
        tmp_path: Path,
    ) -> None:
        """PE DataFrame survives XPT write-read roundtrip."""
        xpt_path = tmp_path / "pe.xpt"
        write_xpt_v5(pe_df, xpt_path, table_name="PE", column_labels=PE_LABELS)

        df_read, meta = pyreadstat.read_xport(str(xpt_path))
        assert df_read.shape[0] == 3
        assert set(df_read.columns) == {c.upper() for c in pe_df.columns}

    def test_vs_xpt_roundtrip(
        self,
        vs_df: pd.DataFrame,
        tmp_path: Path,
    ) -> None:
        """VS DataFrame survives XPT write-read including VSPOS column."""
        xpt_path = tmp_path / "vs.xpt"
        write_xpt_v5(vs_df, xpt_path, table_name="VS", column_labels=VS_LABELS)

        df_read, meta = pyreadstat.read_xport(str(xpt_path))
        assert df_read.shape[0] == 4
        assert "VSPOS" in df_read.columns
        assert set(df_read.columns) == {c.upper() for c in vs_df.columns}

    def test_supplb_xpt_roundtrip(
        self,
        supplb_df: pd.DataFrame,
        tmp_path: Path,
    ) -> None:
        """SUPPLB DataFrame survives XPT write-read roundtrip."""
        xpt_path = tmp_path / "supplb.xpt"
        write_xpt_v5(
            supplb_df,
            xpt_path,
            table_name="SUPPLB",
            column_labels=SUPPLB_LABELS,
        )

        df_read, meta = pyreadstat.read_xport(str(xpt_path))
        assert df_read.shape[0] == 4
        assert set(df_read.columns) == {c.upper() for c in supplb_df.columns}


# ===========================================================================
# Test class: Variable labels and names
# ===========================================================================


class TestFindingsXPTMetadata:
    """Verify variable labels and name constraints for Findings domains."""

    def test_lb_xpt_variable_labels(
        self,
        lb_df: pd.DataFrame,
        tmp_path: Path,
    ) -> None:
        """LB column labels survive XPT roundtrip."""
        xpt_path = tmp_path / "lb.xpt"
        write_xpt_v5(lb_df, xpt_path, table_name="LB", column_labels=LB_LABELS)

        _, meta = pyreadstat.read_xport(str(xpt_path))
        labels = dict(zip(meta.column_names, meta.column_labels, strict=True))
        assert labels["LBTESTCD"] == "Lab Test or Examination Short Name"
        assert labels["LBSTRESN"] == "Numeric Result/Finding in Std Units"

    def test_xpt_variable_name_length(
        self,
        lb_df: pd.DataFrame,
        eg_df: pd.DataFrame,
        pe_df: pd.DataFrame,
        vs_df: pd.DataFrame,
        tmp_path: Path,
    ) -> None:
        """All Findings variable names are <= 8 chars (LBSTRESN is exactly 8)."""
        datasets = [
            ("lb", lb_df, LB_LABELS),
            ("eg", eg_df, EG_LABELS),
            ("pe", pe_df, PE_LABELS),
            ("vs", vs_df, VS_LABELS),
        ]
        for name, df, labels in datasets:
            xpt_path = tmp_path / f"{name}.xpt"
            write_xpt_v5(df, xpt_path, table_name=name.upper(), column_labels=labels)

            df_read, _ = pyreadstat.read_xport(str(xpt_path))
            for col in df_read.columns:
                assert len(col) <= 8, (
                    f"Variable name '{col}' in {name.upper()} exceeds 8 characters"
                )


# ===========================================================================
# Test class: Cross-domain USUBJID validation
# ===========================================================================


class TestFindingsCrossDomainUSUBJID:
    """Verify cross-domain USUBJID validation covers all Findings domains."""

    def test_cross_domain_findings_usubjid(
        self,
        lb_df: pd.DataFrame,
        eg_df: pd.DataFrame,
        pe_df: pd.DataFrame,
        vs_df: pd.DataFrame,
    ) -> None:
        """All Findings domain USUBJIDs exist in DM."""
        # Create DM with all USUBJIDs
        all_usubjids = set()
        for df in [lb_df, eg_df, pe_df, vs_df]:
            all_usubjids.update(df["USUBJID"].unique())

        dm_df = pd.DataFrame({"USUBJID": sorted(all_usubjids)})

        errors = DatasetExecutor.validate_cross_domain_usubjid(
            dm_df,
            {"LB": lb_df, "EG": eg_df, "PE": pe_df, "VS": vs_df},
        )
        assert errors == []


# ===========================================================================
# Test class: Date imputation flag roundtrip
# ===========================================================================


class TestDateImputationFlagRoundtrip:
    """Verify date imputation flags (--DTF) survive XPT roundtrip."""

    def test_lb_date_imputation_flag_roundtrip(
        self,
        lb_df: pd.DataFrame,
        tmp_path: Path,
    ) -> None:
        """LBDTF column with 'D' values survives XPT write-read."""
        xpt_path = tmp_path / "lb.xpt"
        write_xpt_v5(lb_df, xpt_path, table_name="LB", column_labels=LB_LABELS)

        df_read, _ = pyreadstat.read_xport(str(xpt_path))
        assert "LBDTF" in df_read.columns

        # Check that 2 rows have LBDTF="D"
        dtf_values = df_read["LBDTF"].fillna("").str.strip()
        d_rows = dtf_values[dtf_values == "D"]
        assert len(d_rows) == 2

        # Remaining rows should be empty string
        non_d_rows = dtf_values[dtf_values != "D"]
        assert (non_d_rows == "").all()

    def test_eg_date_imputation_flag_roundtrip(
        self,
        eg_df: pd.DataFrame,
        tmp_path: Path,
    ) -> None:
        """EGDTF column with 'D' value for 1 row survives XPT roundtrip."""
        xpt_path = tmp_path / "eg.xpt"
        write_xpt_v5(eg_df, xpt_path, table_name="EG", column_labels=EG_LABELS)

        df_read, _ = pyreadstat.read_xport(str(xpt_path))
        assert "EGDTF" in df_read.columns

        dtf_values = df_read["EGDTF"].fillna("").str.strip()
        d_rows = dtf_values[dtf_values == "D"]
        assert len(d_rows) == 1
