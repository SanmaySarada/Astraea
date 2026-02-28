"""Tests for generate-trial-design CLI command.

Verifies:
- Basic invocation with valid config produces TS/TA/TE/TV XPT files
- Missing config path exits with code 1
- TS validation warnings printed for incomplete configs
- DM path enables SSTDTC derivation in TS output
- Data dir enables SV domain generation (with mock)
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pyreadstat
from typer.testing import CliRunner

from astraea.cli.app import app

runner = CliRunner()


def _make_config() -> dict:
    """Create a minimal valid trial design JSON config."""
    return {
        "ts_config": {
            "study_id": "TEST001",
            "study_title": "Test Study",
            "sponsor": "TestCorp",
            "indication": "Test Indication",
            "treatment": "Test Drug",
            "pharmacological_class": "Test Class",
        },
        "trial_design": {
            "arms": [
                {
                    "armcd": "DRUG",
                    "arm": "Drug Arm",
                    "taetord": 1,
                    "etcd": "SCRN",
                },
            ],
            "elements": [
                {"etcd": "SCRN", "element": "Screening"},
            ],
            "visits": [
                {
                    "visitnum": 1.0,
                    "visit": "Screening",
                    "armcd": "DRUG",
                },
            ],
        },
    }


def test_generate_trial_design_basic(tmp_path: Path) -> None:
    """Basic invocation with valid config produces XPT files."""
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(_make_config()))
    output_dir = tmp_path / "output"

    result = runner.invoke(
        app,
        [
            "generate-trial-design",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0, f"CLI failed: {result.output}"
    assert (output_dir / "ts.xpt").exists()
    assert (output_dir / "ta.xpt").exists()
    assert (output_dir / "te.xpt").exists()
    assert (output_dir / "tv.xpt").exists()


def test_generate_trial_design_missing_config() -> None:
    """Nonexistent config path exits with code 1."""
    result = runner.invoke(
        app,
        [
            "generate-trial-design",
            "/nonexistent/path/config.json",
        ],
    )

    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def test_generate_trial_design_ts_validation_warnings(tmp_path: Path) -> None:
    """Config without SSTDTC prints FDA-mandatory parameter warning."""
    config = _make_config()
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))
    output_dir = tmp_path / "output"

    result = runner.invoke(
        app,
        [
            "generate-trial-design",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0
    # SSTDTC is missing (no DM provided), so there should be a warning
    assert "SSTDTC" in result.output


def test_generate_trial_design_with_dm_path(tmp_path: Path) -> None:
    """DM XPT with RFSTDTC enables SSTDTC derivation in TS."""
    config = _make_config()
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))
    output_dir = tmp_path / "output"

    # Create a minimal DM XPT file
    dm_df = pd.DataFrame(
        {
            "STUDYID": ["TEST001", "TEST001"],
            "DOMAIN": ["DM", "DM"],
            "USUBJID": ["TEST001-001", "TEST001-002"],
            "RFSTDTC": ["2023-01-15", "2023-02-20"],
        }
    )
    dm_xpt_path = tmp_path / "dm.xpt"
    pyreadstat.write_xport(
        dm_df,
        str(dm_xpt_path),
        table_name="DM",
        column_labels={
            "STUDYID": "Study Identifier",
            "DOMAIN": "Domain Abbreviation",
            "USUBJID": "Unique Subject Identifier",
            "RFSTDTC": "Subject Ref Start Date/Time",
        },
        file_format_version=5,
    )

    result = runner.invoke(
        app,
        [
            "generate-trial-design",
            str(config_path),
            "--output-dir",
            str(output_dir),
            "--dm-path",
            str(dm_xpt_path),
        ],
    )

    assert result.exit_code == 0, f"CLI failed: {result.output}"

    # Read back TS and check SSTDTC is present
    ts_df, _ = pyreadstat.read_xport(str(output_dir / "ts.xpt"))
    ts_parmcds = ts_df["TSPARMCD"].tolist()
    assert "SSTDTC" in ts_parmcds, f"SSTDTC not in TS: {ts_parmcds}"

    # Verify SSTDTC value is the earliest RFSTDTC
    sstdtc_row = ts_df[ts_df["TSPARMCD"] == "SSTDTC"]
    assert sstdtc_row["TSVAL"].iloc[0] == "2023-01-15"


def test_generate_trial_design_sv_from_data_dir(tmp_path: Path) -> None:
    """SV domain generated when --data-dir has files with visit metadata."""
    config = _make_config()
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))
    output_dir = tmp_path / "output"
    data_dir = tmp_path / "rawdata"
    data_dir.mkdir()

    # Create a fake .sas7bdat file (empty, just needs to exist for glob)
    fake_sas = data_dir / "test.sas7bdat"
    fake_sas.touch()

    # Mock read_sas_with_metadata to return a DataFrame with visit columns
    visit_df = pd.DataFrame(
        {
            "Subject": ["SUBJ001", "SUBJ001", "SUBJ002"],
            "InstanceName": ["Screening", "Week 4", "Screening"],
            "FolderName": ["SCRN", "WK4", "SCRN"],
            "FolderSeq": [1.0, 2.0, 1.0],
            "VISITDAT": ["2023-01-15", "2023-02-12", "2023-01-20"],
        }
    )

    # Mock metadata (not used by the CLI, just needs to return a tuple)
    from unittest.mock import MagicMock

    mock_meta = MagicMock()

    with patch(
        "astraea.io.sas_reader.read_sas_with_metadata",
        return_value=(visit_df, mock_meta),
    ):
        result = runner.invoke(
            app,
            [
                "generate-trial-design",
                str(config_path),
                "--output-dir",
                str(output_dir),
                "--data-dir",
                str(data_dir),
            ],
        )

    assert result.exit_code == 0, f"CLI failed: {result.output}"
    assert (output_dir / "sv.xpt").exists()

    # Verify SV has expected rows
    sv_df, _ = pyreadstat.read_xport(str(output_dir / "sv.xpt"))
    assert len(sv_df) > 0
    assert "USUBJID" in sv_df.columns
    assert "VISIT" in sv_df.columns
