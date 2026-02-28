"""Tests for eCTD directory structure assembly."""

from __future__ import annotations

from pathlib import Path

import pytest

from astraea.submission.ectd import assemble_ectd_package, validate_xpt_filename


class TestValidateXptFilename:
    """Tests for FDA XPT filename validation."""

    def test_valid_lowercase_name(self) -> None:
        """Valid lowercase name passes validation."""
        valid, corrected = validate_xpt_filename("dm.xpt")
        assert valid is True
        assert corrected == "dm.xpt"

    def test_uppercase_corrected_to_lowercase(self) -> None:
        """Uppercase names are corrected to lowercase."""
        valid, corrected = validate_xpt_filename("DM.xpt")
        assert valid is False
        assert corrected == "dm.xpt"

    def test_mixed_case_corrected(self) -> None:
        """Mixed case names are corrected."""
        valid, corrected = validate_xpt_filename("Ae.XPT")
        assert valid is False
        assert corrected == "ae.xpt"

    def test_underscore_allowed(self) -> None:
        """Underscores are valid in XPT filenames."""
        valid, corrected = validate_xpt_filename("lb_chem.xpt")
        assert valid is True
        assert corrected == "lb_chem.xpt"

    def test_invalid_chars_removed(self) -> None:
        """Invalid characters are stripped from filename."""
        valid, corrected = validate_xpt_filename("ae-data.xpt")
        assert valid is False
        assert corrected == "aedata.xpt"

    def test_spaces_removed(self) -> None:
        """Spaces are removed from filename."""
        valid, corrected = validate_xpt_filename("ae data.xpt")
        assert valid is False
        assert corrected == "aedata.xpt"


class TestAssembleEctdPackage:
    """Tests for eCTD directory structure assembly."""

    def test_creates_directory_structure(self, tmp_path: Path) -> None:
        """Creates the m5/datasets/tabulations/sdtm/ directory tree."""
        source = tmp_path / "source"
        source.mkdir()
        output = tmp_path / "ectd"

        result = assemble_ectd_package(source, output, "STUDY-001")

        assert result == output / "m5" / "datasets" / "tabulations" / "sdtm"
        assert result.is_dir()

    def test_copies_xpt_files(self, tmp_path: Path) -> None:
        """XPT files are copied to sdtm/ directory."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "dm.xpt").write_bytes(b"fake dm data")
        (source / "ae.xpt").write_bytes(b"fake ae data")
        output = tmp_path / "ectd"

        sdtm_dir = assemble_ectd_package(source, output, "STUDY-001")

        assert (sdtm_dir / "dm.xpt").exists()
        assert (sdtm_dir / "ae.xpt").exists()
        assert (sdtm_dir / "dm.xpt").read_bytes() == b"fake dm data"

    def test_renames_to_lowercase(self, tmp_path: Path) -> None:
        """Uppercase XPT filenames are renamed to lowercase."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "DM.xpt").write_bytes(b"dm data")
        (source / "AE.xpt").write_bytes(b"ae data")
        output = tmp_path / "ectd"

        sdtm_dir = assemble_ectd_package(source, output, "STUDY-001")

        assert (sdtm_dir / "dm.xpt").exists()
        assert (sdtm_dir / "ae.xpt").exists()
        # Verify actual filenames on disk are lowercase
        actual_names = {f.name for f in sdtm_dir.glob("*.xpt")}
        assert "dm.xpt" in actual_names
        assert "ae.xpt" in actual_names

    def test_copies_define_xml(self, tmp_path: Path) -> None:
        """define.xml is placed in the sdtm/ directory."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "dm.xpt").write_bytes(b"data")
        define = tmp_path / "define.xml"
        define.write_text("<define/>")
        output = tmp_path / "ectd"

        sdtm_dir = assemble_ectd_package(
            source, output, "STUDY-001", define_xml_path=define
        )

        assert (sdtm_dir / "define.xml").exists()
        assert (sdtm_dir / "define.xml").read_text() == "<define/>"

    def test_copies_csdrg_at_tabulations_level(self, tmp_path: Path) -> None:
        """cSDRG is placed at the tabulations/ level, not sdtm/."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "dm.xpt").write_bytes(b"data")
        csdrg = tmp_path / "csdrg.md"
        csdrg.write_text("# cSDRG")
        output = tmp_path / "ectd"

        sdtm_dir = assemble_ectd_package(
            source, output, "STUDY-001", csdrg_path=csdrg
        )

        tabulations = sdtm_dir.parent  # m5/datasets/tabulations/
        assert (tabulations / "csdrg.md").exists()
        assert (tabulations / "csdrg.md").read_text() == "# cSDRG"
        # Should NOT be in sdtm/ directory
        assert not (sdtm_dir / "csdrg.md").exists()

    def test_handles_empty_source_directory(self, tmp_path: Path) -> None:
        """Empty source directory creates structure but no files."""
        source = tmp_path / "source"
        source.mkdir()
        output = tmp_path / "ectd"

        sdtm_dir = assemble_ectd_package(source, output, "STUDY-001")

        assert sdtm_dir.is_dir()
        xpt_files = list(sdtm_dir.glob("*.xpt"))
        assert len(xpt_files) == 0

    def test_raises_on_missing_source(self, tmp_path: Path) -> None:
        """Raises FileNotFoundError when source directory is missing."""
        source = tmp_path / "nonexistent"
        output = tmp_path / "ectd"

        with pytest.raises(FileNotFoundError, match="does not exist"):
            assemble_ectd_package(source, output, "STUDY-001")

    def test_ignores_non_xpt_files(self, tmp_path: Path) -> None:
        """Non-XPT files in source are not copied."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "dm.xpt").write_bytes(b"data")
        (source / "readme.txt").write_text("notes")
        (source / "data.csv").write_text("a,b,c")
        output = tmp_path / "ectd"

        sdtm_dir = assemble_ectd_package(source, output, "STUDY-001")

        assert (sdtm_dir / "dm.xpt").exists()
        assert not (sdtm_dir / "readme.txt").exists()
        assert not (sdtm_dir / "data.csv").exists()

    def test_define_xml_missing_no_error(self, tmp_path: Path) -> None:
        """Non-existent define.xml path logs warning but does not crash."""
        source = tmp_path / "source"
        source.mkdir()
        missing_define = tmp_path / "no_such_define.xml"
        output = tmp_path / "ectd"

        sdtm_dir = assemble_ectd_package(
            source, output, "STUDY-001", define_xml_path=missing_define
        )

        assert sdtm_dir.is_dir()
        assert not (sdtm_dir / "define.xml").exists()
