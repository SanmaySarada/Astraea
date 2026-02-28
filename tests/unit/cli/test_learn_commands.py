"""Tests for learning system CLI commands."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console
from typer.testing import CliRunner

from astraea.cli.app import app

runner = CliRunner()


class TestLearnIngestCommand:
    """Tests for learn-ingest CLI command."""

    def test_no_session_db(self, tmp_path: Path) -> None:
        """Should show message when no session database exists."""
        result = runner.invoke(
            app,
            [
                "learn-ingest",
                "--session-db",
                str(tmp_path / "nonexistent.db"),
            ],
        )
        assert result.exit_code == 0
        assert "No review session database" in result.output

    def test_no_completed_sessions(self, tmp_path: Path) -> None:
        """Should show message when no completed sessions exist."""
        # Create an empty sessions database with the right schema
        db_path = tmp_path / "sessions.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                study_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'in_progress',
                current_domain_index INTEGER DEFAULT 0,
                domains_json TEXT NOT NULL
            );
        """)
        conn.commit()
        conn.close()

        result = runner.invoke(
            app,
            [
                "learn-ingest",
                "--session-db",
                str(db_path),
            ],
        )
        assert result.exit_code == 0
        assert "No completed sessions found" in result.output


class TestLearnStatsCommand:
    """Tests for learn-stats CLI command."""

    def test_no_learning_db(self, tmp_path: Path) -> None:
        """Should show message when no learning database exists."""
        result = runner.invoke(
            app,
            [
                "learn-stats",
                "--learning-db",
                str(tmp_path / "nonexistent.db"),
            ],
        )
        assert result.exit_code == 0
        assert "No learning database found" in result.output

    def test_empty_learning_db(self, tmp_path: Path) -> None:
        """Should show zero counts with empty learning database."""
        from astraea.learning.example_store import ExampleStore

        db_path = tmp_path / "examples.db"
        store = ExampleStore(db_path)
        store.close()

        result = runner.invoke(
            app,
            [
                "learn-stats",
                "--learning-db",
                str(db_path),
            ],
        )
        assert result.exit_code == 0
        assert "Learning System Stats" in result.output


class TestLearnOptimizeCommand:
    """Tests for learn-optimize CLI command."""

    def test_no_learning_db(self, tmp_path: Path) -> None:
        """Should show message when no learning database exists."""
        result = runner.invoke(
            app,
            [
                "learn-optimize",
                "--learning-db",
                str(tmp_path / "nonexistent.db"),
            ],
        )
        assert result.exit_code == 0
        assert "No learning database found" in result.output

    def test_insufficient_examples(self, tmp_path: Path) -> None:
        """Should show helpful message when not enough examples."""
        from astraea.learning.example_store import ExampleStore

        db_path = tmp_path / "examples.db"
        store = ExampleStore(db_path)
        store.close()

        result = runner.invoke(
            app,
            [
                "learn-optimize",
                "--learning-db",
                str(db_path),
            ],
        )
        assert result.exit_code == 0
        assert "Need at least 10 examples" in result.output


class TestDisplayLearningStats:
    """Tests for display_learning_stats helper."""

    def test_produces_output(self) -> None:
        """Should produce Rich output with stats."""
        from astraea.cli.display import display_learning_stats

        console = Console(force_terminal=True, width=100)
        report = {
            "overall_accuracy": 0.85,
            "by_domain": {
                "AE": {
                    "first": 0.7,
                    "latest": 0.9,
                    "improvement": 0.2,
                    "studies": 3,
                },
            },
            "total_examples": 50,
            "total_corrections": 10,
        }

        # Should not raise
        display_learning_stats(report, 50, 10, console)

    def test_empty_report(self) -> None:
        """Should handle empty report gracefully."""
        from astraea.cli.display import display_learning_stats

        console = Console(force_terminal=True, width=100)
        report = {
            "overall_accuracy": 0.0,
            "by_domain": {},
            "total_examples": 0,
            "total_corrections": 0,
        }

        display_learning_stats(report, 0, 0, console)


class TestDisplayIngestionResult:
    """Tests for display_ingestion_result helper."""

    def test_produces_output(self) -> None:
        """Should produce Rich panel with ingestion summary."""
        from astraea.cli.display import display_ingestion_result

        console = Console(force_terminal=True, width=100)

        # Should not raise
        display_ingestion_result(25, 5, ["AE", "DM", "AE"], console)

    def test_empty_ingestion(self) -> None:
        """Should handle zero ingestion gracefully."""
        from astraea.cli.display import display_ingestion_result

        console = Console(force_terminal=True, width=100)
        display_ingestion_result(0, 0, [], console)
