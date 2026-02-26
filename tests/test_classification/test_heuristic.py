"""Tests for deterministic heuristic domain scoring.

Tests filename pattern matching, variable overlap scoring, combined
heuristic scoring, and multi-file merge detection.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from astraea.classification.heuristic import (
    FILENAME_PATTERNS,
    MERGE_PREFIXES,
    compute_heuristic_scores,
    detect_merge_groups,
    score_by_filename,
    score_by_variables,
)
from astraea.models.classification import HeuristicScore
from astraea.models.profiling import DatasetProfile, VariableProfile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_profile(
    filename: str,
    var_names: list[str],
    edc_columns: list[str] | None = None,
) -> DatasetProfile:
    """Create a minimal DatasetProfile with given variable names."""
    edc_set = set(edc_columns or [])
    variables = [
        VariableProfile(
            name=name,
            dtype="character",
            n_total=100,
            n_missing=0,
            n_unique=10,
            missing_pct=0.0,
            is_edc_column=name in edc_set,
        )
        for name in var_names
    ]
    return DatasetProfile(
        filename=filename,
        row_count=100,
        col_count=len(var_names),
        variables=variables,
        edc_columns=list(edc_set),
    )


def _make_mock_ref(domains: dict[str, list[str]]) -> MagicMock:
    """Create a mock SDTMReference with given domain -> variable lists."""
    ref = MagicMock()
    ref.list_domains.return_value = sorted(domains.keys())

    def get_spec(domain: str) -> MagicMock | None:
        domain = domain.upper()
        if domain not in domains:
            return None
        spec = MagicMock()
        spec.variables = []
        for vname in domains[domain]:
            v = MagicMock()
            v.name = vname
            spec.variables.append(v)
        return spec

    ref.get_domain_spec = get_spec
    return ref


# ---------------------------------------------------------------------------
# score_by_filename tests
# ---------------------------------------------------------------------------


class TestScoreByFilename:
    """Tests for filename-based heuristic scoring."""

    def test_exact_match_ae(self) -> None:
        """ae.sas7bdat should match AE with score 1.0."""
        scores = score_by_filename("ae.sas7bdat")
        assert len(scores) >= 1
        ae_score = next(s for s in scores if s.domain == "AE")
        assert ae_score.score == 1.0
        assert "filename exact match" in ae_score.signals[0]

    def test_exact_match_dm(self) -> None:
        """dm.sas7bdat should match DM with score 1.0."""
        scores = score_by_filename("dm.sas7bdat")
        dm_score = next(s for s in scores if s.domain == "DM")
        assert dm_score.score == 1.0

    def test_prefix_match_lb_biochem(self) -> None:
        """lb_biochem.sas7bdat should match LB with score 0.7."""
        scores = score_by_filename("lb_biochem.sas7bdat")
        lb_score = next(s for s in scores if s.domain == "LB")
        assert lb_score.score == 0.7
        assert "filename contains" in lb_score.signals[0]

    def test_contains_match_conmed(self) -> None:
        """conmed.sas7bdat should match CM with score 1.0 (exact match)."""
        scores = score_by_filename("conmed.sas7bdat")
        cm_score = next(s for s in scores if s.domain == "CM")
        assert cm_score.score == 1.0

    def test_unknown_dataset_empty(self) -> None:
        """unknown_data.sas7bdat should return empty list."""
        scores = score_by_filename("unknown_data.sas7bdat")
        assert scores == []

    def test_case_insensitive(self) -> None:
        """AE.SAS7BDAT should still match AE."""
        scores = score_by_filename("AE.SAS7BDAT")
        ae_score = next(s for s in scores if s.domain == "AE")
        assert ae_score.score == 1.0

    def test_no_extension(self) -> None:
        """Works without .sas7bdat extension."""
        scores = score_by_filename("ae")
        ae_score = next(s for s in scores if s.domain == "AE")
        assert ae_score.score == 1.0

    def test_sorted_descending(self) -> None:
        """Results should be sorted by score descending."""
        scores = score_by_filename("lb_biochem.sas7bdat")
        for i in range(len(scores) - 1):
            assert scores[i].score >= scores[i + 1].score

    def test_vital_signs(self) -> None:
        """vital.sas7bdat should match VS."""
        scores = score_by_filename("vital.sas7bdat")
        vs_score = next(s for s in scores if s.domain == "VS")
        assert vs_score.score == 1.0

    def test_ecg_matches_eg(self) -> None:
        """ecg.sas7bdat should match EG."""
        scores = score_by_filename("ecg.sas7bdat")
        eg_score = next(s for s in scores if s.domain == "EG")
        assert eg_score.score == 1.0

    def test_all_standard_domains_have_patterns(self) -> None:
        """Verify all 15 standard domains have filename patterns."""
        expected_domains = {
            "AE", "CM", "DM", "DS", "DV", "EG", "EX", "IE",
            "LB", "MH", "PE", "VS", "CE", "DA", "SV",
        }
        assert set(FILENAME_PATTERNS.keys()) == expected_domains


# ---------------------------------------------------------------------------
# score_by_variables tests
# ---------------------------------------------------------------------------


class TestScoreByVariables:
    """Tests for variable overlap-based heuristic scoring."""

    def test_ae_variables_score_high(self) -> None:
        """Dataset with AE-specific variables should score high for AE."""
        profile = _make_profile(
            "something.sas7bdat",
            ["STUDYID", "USUBJID", "AETERM", "AESTDTC", "AEENDTC", "AESEQ",
             "AEDECOD", "AEBODSYS"],
        )
        ref = _make_mock_ref({
            "AE": ["STUDYID", "DOMAIN", "USUBJID", "AESEQ", "AETERM",
                    "AEDECOD", "AEBODSYS", "AESTDTC", "AEENDTC", "AESER"],
            "DM": ["STUDYID", "DOMAIN", "USUBJID", "SUBJID", "RFSTDTC",
                    "SEX", "AGE", "RACE"],
        })
        scores = score_by_variables(profile, ref)
        assert len(scores) >= 1
        ae_score = next(s for s in scores if s.domain == "AE")
        assert ae_score.score > 0.5

    def test_non_sdtm_vars_low_score(self) -> None:
        """Dataset with non-SDTM variables should produce low/no scores."""
        profile = _make_profile(
            "custom.sas7bdat",
            ["FOO", "BAR", "BAZ", "QWERTY"],
        )
        ref = _make_mock_ref({
            "AE": ["STUDYID", "DOMAIN", "USUBJID", "AESEQ", "AETERM",
                    "AEDECOD", "AEBODSYS", "AESTDTC"],
        })
        scores = score_by_variables(profile, ref)
        # Should be empty since no meaningful overlap
        assert len(scores) == 0

    def test_excludes_common_identifiers(self) -> None:
        """Common identifiers (STUDYID, USUBJID, etc.) should not count."""
        profile = _make_profile(
            "something.sas7bdat",
            ["STUDYID", "DOMAIN", "USUBJID"],
        )
        ref = _make_mock_ref({
            "AE": ["STUDYID", "DOMAIN", "USUBJID", "AESEQ", "AETERM"],
            "DM": ["STUDYID", "DOMAIN", "USUBJID", "SUBJID", "SEX"],
        })
        scores = score_by_variables(profile, ref)
        # Common identifiers excluded, so no meaningful domain-specific overlap
        assert len(scores) == 0

    def test_edc_columns_excluded(self) -> None:
        """EDC system columns should not be counted in overlap."""
        profile = _make_profile(
            "ae.sas7bdat",
            ["STUDYID", "USUBJID", "AETERM", "projectid", "instanceId"],
            edc_columns=["projectid", "instanceId"],
        )
        ref = _make_mock_ref({
            "AE": ["STUDYID", "DOMAIN", "USUBJID", "AESEQ", "AETERM",
                    "AEDECOD"],
        })
        scores = score_by_variables(profile, ref)
        # AETERM should still match
        assert len(scores) >= 1

    def test_sorted_descending(self) -> None:
        """Results should be sorted by score descending."""
        profile = _make_profile(
            "mixed.sas7bdat",
            ["AETERM", "AEDECOD", "CMTRT", "CMDECOD"],
        )
        ref = _make_mock_ref({
            "AE": ["STUDYID", "DOMAIN", "USUBJID", "AETERM", "AEDECOD",
                    "AEBODSYS"],
            "CM": ["STUDYID", "DOMAIN", "USUBJID", "CMTRT", "CMDECOD",
                    "CMCAT"],
        })
        scores = score_by_variables(profile, ref)
        for i in range(len(scores) - 1):
            assert scores[i].score >= scores[i + 1].score

    def test_signal_format(self) -> None:
        """Signal should include overlap fraction."""
        profile = _make_profile(
            "ae_data.sas7bdat",
            ["AETERM", "AEDECOD"],
        )
        ref = _make_mock_ref({
            "AE": ["STUDYID", "DOMAIN", "USUBJID", "AETERM", "AEDECOD",
                    "AEBODSYS"],
        })
        scores = score_by_variables(profile, ref)
        assert len(scores) >= 1
        assert "variable overlap:" in scores[0].signals[0]


# ---------------------------------------------------------------------------
# compute_heuristic_scores tests
# ---------------------------------------------------------------------------


class TestComputeHeuristicScores:
    """Tests for combined heuristic scoring."""

    def test_filename_only(self) -> None:
        """Should work with filename only (no profile/ref)."""
        scores = compute_heuristic_scores("ae.sas7bdat")
        assert scores[0].domain == "AE"
        assert scores[0].score == 1.0

    def test_combines_filename_and_variables(self) -> None:
        """Should combine both sources, taking max score per domain."""
        profile = _make_profile(
            "ae.sas7bdat",
            ["AETERM", "AEDECOD", "AEBODSYS"],
        )
        ref = _make_mock_ref({
            "AE": ["STUDYID", "DOMAIN", "USUBJID", "AETERM", "AEDECOD",
                    "AEBODSYS"],
        })
        scores = compute_heuristic_scores("ae.sas7bdat", profile, ref)
        ae_score = next(s for s in scores if s.domain == "AE")
        # Filename gives 1.0, variable gives some score; max is 1.0
        assert ae_score.score == 1.0
        # Should have signals from both sources
        assert len(ae_score.signals) >= 2

    def test_unclassified_when_no_match(self) -> None:
        """Should return UNCLASSIFIED when no domain scores >= 0.3."""
        scores = compute_heuristic_scores("random_unknown_file.sas7bdat")
        assert len(scores) == 1
        assert scores[0].domain == "UNCLASSIFIED"
        assert scores[0].score == 0.0
        assert "no heuristic match" in scores[0].signals

    def test_unclassified_with_low_variable_scores(self) -> None:
        """UNCLASSIFIED even with variable scores if all below 0.3."""
        profile = _make_profile(
            "weird_data.sas7bdat",
            ["XYZVAR1", "XYZVAR2"],
        )
        ref = _make_mock_ref({
            "AE": ["STUDYID", "DOMAIN", "USUBJID", "AETERM", "AEDECOD",
                    "AEBODSYS", "AESTDTC", "AEENDTC", "AESER", "AEREL"],
        })
        scores = compute_heuristic_scores(
            "weird_data.sas7bdat", profile, ref
        )
        assert scores[0].domain == "UNCLASSIFIED"

    def test_variable_score_wins_when_higher(self) -> None:
        """When variable overlap gives higher score, it should be used."""
        # lb_something filename gives 0.7 for LB
        # But if variable overlap gives 0.9, that should win
        profile = _make_profile(
            "lb_custom.sas7bdat",
            ["LBTESTCD", "LBTEST", "LBORRES", "LBORRESU", "LBSTRESC",
             "LBSTRESN", "LBSTRESU", "LBCAT"],
        )
        ref = _make_mock_ref({
            "LB": ["STUDYID", "DOMAIN", "USUBJID", "LBSEQ", "LBTESTCD",
                    "LBTEST", "LBCAT", "LBORRES", "LBORRESU", "LBSTRESC",
                    "LBSTRESN", "LBSTRESU"],
        })
        scores = compute_heuristic_scores("lb_custom.sas7bdat", profile, ref)
        lb_score = next(s for s in scores if s.domain == "LB")
        # Variable overlap should give higher score than filename's 0.7
        assert lb_score.score > 0.7


# ---------------------------------------------------------------------------
# detect_merge_groups tests
# ---------------------------------------------------------------------------


class TestDetectMergeGroups:
    """Tests for multi-file merge group detection."""

    def test_lb_merge_group(self) -> None:
        """Multiple lb_ files should group into LB domain."""
        names = ["lb_biochem.sas7bdat", "lb_hem.sas7bdat", "lb_urin.sas7bdat",
                 "ae.sas7bdat", "dm.sas7bdat"]
        groups = detect_merge_groups(names)
        assert "LB" in groups
        assert set(groups["LB"]) == {
            "lb_biochem.sas7bdat", "lb_hem.sas7bdat", "lb_urin.sas7bdat"
        }

    def test_no_merges_for_single_files(self) -> None:
        """Single files per domain should not produce merge groups."""
        names = ["ae.sas7bdat", "dm.sas7bdat", "cm.sas7bdat"]
        groups = detect_merge_groups(names)
        assert groups == {}

    def test_eg_merge_group(self) -> None:
        """Multiple eg_ files should group into EG domain."""
        names = ["eg_resting.sas7bdat", "eg_exercise.sas7bdat"]
        groups = detect_merge_groups(names)
        assert "EG" in groups
        assert len(groups["EG"]) == 2

    def test_requires_two_or_more(self) -> None:
        """Merge groups require at least 2 datasets."""
        names = ["lb_biochem.sas7bdat", "ae.sas7bdat"]
        groups = detect_merge_groups(names)
        # Only one lb_ file, so no LB merge group
        assert "LB" not in groups

    def test_mixed_groups(self) -> None:
        """Should detect multiple merge groups simultaneously."""
        names = [
            "lb_biochem.sas7bdat", "lb_hem.sas7bdat",
            "eg_resting.sas7bdat", "eg_exercise.sas7bdat",
            "ae.sas7bdat",
        ]
        groups = detect_merge_groups(names)
        assert "LB" in groups
        assert "EG" in groups
        assert len(groups["LB"]) == 2
        assert len(groups["EG"]) == 2

    def test_case_insensitive(self) -> None:
        """Should handle mixed case filenames."""
        names = ["LB_BIOCHEM.SAS7BDAT", "LB_HEM.SAS7BDAT"]
        groups = detect_merge_groups(names)
        assert "LB" in groups

    def test_empty_input(self) -> None:
        """Empty list should return empty dict."""
        assert detect_merge_groups([]) == {}
