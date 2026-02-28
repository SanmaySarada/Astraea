"""Tests for the package-submission CLI command and INFORMATIONAL severity."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from astraea.cli.app import app
from astraea.validation.rules.base import RuleSeverity

runner = CliRunner()


class TestPackageSubmissionCLI:
    """Test the package-submission CLI command."""

    def test_command_exists(self) -> None:
        """The package-submission command is registered."""
        result = runner.invoke(app, ["package-submission", "--help"])
        assert result.exit_code == 0
        assert "eCTD" in result.stdout or "submission" in result.stdout

    def test_missing_source_dir(self, tmp_path: Path) -> None:
        """Error when source directory does not exist."""
        result = runner.invoke(
            app,
            [
                "package-submission",
                "--source-dir",
                str(tmp_path / "nonexistent"),
                "--output-dir",
                str(tmp_path / "out"),
                "--study-id",
                "TEST-001",
            ],
        )
        assert result.exit_code != 0

    def test_no_xpt_files(self, tmp_path: Path) -> None:
        """Error when source directory has no .xpt files."""
        src = tmp_path / "src"
        src.mkdir()
        result = runner.invoke(
            app,
            [
                "package-submission",
                "--source-dir",
                str(src),
                "--output-dir",
                str(tmp_path / "out"),
                "--study-id",
                "TEST-001",
            ],
        )
        assert result.exit_code != 0

    def test_successful_packaging(self, tmp_path: Path) -> None:
        """Successfully packages XPT files into eCTD structure."""
        src = tmp_path / "src"
        src.mkdir()
        # Create dummy XPT files
        (src / "dm.xpt").write_bytes(b"\x00" * 100)
        (src / "ae.xpt").write_bytes(b"\x00" * 100)

        out = tmp_path / "out"
        result = runner.invoke(
            app,
            [
                "package-submission",
                "--source-dir",
                str(src),
                "--output-dir",
                str(out),
                "--study-id",
                "TEST-001",
            ],
        )
        assert result.exit_code == 0
        assert "Package assembled" in result.stdout

        # Verify eCTD structure created
        sdtm_dir = out / "m5" / "datasets" / "tabulations" / "sdtm"
        assert sdtm_dir.exists()
        assert (sdtm_dir / "dm.xpt").exists()
        assert (sdtm_dir / "ae.xpt").exists()


class TestInformationalSeverity:
    """Test INFORMATIONAL severity level in RuleSeverity enum."""

    def test_informational_is_valid_member(self) -> None:
        """INFORMATIONAL is a valid RuleSeverity value."""
        assert RuleSeverity.INFORMATIONAL == "INFORMATIONAL"

    def test_informational_display_name(self) -> None:
        """INFORMATIONAL has a proper display name."""
        assert RuleSeverity.INFORMATIONAL.display_name == "Informational"

    def test_all_four_levels_exist(self) -> None:
        """P21-style four severity levels all exist."""
        levels = [s.value for s in RuleSeverity]
        assert "ERROR" in levels
        assert "WARNING" in levels
        assert "NOTICE" in levels
        assert "INFORMATIONAL" in levels
        assert len(levels) == 4
