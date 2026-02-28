"""Tests for LearningRetriever wiring in the map-domain CLI command.

Verifies that _try_load_learning_retriever correctly handles:
- No learning DB (returns None)
- Explicit --learning-db path
- Auto-detection from .astraea/learning/
- Graceful fallback when chromadb import fails
- Non-existent explicit path returns None
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from astraea.cli.app import _try_load_learning_retriever


@pytest.fixture()
def quiet_console() -> Console:
    """Console that captures output without printing."""
    return Console(file=None, quiet=True)


class TestTryLoadLearningRetriever:
    """Tests for _try_load_learning_retriever helper function."""

    def test_no_learning_db_returns_none(
        self, quiet_console: Console, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When learning_db is None and .astraea/learning/ does not exist,
        returns None without error."""
        # Use a tmp dir with no .astraea/learning/ subdirectory
        monkeypatch.chdir(tmp_path)
        result = _try_load_learning_retriever(None, quiet_console)
        assert result is None

    def test_explicit_learning_db_path(
        self, quiet_console: Console, tmp_path: Path
    ) -> None:
        """When --learning-db is explicitly provided, loads from that path."""
        learning_dir = tmp_path / "my_learning_db"
        learning_dir.mkdir()

        mock_vector_store = MagicMock()
        mock_retriever = MagicMock()

        mock_vs_module = MagicMock()
        mock_vs_module.LearningVectorStore.return_value = mock_vector_store
        mock_ret_module = MagicMock()
        mock_ret_module.LearningRetriever.return_value = mock_retriever

        with patch.dict(
            "sys.modules",
            {
                "astraea.learning.vector_store": mock_vs_module,
                "astraea.learning.retriever": mock_ret_module,
            },
        ):
            result = _try_load_learning_retriever(learning_dir, quiet_console)

        assert result is mock_retriever
        mock_vs_module.LearningVectorStore.assert_called_once_with(learning_dir)
        mock_ret_module.LearningRetriever.assert_called_once_with(mock_vector_store)

    def test_auto_detect_astraea_learning_dir(
        self, quiet_console: Console, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When .astraea/learning/ exists in cwd, auto-detects and loads."""
        monkeypatch.chdir(tmp_path)
        learning_dir = tmp_path / ".astraea" / "learning"
        learning_dir.mkdir(parents=True)

        mock_vector_store = MagicMock()
        mock_retriever = MagicMock()

        mock_vs_module = MagicMock()
        mock_vs_module.LearningVectorStore.return_value = mock_vector_store
        mock_ret_module = MagicMock()
        mock_ret_module.LearningRetriever.return_value = mock_retriever

        with patch.dict(
            "sys.modules",
            {
                "astraea.learning.vector_store": mock_vs_module,
                "astraea.learning.retriever": mock_ret_module,
            },
        ):
            result = _try_load_learning_retriever(None, quiet_console)

        assert result is mock_retriever
        mock_vs_module.LearningVectorStore.assert_called_once()
        mock_ret_module.LearningRetriever.assert_called_once_with(mock_vector_store)

    def test_import_error_returns_none(
        self, quiet_console: Console, tmp_path: Path
    ) -> None:
        """When chromadb is not installed (ImportError), returns None gracefully."""
        learning_dir = tmp_path / "learning"
        learning_dir.mkdir()

        # Make the lazy import raise ImportError
        mock_ret_module = MagicMock()
        mock_ret_module.LearningRetriever.side_effect = ImportError(
            "No module named 'chromadb'"
        )
        mock_vs_module = MagicMock()
        mock_vs_module.LearningVectorStore.side_effect = ImportError(
            "No module named 'chromadb'"
        )

        with patch.dict(
            "sys.modules",
            {
                "astraea.learning.vector_store": mock_vs_module,
                "astraea.learning.retriever": mock_ret_module,
            },
        ):
            result = _try_load_learning_retriever(learning_dir, quiet_console)

        assert result is None

    def test_nonexistent_explicit_path_returns_none(
        self, quiet_console: Console, tmp_path: Path
    ) -> None:
        """When --learning-db points to a non-existent directory, returns None."""
        nonexistent = tmp_path / "does_not_exist"
        result = _try_load_learning_retriever(nonexistent, quiet_console)
        assert result is None
