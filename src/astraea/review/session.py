"""SQLite-backed review session persistence.

Stores review sessions, domain reviews, and corrections in SQLite.
All writes use transactions. Designed for single-user CLI usage.
Compatible with future LangGraph SqliteSaver migration.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from astraea.models.mapping import DomainMappingSpec
from astraea.review.models import (
    DomainReview,
    DomainReviewStatus,
    HumanCorrection,
    ReviewDecision,
    ReviewSession,
    SessionStatus,
)


class SessionStore:
    """SQLite-backed review session persistence.

    Stores review sessions, domain reviews, and corrections in SQLite.
    All writes use transactions. Designed for single-user CLI usage.
    Compatible with future LangGraph SqliteSaver migration.
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
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                study_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'in_progress',
                current_domain_index INTEGER DEFAULT 0,
                domains_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS domain_reviews (
                session_id TEXT NOT NULL,
                domain TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                original_spec_json TEXT NOT NULL,
                reviewed_spec_json TEXT,
                decisions_json TEXT NOT NULL DEFAULT '{}',
                corrections_json TEXT NOT NULL DEFAULT '[]',
                reviewed_at TEXT,
                PRIMARY KEY (session_id, domain),
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            );
            CREATE TABLE IF NOT EXISTS corrections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                domain TEXT NOT NULL,
                sdtm_variable TEXT NOT NULL,
                correction_type TEXT NOT NULL,
                original_json TEXT NOT NULL,
                corrected_json TEXT,
                reason TEXT NOT NULL,
                reviewer TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            );
        """)
        self._conn.commit()

    def create_session(
        self,
        study_id: str,
        domains: list[str],
        specs: dict[str, DomainMappingSpec],
    ) -> ReviewSession:
        """Create a new review session.

        Generates uuid4 hex[:12] as session_id. Stores each domain's spec
        as a pending DomainReview.

        Args:
            study_id: Study identifier.
            domains: Ordered list of domain codes to review.
            specs: Mapping specs keyed by domain code.

        Returns:
            The created ReviewSession object.
        """
        session_id = uuid.uuid4().hex[:12]
        now = datetime.now(tz=UTC).isoformat()

        domain_reviews: dict[str, DomainReview] = {}
        for domain in domains:
            if domain not in specs:
                msg = f"No spec provided for domain '{domain}'"
                raise ValueError(msg)
            domain_reviews[domain] = DomainReview(
                domain=domain,
                original_spec=specs[domain],
            )

        session = ReviewSession(
            session_id=session_id,
            study_id=study_id,
            created_at=now,
            updated_at=now,
            domains=domains,
            domain_reviews=domain_reviews,
        )

        # Persist session row
        self._conn.execute(
            """INSERT INTO sessions
               (session_id, study_id, created_at, updated_at, status,
                current_domain_index, domains_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                session.session_id,
                session.study_id,
                session.created_at,
                session.updated_at,
                session.status.value,
                session.current_domain_index,
                json.dumps(session.domains),
            ),
        )

        # Persist domain review rows
        for domain, review in domain_reviews.items():
            self._conn.execute(
                """INSERT INTO domain_reviews
                   (session_id, domain, status, original_spec_json,
                    reviewed_spec_json, decisions_json, corrections_json,
                    reviewed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session.session_id,
                    domain,
                    review.status.value,
                    review.original_spec.model_dump_json(),
                    None,
                    json.dumps({}),
                    json.dumps([]),
                    None,
                ),
            )

        self._conn.commit()
        return session

    def save_session(self, session: ReviewSession) -> None:
        """Persist full session state.

        Updates the session row and all domain reviews and corrections.

        Args:
            session: The ReviewSession to persist.
        """
        now = datetime.now(tz=UTC).isoformat()

        self._conn.execute(
            """UPDATE sessions
               SET updated_at = ?, status = ?, current_domain_index = ?
               WHERE session_id = ?""",
            (
                now,
                session.status.value,
                session.current_domain_index,
                session.session_id,
            ),
        )

        for _domain, review in session.domain_reviews.items():
            self.save_domain_review(session.session_id, review)

        self._conn.commit()

    def save_domain_review(self, session_id: str, domain_review: DomainReview) -> None:
        """Save/update a single domain review within a session.

        Args:
            session_id: The session this review belongs to.
            domain_review: The domain review to persist.
        """
        # Serialize decisions dict
        decisions_json = json.dumps({k: v.model_dump() for k, v in domain_review.decisions.items()})
        # Serialize corrections list
        corrections_json = json.dumps([c.model_dump() for c in domain_review.corrections])

        self._conn.execute(
            """INSERT OR REPLACE INTO domain_reviews
               (session_id, domain, status, original_spec_json,
                reviewed_spec_json, decisions_json, corrections_json,
                reviewed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                domain_review.domain,
                domain_review.status.value,
                domain_review.original_spec.model_dump_json(),
                (
                    domain_review.reviewed_spec.model_dump_json()
                    if domain_review.reviewed_spec
                    else None
                ),
                decisions_json,
                corrections_json,
                domain_review.reviewed_at,
            ),
        )
        self._conn.commit()

    def save_correction(self, correction: HumanCorrection) -> None:
        """Append a correction to the corrections table.

        Args:
            correction: The correction to persist.
        """
        self._conn.execute(
            """INSERT INTO corrections
               (session_id, domain, sdtm_variable, correction_type,
                original_json, corrected_json, reason, reviewer, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                correction.session_id,
                correction.domain,
                correction.sdtm_variable,
                correction.correction_type.value,
                correction.original_mapping.model_dump_json(),
                (
                    correction.corrected_mapping.model_dump_json()
                    if correction.corrected_mapping
                    else None
                ),
                correction.reason,
                correction.reviewer,
                correction.timestamp,
            ),
        )
        self._conn.commit()

    def load_session(self, session_id: str) -> ReviewSession:
        """Load full session state including all domain reviews.

        Args:
            session_id: The session to load.

        Returns:
            The loaded ReviewSession.

        Raises:
            ValueError: If session_id is not found.
        """
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()

        if row is None:
            msg = f"Session '{session_id}' not found"
            raise ValueError(msg)

        # Load domain reviews
        domain_rows = self._conn.execute(
            "SELECT * FROM domain_reviews WHERE session_id = ?",
            (session_id,),
        ).fetchall()

        domain_reviews: dict[str, DomainReview] = {}
        for dr_row in domain_rows:
            # Deserialize decisions
            decisions_raw = json.loads(dr_row["decisions_json"])
            decisions = {k: ReviewDecision(**v) for k, v in decisions_raw.items()}

            # Deserialize corrections
            corrections_raw = json.loads(dr_row["corrections_json"])
            corrections = [HumanCorrection(**c) for c in corrections_raw]

            domain_reviews[dr_row["domain"]] = DomainReview(
                domain=dr_row["domain"],
                status=DomainReviewStatus(dr_row["status"]),
                original_spec=DomainMappingSpec.model_validate_json(dr_row["original_spec_json"]),
                reviewed_spec=(
                    DomainMappingSpec.model_validate_json(dr_row["reviewed_spec_json"])
                    if dr_row["reviewed_spec_json"]
                    else None
                ),
                decisions=decisions,
                corrections=corrections,
                reviewed_at=dr_row["reviewed_at"],
            )

        return ReviewSession(
            session_id=row["session_id"],
            study_id=row["study_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            status=SessionStatus(row["status"]),
            domains=json.loads(row["domains_json"]),
            current_domain_index=row["current_domain_index"],
            domain_reviews=domain_reviews,
        )

    def list_sessions(self, study_id: str | None = None) -> list[dict[str, str | int | None]]:
        """Return list of session summaries.

        Args:
            study_id: Optional filter by study ID.

        Returns:
            List of dicts with keys: session_id, study_id, status,
            created_at, updated_at, domain_count.
        """
        if study_id is not None:
            rows = self._conn.execute(
                "SELECT * FROM sessions WHERE study_id = ? ORDER BY created_at DESC",
                (study_id,),
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT * FROM sessions ORDER BY created_at DESC").fetchall()

        results = []
        for row in rows:
            domains = json.loads(row["domains_json"])
            results.append(
                {
                    "session_id": row["session_id"],
                    "study_id": row["study_id"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "domain_count": len(domains),
                }
            )
        return results

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
