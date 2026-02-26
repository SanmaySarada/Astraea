"""Tests for SAS file reader with metadata extraction.

Integration tests that read real .sas7bdat files from the Fakedata/ directory.
"""

from pathlib import Path

import pandas as pd
import pytest

from astraea.io.sas_reader import read_all_sas_files, read_sas_with_metadata
from astraea.models.metadata import DatasetMetadata, VariableMetadata

FAKEDATA_DIR = Path(__file__).parent.parent.parent / "Fakedata"


@pytest.fixture
def dm_path() -> Path:
    return FAKEDATA_DIR / "dm.sas7bdat"


class TestReadSasWithMetadata:
    """Tests for read_sas_with_metadata function."""

    def test_returns_tuple_of_dataframe_and_metadata(self, dm_path: Path) -> None:
        df, meta = read_sas_with_metadata(dm_path)
        assert isinstance(df, pd.DataFrame)
        assert isinstance(meta, DatasetMetadata)

    def test_row_count_positive(self, dm_path: Path) -> None:
        df, meta = read_sas_with_metadata(dm_path)
        assert meta.row_count > 0
        assert len(df) == meta.row_count

    def test_col_count_matches_dataframe(self, dm_path: Path) -> None:
        df, meta = read_sas_with_metadata(dm_path)
        assert meta.col_count > 0
        assert len(df.columns) == meta.col_count

    def test_variables_list_populated(self, dm_path: Path) -> None:
        _, meta = read_sas_with_metadata(dm_path)
        assert len(meta.variables) > 0
        assert len(meta.variables) == meta.col_count
        assert all(isinstance(v, VariableMetadata) for v in meta.variables)

    def test_variable_names_match_dataframe_columns(self, dm_path: Path) -> None:
        df, meta = read_sas_with_metadata(dm_path)
        var_names = [v.name for v in meta.variables]
        assert var_names == list(df.columns)

    def test_file_encoding_populated(self, dm_path: Path) -> None:
        _, meta = read_sas_with_metadata(dm_path)
        assert meta.file_encoding is not None
        assert len(meta.file_encoding) > 0

    def test_filename_is_basename(self, dm_path: Path) -> None:
        _, meta = read_sas_with_metadata(dm_path)
        assert meta.filename == "dm.sas7bdat"

    def test_character_variables_detected(self, dm_path: Path) -> None:
        """DM dataset has character variables like Subject, Site."""
        _, meta = read_sas_with_metadata(dm_path)
        char_vars = [v for v in meta.variables if v.dtype == "character"]
        assert len(char_vars) > 0

    def test_numeric_variables_detected(self, dm_path: Path) -> None:
        """DM dataset has numeric variables like projectid, studyid."""
        _, meta = read_sas_with_metadata(dm_path)
        num_vars = [v for v in meta.variables if v.dtype == "numeric"]
        assert len(num_vars) > 0

    def test_labels_extracted(self, dm_path: Path) -> None:
        """Most variables in the sample data have labels."""
        _, meta = read_sas_with_metadata(dm_path)
        labeled = [v for v in meta.variables if v.label]
        assert len(labeled) > 0

    def test_datetime_not_converted(self, dm_path: Path) -> None:
        """With disable_datetime_conversion=True, DATETIME columns stay numeric."""
        df, meta = read_sas_with_metadata(dm_path)
        datetime_vars = [v for v in meta.variables if v.sas_format == "DATETIME"]
        if datetime_vars:
            col = datetime_vars[0].name
            # Should be float, not datetime64
            assert df[col].dtype != "datetime64[ns]"

    def test_nonexistent_file_raises_error(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            read_sas_with_metadata(tmp_path / "nonexistent.sas7bdat")

    def test_wrong_extension_raises_error(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "test.csv"
        bad_file.write_text("a,b,c")
        with pytest.raises(ValueError, match="Expected .sas7bdat"):
            read_sas_with_metadata(bad_file)

    def test_reads_ae_dataset(self) -> None:
        """Verify reader works on a larger dataset (AE)."""
        ae_path = FAKEDATA_DIR / "ae.sas7bdat"
        df, meta = read_sas_with_metadata(ae_path)
        assert meta.row_count > 0
        assert meta.col_count > 50  # AE has ~135 columns

    def test_string_path_accepted(self) -> None:
        """Reader should accept string paths, not just Path objects."""
        df, meta = read_sas_with_metadata(str(FAKEDATA_DIR / "dm.sas7bdat"))
        assert meta.row_count > 0


class TestReadAllSasFiles:
    """Tests for read_all_sas_files function."""

    def test_returns_dict_with_multiple_keys(self) -> None:
        results = read_all_sas_files(FAKEDATA_DIR)
        assert isinstance(results, dict)
        assert len(results) > 10  # 36 files expected

    def test_dm_key_exists(self) -> None:
        results = read_all_sas_files(FAKEDATA_DIR)
        assert "dm" in results

    def test_values_are_tuples(self) -> None:
        results = read_all_sas_files(FAKEDATA_DIR)
        for key, value in results.items():
            assert isinstance(value, tuple), f"Value for {key} is not a tuple"
            assert len(value) == 2
            assert isinstance(value[0], pd.DataFrame)
            assert isinstance(value[1], DatasetMetadata)

    def test_nonexistent_directory_raises_error(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            read_all_sas_files(tmp_path / "nonexistent")

    def test_empty_directory_raises_error(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="No .sas7bdat files"):
            read_all_sas_files(tmp_path)
