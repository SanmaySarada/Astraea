"""Tests for USUBJID generation and cross-domain validation."""

from __future__ import annotations

import pandas as pd
import pytest

from astraea.transforms.usubjid import (
    extract_usubjid_components,
    generate_usubjid,
    generate_usubjid_column,
    validate_usubjid_consistency,
)

# ---------------------------------------------------------------------------
# generate_usubjid
# ---------------------------------------------------------------------------


class TestGenerateUsubjid:
    def test_basic(self):
        assert generate_usubjid("301", "04401", "01") == "301-04401-01"

    def test_custom_delimiter(self):
        assert generate_usubjid("301", "04401", "01", delimiter=".") == "301.04401.01"

    def test_whitespace_stripping(self):
        assert generate_usubjid(" 301 ", " 04401 ", " 01 ") == "301-04401-01"

    def test_longer_ids(self):
        assert generate_usubjid("PHA022121-C301", "04401", "001") == "PHA022121-C301-04401-001"

    def test_empty_components_raises(self):
        with pytest.raises(ValueError, match="empty or NaN"):
            generate_usubjid("", "", "")

    def test_numeric_like_values(self):
        """Ensure string conversion works for any input."""
        assert generate_usubjid("301", "04401", "01") == "301-04401-01"

    def test_nan_siteid_raises(self):
        with pytest.raises(ValueError, match="siteid.*empty or NaN"):
            generate_usubjid("301", float("nan"), "01")

    def test_nan_subjid_raises(self):
        with pytest.raises(ValueError, match="subjid.*empty or NaN"):
            generate_usubjid("301", "04401", float("nan"))

    def test_none_component_raises(self):
        with pytest.raises(ValueError, match="siteid.*empty or NaN"):
            generate_usubjid("301", None, "01")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="studyid.*empty or NaN"):
            generate_usubjid("", "04401", "01")


# ---------------------------------------------------------------------------
# extract_usubjid_components
# ---------------------------------------------------------------------------


class TestExtractUsubjidComponents:
    def test_three_parts(self):
        result = extract_usubjid_components("301-04401-01")
        assert result == {"studyid": "301", "siteid": "04401", "subjid": "01"}

    def test_custom_delimiter(self):
        result = extract_usubjid_components("301.04401.01", delimiter=".")
        assert result == {"studyid": "301", "siteid": "04401", "subjid": "01"}

    def test_one_part_warns(self):
        result = extract_usubjid_components("NOHYPHEN")
        assert result["studyid"] == "NOHYPHEN"
        assert result["siteid"] == ""
        assert result["subjid"] == ""

    def test_two_parts_warns(self):
        result = extract_usubjid_components("301-04401")
        assert result["studyid"] == "301"
        assert result["siteid"] == "04401"
        assert result["subjid"] == ""

    def test_four_parts_joins_remainder(self):
        result = extract_usubjid_components("PHA-C301-04401-01")
        assert result["studyid"] == "PHA"
        assert result["siteid"] == "C301"
        assert result["subjid"] == "04401-01"

    def test_whitespace_stripped(self):
        result = extract_usubjid_components("  301-04401-01  ")
        assert result == {"studyid": "301", "siteid": "04401", "subjid": "01"}


# ---------------------------------------------------------------------------
# generate_usubjid_column
# ---------------------------------------------------------------------------


class TestGenerateUsubjidColumn:
    def test_with_constant_studyid(self):
        df = pd.DataFrame(
            {
                "SITEID": ["04401", "04402"],
                "SUBJID": ["01", "02"],
            }
        )
        result = generate_usubjid_column(df, studyid_value="301")
        assert list(result) == ["301-04401-01", "301-04402-02"]

    def test_with_studyid_column(self):
        df = pd.DataFrame(
            {
                "STUDYID": ["301", "301"],
                "SITEID": ["04401", "04402"],
                "SUBJID": ["01", "02"],
            }
        )
        result = generate_usubjid_column(df)
        assert list(result) == ["301-04401-01", "301-04402-02"]

    def test_whitespace_in_columns(self):
        df = pd.DataFrame(
            {
                "SITEID": [" 04401 ", "04402"],
                "SUBJID": ["01 ", " 02"],
            }
        )
        result = generate_usubjid_column(df, studyid_value="301")
        assert list(result) == ["301-04401-01", "301-04402-02"]

    def test_missing_column_raises(self):
        df = pd.DataFrame({"SITEID": ["04401"]})
        with pytest.raises(KeyError, match="Missing required columns"):
            generate_usubjid_column(df, studyid_value="301")

    def test_missing_studyid_col_when_no_value(self):
        df = pd.DataFrame(
            {
                "SITEID": ["04401"],
                "SUBJID": ["01"],
            }
        )
        with pytest.raises(KeyError, match="Missing required columns"):
            generate_usubjid_column(df)

    def test_custom_column_names(self):
        df = pd.DataFrame(
            {
                "study": ["301"],
                "site": ["04401"],
                "subj": ["01"],
            }
        )
        result = generate_usubjid_column(
            df, studyid_col="study", siteid_col="site", subjid_col="subj"
        )
        assert list(result) == ["301-04401-01"]

    def test_custom_delimiter(self):
        df = pd.DataFrame(
            {
                "SITEID": ["04401"],
                "SUBJID": ["01"],
            }
        )
        result = generate_usubjid_column(df, studyid_value="301", delimiter=".")
        assert list(result) == ["301.04401.01"]

    def test_nan_produces_na(self):
        """NaN in source columns should produce pd.NA, not '301-nan-01'."""
        df = pd.DataFrame(
            {
                "SITEID": ["04401", None, "04403"],
                "SUBJID": ["01", "02", "03"],
            }
        )
        result = generate_usubjid_column(df, studyid_value="301")
        assert result.iloc[0] == "301-04401-01"
        assert pd.isna(result.iloc[1])
        assert result.iloc[2] == "301-04403-03"

    def test_valid_column_unchanged(self):
        """Normal DataFrame still produces correct USUBJIDs."""
        df = pd.DataFrame(
            {
                "SITEID": ["04401", "04402", "04403"],
                "SUBJID": ["01", "02", "03"],
            }
        )
        result = generate_usubjid_column(df, studyid_value="301")
        expected = ["301-04401-01", "301-04402-02", "301-04403-03"]
        assert list(result) == expected


# ---------------------------------------------------------------------------
# validate_usubjid_consistency
# ---------------------------------------------------------------------------


class TestValidateUsubjidConsistency:
    def test_valid_returns_empty(self):
        datasets = {
            "DM": pd.DataFrame({"USUBJID": ["301-04401-01", "301-04402-02"]}),
            "AE": pd.DataFrame({"USUBJID": ["301-04401-01"]}),
            "VS": pd.DataFrame({"USUBJID": ["301-04401-01", "301-04402-02"]}),
        }
        errors = validate_usubjid_consistency(datasets)
        assert errors == []

    def test_orphan_detected(self):
        datasets = {
            "DM": pd.DataFrame({"USUBJID": ["301-04401-01"]}),
            "AE": pd.DataFrame({"USUBJID": ["301-04401-01", "301-99999-99"]}),
        }
        errors = validate_usubjid_consistency(datasets)
        assert len(errors) == 1
        assert "Orphan" in errors[0]
        assert "301-99999-99" in errors[0]

    def test_duplicate_in_dm(self):
        datasets = {
            "DM": pd.DataFrame({"USUBJID": ["301-04401-01", "301-04401-01"]}),
        }
        errors = validate_usubjid_consistency(datasets)
        assert len(errors) == 1
        assert "Duplicate" in errors[0]

    def test_missing_dm(self):
        datasets = {
            "AE": pd.DataFrame({"USUBJID": ["301-04401-01"]}),
        }
        errors = validate_usubjid_consistency(datasets)
        assert len(errors) == 1
        assert "DM domain not found" in errors[0]

    def test_dm_missing_usubjid_column(self):
        datasets = {
            "DM": pd.DataFrame({"SUBJECT": ["301-04401-01"]}),
        }
        errors = validate_usubjid_consistency(datasets)
        assert len(errors) == 1
        assert "missing" in errors[0].lower()

    def test_inconsistent_format(self):
        datasets = {
            "DM": pd.DataFrame(
                {
                    "USUBJID": ["301-04401-01", "STUDY.SITE.SUBJ"],
                }
            ),
        }
        errors = validate_usubjid_consistency(datasets)
        # 301-04401-01 has 2 dashes, STUDY.SITE.SUBJ has 0 dashes
        assert any("Inconsistent" in e for e in errors)

    def test_domain_without_usubjid_skipped(self):
        """Domains without USUBJID column should be silently skipped."""
        datasets = {
            "DM": pd.DataFrame({"USUBJID": ["301-04401-01"]}),
            "TS": pd.DataFrame({"TSVAL": ["some_value"]}),
        }
        errors = validate_usubjid_consistency(datasets)
        assert errors == []

    def test_nan_values_ignored(self):
        """NaN/missing USUBJIDs should not cause false positives."""
        datasets = {
            "DM": pd.DataFrame({"USUBJID": ["301-04401-01", None]}),
            "AE": pd.DataFrame({"USUBJID": ["301-04401-01", None]}),
        }
        errors = validate_usubjid_consistency(datasets)
        assert errors == []
