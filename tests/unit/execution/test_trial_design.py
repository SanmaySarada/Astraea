"""Tests for trial design domain builders (TA, TE, TV, TI)."""

from __future__ import annotations

import pytest

from astraea.execution.trial_design import (
    build_ta_domain,
    build_te_domain,
    build_ti_domain,
    build_tv_domain,
)
from astraea.models.trial_design import (
    ArmDef,
    ElementDef,
    IEDef,
    TrialDesignConfig,
    VisitDef,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

STUDY_ID = "PHA022121-C301"


@pytest.fixture
def basic_config() -> TrialDesignConfig:
    """Config with 2 arms, 3 elements, 5 visits, 5 I/E criteria."""
    return TrialDesignConfig(
        arms=[
            ArmDef(armcd="DRUG", arm="Drug 1000 IU", taetord=1, etcd="SCRN"),
            ArmDef(armcd="DRUG", arm="Drug 1000 IU", taetord=2, etcd="TRT"),
            ArmDef(armcd="DRUG", arm="Drug 1000 IU", taetord=3, etcd="FUP"),
            ArmDef(armcd="PBO", arm="Placebo", taetord=1, etcd="SCRN"),
            ArmDef(armcd="PBO", arm="Placebo", taetord=2, etcd="TRT"),
            ArmDef(armcd="PBO", arm="Placebo", taetord=3, etcd="FUP"),
        ],
        elements=[
            ElementDef(etcd="SCRN", element="Screening", testrl="Informed consent", teenrl="Randomization", tedur="P28D"),
            ElementDef(etcd="TRT", element="Treatment", testrl="Randomization", teenrl="Last dose"),
            ElementDef(etcd="FUP", element="Follow-up", testrl="Last dose", teenrl="End of study", tedur="P30D"),
        ],
        visits=[
            VisitDef(visitnum=1.0, visit="Screening", visitdy=-28, armcd="DRUG"),
            VisitDef(visitnum=2.0, visit="Baseline", visitdy=1, armcd="DRUG"),
            VisitDef(visitnum=3.0, visit="Week 4", visitdy=29, armcd="DRUG"),
            VisitDef(visitnum=4.0, visit="Week 8", visitdy=57, armcd="DRUG"),
            VisitDef(visitnum=5.0, visit="Follow-up", visitdy=85, armcd="DRUG"),
            VisitDef(visitnum=1.0, visit="Screening", visitdy=-28, armcd="PBO"),
            VisitDef(visitnum=2.0, visit="Baseline", visitdy=1, armcd="PBO"),
            VisitDef(visitnum=3.0, visit="Week 4", visitdy=29, armcd="PBO"),
            VisitDef(visitnum=4.0, visit="Week 8", visitdy=57, armcd="PBO"),
            VisitDef(visitnum=5.0, visit="Follow-up", visitdy=85, armcd="PBO"),
        ],
        inclusion_exclusion=[
            IEDef(ietestcd="INCL01", ietest="Age >= 18 years", iecat="INCLUSION"),
            IEDef(ietestcd="INCL02", ietest="Confirmed HAE diagnosis", iecat="INCLUSION"),
            IEDef(ietestcd="INCL03", ietest="Willing to provide consent", iecat="INCLUSION"),
            IEDef(ietestcd="EXCL01", ietest="Pregnant or nursing", iecat="EXCLUSION"),
            IEDef(ietestcd="EXCL02", ietest="Active malignancy", iecat="EXCLUSION"),
        ],
    )


# ---------------------------------------------------------------------------
# TA domain tests
# ---------------------------------------------------------------------------


class TestBuildTA:
    def test_ta_basic(self, basic_config: TrialDesignConfig) -> None:
        ta = build_ta_domain(basic_config, STUDY_ID)
        # 2 arms x 3 elements = 6 rows
        assert len(ta) == 6

    def test_ta_columns(self, basic_config: TrialDesignConfig) -> None:
        ta = build_ta_domain(basic_config, STUDY_ID)
        expected_cols = {"STUDYID", "DOMAIN", "ARMCD", "ARM", "TAETORD", "ETCD", "ELEMENT", "TABRSESS", "EPOCH"}
        assert expected_cols == set(ta.columns)
        assert (ta["DOMAIN"] == "TA").all()
        assert (ta["STUDYID"] == STUDY_ID).all()


# ---------------------------------------------------------------------------
# TE domain tests
# ---------------------------------------------------------------------------


class TestBuildTE:
    def test_te_basic(self, basic_config: TrialDesignConfig) -> None:
        te = build_te_domain(basic_config, STUDY_ID)
        assert len(te) == 3
        expected_cols = {"STUDYID", "DOMAIN", "ETCD", "ELEMENT", "TESTRL", "TEENRL", "TEDUR"}
        assert expected_cols == set(te.columns)
        assert (te["DOMAIN"] == "TE").all()


# ---------------------------------------------------------------------------
# TV domain tests
# ---------------------------------------------------------------------------


class TestBuildTV:
    def test_tv_basic(self, basic_config: TrialDesignConfig) -> None:
        tv = build_tv_domain(basic_config, STUDY_ID)
        # 5 visits x 2 arms = 10 rows
        assert len(tv) == 10

    def test_tv_visitnum(self, basic_config: TrialDesignConfig) -> None:
        tv = build_tv_domain(basic_config, STUDY_ID)
        assert "VISITNUM" in tv.columns
        assert tv["VISITNUM"].notna().all()
        # Each arm has visits 1-5
        for _, group in tv.groupby("ARMCD"):
            assert sorted(group["VISITNUM"].tolist()) == [1.0, 2.0, 3.0, 4.0, 5.0]


# ---------------------------------------------------------------------------
# TI domain tests
# ---------------------------------------------------------------------------


class TestBuildTI:
    def test_ti_basic(self, basic_config: TrialDesignConfig) -> None:
        ti = build_ti_domain(basic_config, STUDY_ID)
        assert len(ti) == 5
        expected_cols = {"STUDYID", "DOMAIN", "IETESTCD", "IETEST", "IECAT", "TIRL"}
        assert expected_cols == set(ti.columns)
        assert (ti["DOMAIN"] == "TI").all()

    def test_ti_empty(self) -> None:
        """Config with no I/E criteria -> empty TI DataFrame with correct columns."""
        config = TrialDesignConfig(
            arms=[ArmDef(armcd="A", arm="Arm A", taetord=1, etcd="E1")],
            elements=[ElementDef(etcd="E1", element="Element 1")],
            visits=[VisitDef(visitnum=1.0, visit="Visit 1", armcd="A")],
            inclusion_exclusion=None,
        )
        ti = build_ti_domain(config, STUDY_ID)
        assert ti.empty
        assert "IETESTCD" in ti.columns
        assert "IECAT" in ti.columns


# ---------------------------------------------------------------------------
# TrialDesignConfig validation tests
# ---------------------------------------------------------------------------


class TestTrialDesignConfig:
    def test_valid_config(self, basic_config: TrialDesignConfig) -> None:
        assert len(basic_config.arms) == 6
        assert len(basic_config.elements) == 3
        assert len(basic_config.visits) == 10
        assert basic_config.inclusion_exclusion is not None
        assert len(basic_config.inclusion_exclusion) == 5

    def test_config_rejects_empty_arms(self) -> None:
        with pytest.raises(Exception):
            TrialDesignConfig(
                arms=[],
                elements=[ElementDef(etcd="E1", element="Element 1")],
                visits=[VisitDef(visitnum=1.0, visit="Visit 1", armcd="A")],
            )

    def test_config_rejects_empty_elements(self) -> None:
        with pytest.raises(Exception):
            TrialDesignConfig(
                arms=[ArmDef(armcd="A", arm="Arm A", taetord=1, etcd="E1")],
                elements=[],
                visits=[VisitDef(visitnum=1.0, visit="Visit 1", armcd="A")],
            )

    def test_iecat_validation(self) -> None:
        with pytest.raises(ValueError, match="INCLUSION.*EXCLUSION"):
            IEDef(ietestcd="I01", ietest="Test", iecat="INVALID")

    def test_armcd_uppercase(self) -> None:
        arm = ArmDef(armcd="drug", arm="Drug Arm", taetord=1, etcd="E1")
        assert arm.armcd == "DRUG"
