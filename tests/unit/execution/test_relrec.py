"""Tests for RELREC model and stub generator."""

from __future__ import annotations

import pytest
from loguru import logger

from astraea.execution.relrec import RELREC_COLUMNS, generate_relrec_stub
from astraea.models.relrec import RelRecConfig, RelRecRecord, RelRecRelationship


# ---------------------------------------------------------------------------
# RelRecRecord model tests
# ---------------------------------------------------------------------------


class TestRelRecRecord:
    def test_relrec_record_model(self) -> None:
        record = RelRecRecord(
            studyid="STUDY01",
            rdomain="AE",
            usubjid="STUDY01-001-001",
            idvar="AESEQ",
            idvarval="1",
            reltype="ONE",
            relid="REL001",
        )
        assert record.studyid == "STUDY01"
        assert record.rdomain == "AE"
        assert record.reltype == "ONE"

    def test_relrec_record_uppercase_rdomain(self) -> None:
        record = RelRecRecord(
            studyid="S", rdomain="ae", usubjid="U",
            idvar="V", idvarval="1", reltype="ONE", relid="R1",
        )
        assert record.rdomain == "AE"

    def test_relrec_record_validates_reltype(self) -> None:
        with pytest.raises(ValueError, match="ONE.*MANY"):
            RelRecRecord(
                studyid="S", rdomain="AE", usubjid="U",
                idvar="V", idvarval="1", reltype="INVALID", relid="R1",
            )

    def test_relrec_record_many_reltype(self) -> None:
        record = RelRecRecord(
            studyid="S", rdomain="CM", usubjid="U",
            idvar="CMSEQ", idvarval="3", reltype="MANY", relid="R2",
        )
        assert record.reltype == "MANY"


# ---------------------------------------------------------------------------
# RelRecConfig model tests
# ---------------------------------------------------------------------------


class TestRelRecConfig:
    def test_relrec_config_model(self) -> None:
        config = RelRecConfig(
            relationships=[
                RelRecRelationship(
                    domain_1="AE", idvar_1="AESEQ",
                    domain_2="CM", idvar_2="CMSEQ",
                    description="AE treated by CM",
                ),
            ]
        )
        assert len(config.relationships) == 1
        assert config.relationships[0].domain_1 == "AE"

    def test_relrec_config_empty(self) -> None:
        config = RelRecConfig()
        assert config.relationships == []

    def test_relrec_config_docstring_mentions_deferral(self) -> None:
        """Verify RelRecConfig documents deferral in its docstring."""
        assert "deferred" in RelRecConfig.__doc__.lower()
        assert "PITFALLS" in RelRecConfig.__doc__


# ---------------------------------------------------------------------------
# generate_relrec_stub tests
# ---------------------------------------------------------------------------


class TestGenerateRelrecStub:
    def test_relrec_stub_returns_empty_df(self) -> None:
        df = generate_relrec_stub("STUDY01")
        assert df.empty
        assert len(df) == 0

    def test_relrec_stub_column_names(self) -> None:
        df = generate_relrec_stub("STUDY01")
        assert list(df.columns) == RELREC_COLUMNS
        assert "STUDYID" in df.columns
        assert "RDOMAIN" in df.columns
        assert "RELID" in df.columns

    def test_relrec_stub_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level("WARNING"):
            # loguru needs sink added to caplog
            sink_id = logger.add(
                lambda msg: caplog.records.append(msg),
                level="WARNING",
                format="{message}",
            )
            try:
                generate_relrec_stub("STUDY01")
            finally:
                logger.remove(sink_id)

        # Check that the warning message is present
        warning_found = any(
            "stub" in str(r).lower() and "deferred" in str(r).lower()
            for r in caplog.records
        )
        assert warning_found, "Expected warning about RELREC stub deferral"

    def test_relrec_stub_validates_domains(self) -> None:
        # Valid domains should work
        df = generate_relrec_stub("STUDY01", domains=["AE", "CM", "LB"])
        assert df.empty

    def test_relrec_stub_rejects_invalid_domain(self) -> None:
        with pytest.raises(ValueError, match="not a valid SDTM domain"):
            generate_relrec_stub("STUDY01", domains=["AE", "INVALID"])
