"""SQLite-backed storage for mapping examples, corrections, and study metrics.

Provides structured persistence for the learning system's training data.
Follows the SessionStore pattern (sqlite3.Row factory, parent mkdir).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from astraea.learning.models import CorrectionRecord, MappingExample, StudyMetrics


class ExampleStore:
    """SQLite-backed structured storage for mapping examples and corrections.

    Stores approved mappings, human corrections, and study-level accuracy
    metrics. All writes use individual transactions. Designed for single-user
    CLI usage.
    """

    def __init__(self, db_path: Path) -> None:
        """Open or create the SQLite database.

        Args:
            db_path: Path to the SQLite database file.
                     Parent directory is created if needed.
        """
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Create tables if they don't exist."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS mapping_examples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                example_id TEXT UNIQUE NOT NULL,
                study_id TEXT NOT NULL,
                domain TEXT NOT NULL,
                sdtm_variable TEXT NOT NULL,
                mapping_pattern TEXT NOT NULL,
                mapping_logic TEXT NOT NULL,
                source_variable TEXT,
                source_dataset TEXT,
                source_label TEXT,
                confidence REAL NOT NULL,
                was_corrected INTEGER NOT NULL DEFAULT 0,
                final_mapping_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS corrections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                correction_id TEXT UNIQUE NOT NULL,
                study_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                domain TEXT NOT NULL,
                sdtm_variable TEXT NOT NULL,
                correction_type TEXT NOT NULL,
                original_pattern TEXT NOT NULL,
                corrected_pattern TEXT,
                original_logic TEXT NOT NULL,
                corrected_logic TEXT,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL,
                invalidated INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS study_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                study_id TEXT NOT NULL,
                domain TEXT NOT NULL,
                total_proposed INTEGER NOT NULL,
                approved_unchanged INTEGER NOT NULL,
                corrected INTEGER NOT NULL,
                rejected INTEGER NOT NULL,
                added_by_reviewer INTEGER NOT NULL,
                accuracy_rate REAL NOT NULL,
                correction_rate REAL NOT NULL,
                completed_at TEXT NOT NULL,
                UNIQUE(study_id, domain)
            );
        """)
        self._conn.commit()

    def save_example(self, example: MappingExample) -> None:
        """Save a mapping example to the database.

        Uses INSERT OR REPLACE to handle duplicate example_ids.

        Args:
            example: The mapping example to persist.
        """
        self._conn.execute(
            """INSERT OR REPLACE INTO mapping_examples
               (example_id, study_id, domain, sdtm_variable, mapping_pattern,
                mapping_logic, source_variable, source_dataset, source_label,
                confidence, was_corrected, final_mapping_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                example.example_id,
                example.study_id,
                example.domain,
                example.sdtm_variable,
                example.mapping_pattern,
                example.mapping_logic,
                example.source_variable,
                example.source_dataset,
                example.source_label,
                example.confidence,
                int(example.was_corrected),
                example.final_mapping_json,
                example.created_at,
            ),
        )
        self._conn.commit()

    def save_correction(self, correction: CorrectionRecord) -> None:
        """Save a correction record to the database.

        Uses INSERT OR REPLACE to handle duplicate correction_ids.

        Args:
            correction: The correction record to persist.
        """
        self._conn.execute(
            """INSERT OR REPLACE INTO corrections
               (correction_id, study_id, session_id, domain, sdtm_variable,
                correction_type, original_pattern, corrected_pattern,
                original_logic, corrected_logic, reason, created_at, invalidated)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                correction.correction_id,
                correction.study_id,
                correction.session_id,
                correction.domain,
                correction.sdtm_variable,
                correction.correction_type,
                correction.original_pattern,
                correction.corrected_pattern,
                correction.original_logic,
                correction.corrected_logic,
                correction.reason,
                correction.created_at,
                int(correction.invalidated),
            ),
        )
        self._conn.commit()

    def save_metrics(self, metrics: StudyMetrics) -> None:
        """Save study metrics to the database.

        Uses INSERT OR REPLACE to update existing metrics for the same
        study_id + domain combination.

        Args:
            metrics: The study metrics to persist.
        """
        self._conn.execute(
            """INSERT OR REPLACE INTO study_metrics
               (study_id, domain, total_proposed, approved_unchanged,
                corrected, rejected, added_by_reviewer, accuracy_rate,
                correction_rate, completed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                metrics.study_id,
                metrics.domain,
                metrics.total_proposed,
                metrics.approved_unchanged,
                metrics.corrected,
                metrics.rejected,
                metrics.added_by_reviewer,
                metrics.accuracy_rate,
                metrics.correction_rate,
                metrics.completed_at,
            ),
        )
        self._conn.commit()

    def get_examples_for_domain(self, domain: str, limit: int = 50) -> list[MappingExample]:
        """Retrieve mapping examples filtered by domain.

        Args:
            domain: SDTM domain code to filter by.
            limit: Maximum number of examples to return.

        Returns:
            List of MappingExample objects for the domain.
        """
        rows = self._conn.execute(
            """SELECT * FROM mapping_examples
               WHERE domain = ?
               ORDER BY created_at DESC
               LIMIT ?""",
            (domain, limit),
        ).fetchall()

        return [
            MappingExample(
                example_id=row["example_id"],
                study_id=row["study_id"],
                domain=row["domain"],
                sdtm_variable=row["sdtm_variable"],
                mapping_pattern=row["mapping_pattern"],
                mapping_logic=row["mapping_logic"],
                source_variable=row["source_variable"],
                source_dataset=row["source_dataset"],
                source_label=row["source_label"],
                confidence=row["confidence"],
                was_corrected=bool(row["was_corrected"]),
                final_mapping_json=row["final_mapping_json"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def get_corrections_for_domain(
        self, domain: str, include_invalidated: bool = False
    ) -> list[CorrectionRecord]:
        """Retrieve corrections filtered by domain.

        Args:
            domain: SDTM domain code to filter by.
            include_invalidated: If False (default), excludes invalidated corrections.

        Returns:
            List of CorrectionRecord objects for the domain.
        """
        if include_invalidated:
            rows = self._conn.execute(
                """SELECT * FROM corrections
                   WHERE domain = ?
                   ORDER BY created_at DESC""",
                (domain,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """SELECT * FROM corrections
                   WHERE domain = ? AND invalidated = 0
                   ORDER BY created_at DESC""",
                (domain,),
            ).fetchall()

        return [
            CorrectionRecord(
                correction_id=row["correction_id"],
                study_id=row["study_id"],
                session_id=row["session_id"],
                domain=row["domain"],
                sdtm_variable=row["sdtm_variable"],
                correction_type=row["correction_type"],
                original_pattern=row["original_pattern"],
                corrected_pattern=row["corrected_pattern"],
                original_logic=row["original_logic"],
                corrected_logic=row["corrected_logic"],
                reason=row["reason"],
                created_at=row["created_at"],
                invalidated=bool(row["invalidated"]),
            )
            for row in rows
        ]

    def get_study_metrics(self, study_id: str | None = None) -> list[StudyMetrics]:
        """Retrieve study metrics, optionally filtered by study.

        Args:
            study_id: Optional study identifier to filter by.

        Returns:
            List of StudyMetrics objects.
        """
        if study_id is not None:
            rows = self._conn.execute(
                """SELECT * FROM study_metrics
                   WHERE study_id = ?
                   ORDER BY domain""",
                (study_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """SELECT * FROM study_metrics
                   ORDER BY study_id, domain"""
            ).fetchall()

        return [
            StudyMetrics(
                study_id=row["study_id"],
                domain=row["domain"],
                total_proposed=row["total_proposed"],
                approved_unchanged=row["approved_unchanged"],
                corrected=row["corrected"],
                rejected=row["rejected"],
                added_by_reviewer=row["added_by_reviewer"],
                accuracy_rate=row["accuracy_rate"],
                correction_rate=row["correction_rate"],
                completed_at=row["completed_at"],
            )
            for row in rows
        ]

    def invalidate_correction(self, correction_id: str) -> None:
        """Mark a correction as invalidated.

        Used for poisoning protection when a correction is later found
        to be incorrect.

        Args:
            correction_id: The correction to invalidate.
        """
        self._conn.execute(
            "UPDATE corrections SET invalidated = 1 WHERE correction_id = ?",
            (correction_id,),
        )
        self._conn.commit()

    def get_example_count(self) -> int:
        """Return total number of mapping examples."""
        row = self._conn.execute("SELECT COUNT(*) as cnt FROM mapping_examples").fetchone()
        return row["cnt"]

    def get_correction_count(self) -> int:
        """Return total number of corrections (including invalidated)."""
        row = self._conn.execute("SELECT COUNT(*) as cnt FROM corrections").fetchone()
        return row["cnt"]

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
