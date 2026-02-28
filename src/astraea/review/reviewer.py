"""Core review loop logic for the human review gate.

Drives the interactive review loop for a single domain, supporting
two-tier review (batch HIGH, individual MEDIUM/LOW), corrections,
and per-variable persistence for crash recovery.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from rich.console import Console
from rich.prompt import Prompt

from astraea.models.mapping import ConfidenceLevel, VariableMapping
from astraea.review.display import (
    display_review_summary,
    display_review_table,
    display_variable_detail,
)
from astraea.review.models import (
    CorrectionType,
    DomainReview,
    DomainReviewStatus,
    HumanCorrection,
    ReviewDecision,
    ReviewStatus,
)
from astraea.review.session import SessionStore


class ReviewInterrupted(Exception):
    """Raised when reviewer quits mid-session."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(f"Review interrupted. Resume with: astraea resume {session_id}")


class DomainReviewer:
    """Drives the interactive review loop for a single domain.

    Supports two review modes:
    1. Two-tier: batch approve HIGH confidence, individual review MEDIUM/LOW
    2. Per-variable: review every variable individually

    Accepts an optional input_callback for testability (replaces Rich Prompt.ask).
    When input_callback is None, uses Rich Prompt.ask() for real terminal input.
    """

    def __init__(
        self,
        session_store: SessionStore,
        console: Console,
        *,
        input_callback: Callable[[str, list[str], str], str] | None = None,
    ) -> None:
        """Initialize the reviewer.

        Args:
            session_store: SessionStore for persisting review state.
            console: Rich Console for display output.
            input_callback: Optional callback for testing. Signature:
                (message, choices, default) -> selected choice.
                When None, uses Rich Prompt.ask().
        """
        self._store = session_store
        self._console = console
        self._input_callback = input_callback

    def review_domain(self, session_id: str, domain: str) -> DomainReview:
        """Run the interactive review loop for a single domain.

        Loads domain review from session store, displays the mapping table,
        prompts for action (approve-all/review/skip/quit), and persists
        progress after each decision.

        Args:
            session_id: The session this review belongs to.
            domain: The SDTM domain code to review.

        Returns:
            The updated DomainReview after review is complete.

        Raises:
            ReviewInterrupted: If the reviewer quits mid-session.
        """
        session = self._store.load_session(session_id)
        domain_review = session.domain_reviews[domain]

        # Mark in progress if still pending
        if domain_review.status == DomainReviewStatus.PENDING:
            domain_review.status = DomainReviewStatus.IN_PROGRESS
            self._store.save_domain_review(session_id, domain_review)

        # Display current state
        display_review_table(
            domain_review.original_spec,
            domain_review.decisions,
            self._console,
        )

        # Check if all variables already reviewed (resume case)
        pending_count = self._pending_count(domain_review)
        if pending_count == 0:
            domain_review.status = DomainReviewStatus.COMPLETED
            domain_review.reviewed_at = datetime.now(tz=UTC).isoformat()
            self._store.save_domain_review(session_id, domain_review)
            display_review_summary(domain_review, self._console)
            return domain_review

        # Prompt for action
        action = self._prompt(
            "Action",
            ["approve-all", "review", "skip", "quit"],
            "review",
        )

        if action == "approve-all":
            self._approve_all(session_id, domain_review)
        elif action == "review":
            self._review_two_tier(session_id, domain_review)
        elif action == "skip":
            domain_review.status = DomainReviewStatus.SKIPPED
            domain_review.reviewed_at = datetime.now(tz=UTC).isoformat()
            self._store.save_domain_review(session_id, domain_review)
        elif action == "quit":
            self._store.save_domain_review(session_id, domain_review)
            raise ReviewInterrupted(session_id)

        # Mark completed if all reviewed
        if self._pending_count(domain_review) == 0:
            domain_review.status = DomainReviewStatus.COMPLETED
            domain_review.reviewed_at = datetime.now(tz=UTC).isoformat()
            self._store.save_domain_review(session_id, domain_review)

        display_review_summary(domain_review, self._console)
        return domain_review

    def _approve_all(self, session_id: str, domain_review: DomainReview) -> None:
        """Approve all pending variables."""
        now = datetime.now(tz=UTC).isoformat()
        for mapping in domain_review.original_spec.variable_mappings:
            if mapping.sdtm_variable not in domain_review.decisions:
                domain_review.decisions[mapping.sdtm_variable] = ReviewDecision(
                    sdtm_variable=mapping.sdtm_variable,
                    status=ReviewStatus.APPROVED,
                    original_mapping=mapping,
                    timestamp=now,
                )
        self._store.save_domain_review(session_id, domain_review)

    def _review_two_tier(self, session_id: str, domain_review: DomainReview) -> None:
        """Two-tier review: batch HIGH, individual MEDIUM/LOW.

        Args:
            session_id: The session ID for persistence.
            domain_review: The domain review to update in place.

        Raises:
            ReviewInterrupted: If the reviewer quits mid-review.
        """
        # Partition pending variables by confidence
        pending_mappings = [
            m
            for m in domain_review.original_spec.variable_mappings
            if m.sdtm_variable not in domain_review.decisions
        ]

        high_mappings = [m for m in pending_mappings if m.confidence_level == ConfidenceLevel.HIGH]
        other_mappings = [m for m in pending_mappings if m.confidence_level != ConfidenceLevel.HIGH]

        # Batch approve HIGH confidence
        if high_mappings:
            batch_action = self._prompt(
                f"Batch approve {len(high_mappings)} HIGH confidence mappings?",
                ["y", "n"],
                "y",
            )
            if batch_action == "y":
                now = datetime.now(tz=UTC).isoformat()
                for mapping in high_mappings:
                    domain_review.decisions[mapping.sdtm_variable] = ReviewDecision(
                        sdtm_variable=mapping.sdtm_variable,
                        status=ReviewStatus.APPROVED,
                        original_mapping=mapping,
                        timestamp=now,
                    )
                self._store.save_domain_review(session_id, domain_review)
            else:
                # Add HIGH to individual review
                other_mappings = high_mappings + other_mappings

        # Individual review for remaining
        for mapping in other_mappings:
            # Skip if already decided (from batch or prior session)
            if mapping.sdtm_variable in domain_review.decisions:
                continue

            display_variable_detail(mapping, self._console)

            var_action = self._prompt(
                f"[{mapping.sdtm_variable}]",
                ["a", "c", "s", "q"],
                "a",
            )

            if var_action == "a":
                domain_review.decisions[mapping.sdtm_variable] = ReviewDecision(
                    sdtm_variable=mapping.sdtm_variable,
                    status=ReviewStatus.APPROVED,
                    original_mapping=mapping,
                    timestamp=datetime.now(tz=UTC).isoformat(),
                )
                self._store.save_domain_review(session_id, domain_review)

            elif var_action == "c":
                corrected_mapping, correction_type, reason = self._collect_correction(mapping)

                decision = ReviewDecision(
                    sdtm_variable=mapping.sdtm_variable,
                    status=ReviewStatus.CORRECTED,
                    correction_type=correction_type,
                    original_mapping=mapping,
                    corrected_mapping=corrected_mapping,
                    reason=reason,
                    timestamp=datetime.now(tz=UTC).isoformat(),
                )
                domain_review.decisions[mapping.sdtm_variable] = decision

                correction = HumanCorrection(
                    session_id=session_id,
                    domain=domain_review.domain,
                    sdtm_variable=mapping.sdtm_variable,
                    correction_type=correction_type,
                    original_mapping=mapping,
                    corrected_mapping=corrected_mapping,
                    reason=reason,
                    timestamp=datetime.now(tz=UTC).isoformat(),
                )
                domain_review.corrections.append(correction)
                self._store.save_domain_review(session_id, domain_review)
                self._store.save_correction(correction)

            elif var_action == "s":
                domain_review.decisions[mapping.sdtm_variable] = ReviewDecision(
                    sdtm_variable=mapping.sdtm_variable,
                    status=ReviewStatus.SKIPPED,
                    original_mapping=mapping,
                    timestamp=datetime.now(tz=UTC).isoformat(),
                )
                self._store.save_domain_review(session_id, domain_review)

            elif var_action == "q":
                self._store.save_domain_review(session_id, domain_review)
                raise ReviewInterrupted(session_id)

    def _collect_correction(
        self, mapping: VariableMapping
    ) -> tuple[VariableMapping | None, CorrectionType, str]:
        """Collect correction details from the reviewer.

        Args:
            mapping: The original variable mapping being corrected.

        Returns:
            Tuple of (corrected_mapping or None, correction_type, reason).
        """
        correction_type_choice = self._prompt(
            "Correction type",
            ["s", "r", "o"],
            "s",
        )

        if correction_type_choice == "s":
            # Source change
            new_source = self._prompt("New source variable", [], "")
            reason = self._prompt("Reason", [], "")

            corrected = VariableMapping(
                sdtm_variable=mapping.sdtm_variable,
                sdtm_label=mapping.sdtm_label,
                sdtm_data_type=mapping.sdtm_data_type,
                core=mapping.core,
                source_dataset=mapping.source_dataset,
                source_variable=new_source,
                source_label=mapping.source_label,
                mapping_pattern=mapping.mapping_pattern,
                mapping_logic=(
                    f"Corrected: source changed from {mapping.source_variable} to {new_source}"
                ),
                derivation_rule=mapping.derivation_rule,
                assigned_value=mapping.assigned_value,
                codelist_code=mapping.codelist_code,
                codelist_name=mapping.codelist_name,
                confidence=1.0,
                confidence_level=ConfidenceLevel.HIGH,
                confidence_rationale="Human-verified correction",
                notes=mapping.notes,
                order=mapping.order,
                length=mapping.length,
            )
            return corrected, CorrectionType.SOURCE_CHANGE, reason

        elif correction_type_choice == "r":
            # Reject
            reason = self._prompt("Reason for rejection", [], "")
            return None, CorrectionType.REJECT, reason

        else:
            # Other / logic change
            reason = self._prompt("Describe the correction", [], "")
            return mapping, CorrectionType.LOGIC_CHANGE, reason

    def _prompt(self, message: str, choices: list[str], default: str) -> str:
        """Prompt for input, using callback or Rich Prompt.

        Args:
            message: The prompt message.
            choices: Valid choices (empty list = free text).
            default: Default value.

        Returns:
            The user's selection/input.
        """
        if self._input_callback is not None:
            return self._input_callback(message, choices, default)
        if choices:
            return Prompt.ask(message, choices=choices, default=default, console=self._console)
        return Prompt.ask(message, default=default, console=self._console)

    @staticmethod
    def _pending_count(domain_review: DomainReview) -> int:
        """Count variables without a decision."""
        total = len(domain_review.original_spec.variable_mappings)
        decided = len(domain_review.decisions)
        return total - decided
