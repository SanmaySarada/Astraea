"""Tests for derivation rule parser and column resolution helpers."""

from __future__ import annotations

import pandas as pd
import pytest

from astraea.execution.pattern_handlers import (
    _extract_race_from_col,
    _resolve_column,
    parse_derivation_rule,
)


class TestParseDerivationRule:
    def test_parse_simple(self) -> None:
        keyword, args = parse_derivation_rule("CONCAT('a', '-', 'b')")
        assert keyword == "CONCAT"
        assert args == ["a", "-", "b"]

    def test_parse_with_dataset_prefix(self) -> None:
        keyword, args = parse_derivation_rule(
            "CONCAT(dm.AGE, '-', irt.SSITENUM)"
        )
        assert keyword == "CONCAT"
        assert args == ["AGE", "-", "SSITENUM"]

    def test_parse_bare_keyword(self) -> None:
        keyword, args = parse_derivation_rule("GENERATE_USUBJID")
        assert keyword == "GENERATE_USUBJID"
        assert args == []

    def test_parse_single_arg(self) -> None:
        keyword, args = parse_derivation_rule("ISO8601_DATE(AESTDAT_INT)")
        assert keyword == "ISO8601_DATE"
        assert args == ["AESTDAT_INT"]

    def test_parse_preserves_numeric_literal_with_dot(self) -> None:
        """Numeric literals like 3.14 should NOT have dot-prefix stripped."""
        keyword, args = parse_derivation_rule("CONCAT('3.14', col)")
        assert keyword == "CONCAT"
        assert args == ["3.14", "col"]

    def test_parse_multiple_race_cols(self) -> None:
        keyword, args = parse_derivation_rule(
            "RACE_CHECKBOX(dm.RACEAME, dm.RACEASI, dm.RACEWHI)"
        )
        assert keyword == "RACE_CHECKBOX"
        assert args == ["RACEAME", "RACEASI", "RACEWHI"]

    def test_parse_keyword_case_insensitive(self) -> None:
        keyword, _ = parse_derivation_rule("concat('a')")
        assert keyword == "CONCAT"

    def test_parse_whitespace_around_parens(self) -> None:
        keyword, args = parse_derivation_rule("  ISO8601_DATE (COL1)  ")
        assert keyword == "ISO8601_DATE"
        assert args == ["COL1"]


class TestResolveColumn:
    @pytest.fixture()
    def df_with_subject(self) -> pd.DataFrame:
        return pd.DataFrame({"Subject": ["001"], "SiteNumber": ["100"]})

    def test_resolve_exact_match(self, df_with_subject: pd.DataFrame) -> None:
        assert _resolve_column(df_with_subject, "Subject", {}) == "Subject"

    def test_resolve_edc_alias(self, df_with_subject: pd.DataFrame) -> None:
        assert _resolve_column(df_with_subject, "SSUBJID", {}) == "Subject"

    def test_resolve_edc_alias_site(self, df_with_subject: pd.DataFrame) -> None:
        assert _resolve_column(df_with_subject, "SSITENUM", {}) == "SiteNumber"

    def test_resolve_custom_alias(self) -> None:
        df = pd.DataFrame({"ActualCol": [1]})
        result = _resolve_column(
            df, "MYCOL", {"column_aliases": {"MYCOL": "ActualCol"}}
        )
        assert result == "ActualCol"

    def test_resolve_case_insensitive(self) -> None:
        df = pd.DataFrame({"subject": [1]})
        assert _resolve_column(df, "Subject", {}) == "subject"

    def test_resolve_not_found(self) -> None:
        df = pd.DataFrame({"A": [1]})
        assert _resolve_column(df, "NONEXISTENT", {}) is None

    def test_resolve_strips_dataset_prefix(self) -> None:
        df = pd.DataFrame({"COL": [1]})
        assert _resolve_column(df, "dm.COL", {}) == "COL"


class TestExtractRaceFromCol:
    def test_extract_race_raceame(self) -> None:
        df = pd.DataFrame({"RACEAME": [1]})
        assert _extract_race_from_col("RACEAME", df) == "AMERICAN INDIAN OR ALASKA NATIVE"

    def test_extract_race_racewhi(self) -> None:
        df = pd.DataFrame({"RACEWHI": [1]})
        assert _extract_race_from_col("RACEWHI", df) == "WHITE"

    def test_extract_race_raceasi(self) -> None:
        df = pd.DataFrame({"RACEASI": [1]})
        assert _extract_race_from_col("RACEASI", df) == "ASIAN"

    def test_extract_race_from_label(self) -> None:
        df = pd.DataFrame({"RACE1": [1]})
        df.attrs["column_labels"] = {"RACE1": "Native Hawaiian"}
        assert _extract_race_from_col("RACE1", df) == "NATIVE HAWAIIAN"

    def test_extract_race_unknown_col(self) -> None:
        df = pd.DataFrame({"FOOBAR": [1]})
        assert _extract_race_from_col("FOOBAR", df) is None
