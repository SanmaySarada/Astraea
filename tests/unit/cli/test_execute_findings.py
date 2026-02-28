"""Tests for Findings domain routing in execute-domain CLI command.

Verifies that LB/VS/EG domains are routed through FindingsExecutor
while other domains (DM, AE, CM, etc.) continue using DatasetExecutor.
Also verifies SUPPQUAL XPT generation when FindingsExecutor returns
supplemental data.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
from typer.testing import CliRunner

from astraea.cli.app import app

runner = CliRunner()

# Patch targets at source modules (lazy imports in app.py)
_PATCH_READ_SAS = "astraea.io.sas_reader.read_sas_with_metadata"
_PATCH_LOAD_SDTM = "astraea.reference.load_sdtm_reference"
_PATCH_LOAD_CT = "astraea.reference.load_ct_reference"
_PATCH_WRITE_XPT = "astraea.io.xpt_writer.write_xpt_v5"


def _make_var(name: str, label: str, pattern: str = "assign") -> dict:
    """Create a minimal valid VariableMapping dict."""
    return {
        "sdtm_variable": name,
        "sdtm_label": label,
        "sdtm_data_type": "Char",
        "core": "Req",
        "mapping_pattern": pattern,
        "mapping_logic": f"{name} assignment",
        "confidence": 1.0,
        "confidence_level": "high",
        "confidence_rationale": "Test fixture",
    }


def _make_spec_json(domain: str, tmp_path: Path) -> Path:
    """Create a minimal valid DomainMappingSpec JSON for testing."""
    domain_classes = {"LB": "Findings", "VS": "Findings", "EG": "Findings"}
    spec = {
        "domain": domain,
        "domain_label": f"{domain} Domain",
        "domain_class": domain_classes.get(domain, "Special Purpose"),
        "structure": "One record per subject per test per visit",
        "study_id": "TEST001",
        "source_datasets": ["test.sas7bdat"],
        "variable_mappings": [
            _make_var("STUDYID", "Study Identifier"),
            _make_var("DOMAIN", "Domain Abbreviation"),
            _make_var("USUBJID", "Unique Subject Identifier"),
        ],
        "total_variables": 3,
        "required_mapped": 3,
        "expected_mapped": 0,
        "high_confidence_count": 3,
        "medium_confidence_count": 0,
        "low_confidence_count": 0,
        "mapping_timestamp": "2026-02-27T00:00:00",
        "model_used": "test",
    }
    spec_path = tmp_path / f"{domain.lower()}_spec.json"
    spec_path.write_text(json.dumps(spec))
    return spec_path


def _make_dummy_sas(tmp_path: Path, name: str = "test.sas7bdat") -> Path:
    """Create a dummy SAS file path (reading will be mocked)."""
    path = tmp_path / name
    path.write_bytes(b"dummy")
    return path


def _mock_read_sas(*_args, **_kwargs):
    """Return a minimal DataFrame as if read from a SAS file."""
    df = pd.DataFrame({"Subject": ["001"], "SiteNumber": ["01"], "LBTEST": ["WBC"]})
    meta = MagicMock()
    return df, meta


@patch(_PATCH_LOAD_SDTM)
@patch(_PATCH_LOAD_CT)
@patch(_PATCH_READ_SAS, side_effect=_mock_read_sas)
def test_execute_domain_lb_uses_findings_executor(mock_read_sas, mock_ct, mock_sdtm, tmp_path):
    """LB domain should be routed through FindingsExecutor.execute_lb."""
    spec_path = _make_spec_json("LB", tmp_path)
    _make_dummy_sas(tmp_path)
    output_dir = tmp_path / "output"

    main_df = pd.DataFrame(
        {"STUDYID": ["TEST001"], "DOMAIN": ["LB"], "USUBJID": ["TEST001-001-001"]}
    )

    with (
        patch(
            "astraea.execution.findings.FindingsExecutor.execute_lb",
            return_value=(main_df, None),
        ) as mock_execute_lb,
        patch(_PATCH_WRITE_XPT),
    ):
        result = runner.invoke(
            app,
            [
                "execute-domain",
                str(spec_path),
                str(tmp_path),
                "--output-dir",
                str(output_dir),
            ],
        )
        assert result.exit_code == 0, result.output
        mock_execute_lb.assert_called_once()


@patch(_PATCH_LOAD_SDTM)
@patch(_PATCH_LOAD_CT)
@patch(_PATCH_READ_SAS, side_effect=_mock_read_sas)
def test_execute_domain_eg_uses_findings_executor(mock_read_sas, mock_ct, mock_sdtm, tmp_path):
    """EG domain should be routed through FindingsExecutor.execute_eg."""
    spec_path = _make_spec_json("EG", tmp_path)
    _make_dummy_sas(tmp_path)
    output_dir = tmp_path / "output"

    main_df = pd.DataFrame(
        {"STUDYID": ["TEST001"], "DOMAIN": ["EG"], "USUBJID": ["TEST001-001-001"]}
    )

    with (
        patch(
            "astraea.execution.findings.FindingsExecutor.execute_eg",
            return_value=(main_df, None),
        ) as mock_execute_eg,
        patch(_PATCH_WRITE_XPT),
    ):
        result = runner.invoke(
            app,
            [
                "execute-domain",
                str(spec_path),
                str(tmp_path),
                "--output-dir",
                str(output_dir),
            ],
        )
        assert result.exit_code == 0, result.output
        mock_execute_eg.assert_called_once()


@patch(_PATCH_LOAD_SDTM)
@patch(_PATCH_LOAD_CT)
@patch(_PATCH_READ_SAS, side_effect=_mock_read_sas)
def test_execute_domain_dm_uses_generic_executor(mock_read_sas, mock_ct, mock_sdtm, tmp_path):
    """DM domain should use generic DatasetExecutor, NOT FindingsExecutor."""
    spec_path = _make_spec_json("DM", tmp_path)
    _make_dummy_sas(tmp_path)
    output_dir = tmp_path / "output"

    with patch("astraea.execution.executor.DatasetExecutor.execute_to_xpt") as mock_exec_xpt:
        mock_exec_xpt.return_value = Path(output_dir / "dm.xpt")
        result = runner.invoke(
            app,
            [
                "execute-domain",
                str(spec_path),
                str(tmp_path),
                "--output-dir",
                str(output_dir),
            ],
        )
        assert result.exit_code == 0, result.output
        mock_exec_xpt.assert_called_once()


@patch(_PATCH_LOAD_SDTM)
@patch(_PATCH_LOAD_CT)
@patch(_PATCH_READ_SAS, side_effect=_mock_read_sas)
def test_execute_domain_lb_with_suppqual(mock_read_sas, mock_ct, mock_sdtm, tmp_path):
    """When FindingsExecutor returns SUPPQUAL data, two XPT files should be written."""
    spec_path = _make_spec_json("LB", tmp_path)
    _make_dummy_sas(tmp_path)
    output_dir = tmp_path / "output"

    main_df = pd.DataFrame(
        {"STUDYID": ["TEST001"], "DOMAIN": ["LB"], "USUBJID": ["TEST001-001-001"]}
    )
    supp_df = pd.DataFrame(
        {
            "STUDYID": ["TEST001"],
            "RDOMAIN": ["LB"],
            "USUBJID": ["TEST001-001-001"],
            "IDVAR": ["LBSEQ"],
            "IDVARVAL": ["1"],
            "QNAM": ["LBFAST"],
            "QLABEL": ["Fasting Status"],
            "QVAL": ["Y"],
            "QORIG": ["CRF"],
            "QEVAL": [""],
        }
    )

    write_calls: list[str] = []

    def mock_write_xpt(df, path, **kwargs):
        write_calls.append(str(path))

    with (
        patch(
            "astraea.execution.findings.FindingsExecutor.execute_lb",
            return_value=(main_df, supp_df),
        ),
        patch(_PATCH_WRITE_XPT, side_effect=mock_write_xpt),
    ):
        result = runner.invoke(
            app,
            [
                "execute-domain",
                str(spec_path),
                str(tmp_path),
                "--output-dir",
                str(output_dir),
            ],
        )
        assert result.exit_code == 0, result.output
        # Two writes: lb.xpt and supplb.xpt
        assert len(write_calls) == 2
        assert any("lb.xpt" in c for c in write_calls)
        assert any("supplb.xpt" in c for c in write_calls)


@patch(_PATCH_LOAD_SDTM)
@patch(_PATCH_LOAD_CT)
@patch(_PATCH_READ_SAS, side_effect=_mock_read_sas)
def test_execute_domain_lb_no_suppqual(mock_read_sas, mock_ct, mock_sdtm, tmp_path):
    """When FindingsExecutor returns None for SUPPQUAL, only main XPT is written."""
    spec_path = _make_spec_json("LB", tmp_path)
    _make_dummy_sas(tmp_path)
    output_dir = tmp_path / "output"

    main_df = pd.DataFrame(
        {"STUDYID": ["TEST001"], "DOMAIN": ["LB"], "USUBJID": ["TEST001-001-001"]}
    )

    write_calls: list[str] = []

    def mock_write_xpt(df, path, **kwargs):
        write_calls.append(str(path))

    with (
        patch(
            "astraea.execution.findings.FindingsExecutor.execute_lb",
            return_value=(main_df, None),
        ),
        patch(_PATCH_WRITE_XPT, side_effect=mock_write_xpt),
    ):
        result = runner.invoke(
            app,
            [
                "execute-domain",
                str(spec_path),
                str(tmp_path),
                "--output-dir",
                str(output_dir),
            ],
        )
        assert result.exit_code == 0, result.output
        # Only one write: lb.xpt (no supplb.xpt)
        assert len(write_calls) == 1
        assert "lb.xpt" in write_calls[0]
        assert "supplb.xpt" not in write_calls[0]
