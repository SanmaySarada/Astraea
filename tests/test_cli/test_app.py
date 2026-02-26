"""Tests for the Astraea CLI application."""

from __future__ import annotations

from typer.testing import CliRunner

from astraea.cli.app import app

runner = CliRunner()


class TestVersionCommand:
    def test_version_exits_zero(self) -> None:
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "astraea-sdtm" in result.output


class TestProfileCommand:
    def test_profile_fakedata_exits_zero(self) -> None:
        result = runner.invoke(app, ["profile", "Fakedata/"])
        assert result.exit_code == 0
        assert "Dataset Summary" in result.output

    def test_profile_shows_dataset_names(self) -> None:
        result = runner.invoke(app, ["profile", "Fakedata/"])
        assert result.exit_code == 0
        # Should contain at least one known dataset name
        assert "ae" in result.output.lower() or "dm" in result.output.lower()

    def test_profile_shows_row_counts(self) -> None:
        result = runner.invoke(app, ["profile", "Fakedata/"])
        assert result.exit_code == 0
        # Should contain the "datasets profiled" footer
        assert "profiled" in result.output.lower()

    def test_profile_nonexistent_dir_exits_nonzero(self) -> None:
        result = runner.invoke(app, ["profile", "/nonexistent/path/"])
        assert result.exit_code != 0
        assert "Error" in result.output

    def test_profile_detail_flag(self) -> None:
        result = runner.invoke(app, ["profile", "Fakedata/", "--detail"])
        assert result.exit_code == 0
        # Detail mode should show variable-level info
        assert "Variable" in result.output


class TestReferenceCommand:
    def test_reference_dm_exits_zero(self) -> None:
        result = runner.invoke(app, ["reference", "DM"])
        assert result.exit_code == 0

    def test_reference_dm_shows_usubjid(self) -> None:
        result = runner.invoke(app, ["reference", "DM"])
        assert result.exit_code == 0
        assert "USUBJID" in result.output

    def test_reference_dm_shows_domain_info(self) -> None:
        result = runner.invoke(app, ["reference", "DM"])
        assert result.exit_code == 0
        assert "Demographics" in result.output

    def test_reference_invalid_domain_exits_nonzero(self) -> None:
        result = runner.invoke(app, ["reference", "INVALID"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_reference_lists_available_domains(self) -> None:
        result = runner.invoke(app, ["reference", "INVALID"])
        assert "Available domains" in result.output

    def test_reference_variable_flag(self) -> None:
        result = runner.invoke(app, ["reference", "DM", "--variable", "SEX"])
        assert result.exit_code == 0
        assert "SEX" in result.output

    def test_reference_invalid_variable(self) -> None:
        result = runner.invoke(app, ["reference", "DM", "--variable", "NONEXIST"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()


class TestCodelistCommand:
    def test_codelist_c66731_exits_zero(self) -> None:
        result = runner.invoke(app, ["codelist", "C66731"])
        assert result.exit_code == 0
        assert "Sex" in result.output or "SEX" in result.output

    def test_codelist_shows_terms(self) -> None:
        result = runner.invoke(app, ["codelist", "C66731"])
        assert result.exit_code == 0
        # Should show M, F terms
        assert "M" in result.output
        assert "F" in result.output

    def test_codelist_invalid_code(self) -> None:
        result = runner.invoke(app, ["codelist", "INVALID"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_codelist_list_all(self) -> None:
        result = runner.invoke(app, ["codelist"])
        assert result.exit_code == 0
        assert "Available Codelists" in result.output

    def test_codelist_by_variable(self) -> None:
        result = runner.invoke(app, ["codelist", "--variable", "SEX"])
        assert result.exit_code == 0
        assert "Sex" in result.output or "SEX" in result.output
