"""Cross-study domain template library.

Abstracts approved domain mapping specifications into reusable templates
that capture the mapping shape (pattern distribution, variable patterns,
quality signals) rather than study-specific details. When mapping a new
study, relevant templates can be matched by domain to provide a starting
point based on proven patterns.
"""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from astraea.learning.models import StudyMetrics
from astraea.models.mapping import DomainMappingSpec


class VariablePattern(BaseModel):
    """Study-independent variable mapping pattern.

    Captures the typical way a specific SDTM variable gets mapped across
    studies: which mapping pattern is most common, what source variable
    keywords tend to appear, and what issues have been found during reviews.
    """

    sdtm_variable: str = Field(..., description="SDTM variable name (e.g., 'AETERM', 'USUBJID')")
    typical_pattern: str = Field(
        ..., description="Most common mapping pattern for this variable across studies"
    )
    typical_source_keywords: list[str] = Field(
        default_factory=list,
        description="Keywords from source variable names/labels "
        "(e.g., ['birth', 'date'] for BRTHDTC)",
    )
    derivation_template: str | None = Field(
        default=None,
        description="Generalized derivation logic (for derivation pattern variables)",
    )
    common_issues: list[str] = Field(
        default_factory=list,
        description="Issues found during past reviews for this variable",
    )


class DomainTemplate(BaseModel):
    """Reusable domain mapping template derived from completed studies.

    Captures the shape of a successful domain mapping: how many variables
    use each pattern, what the typical variable-level mappings look like,
    and the overall quality signal from past reviews.
    """

    template_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex,
        description="Unique template identifier",
    )
    domain: str = Field(..., description="SDTM domain code (e.g., 'AE', 'DM')")
    domain_class: str = Field(
        ...,
        description="Domain class (Events, Interventions, Findings, Special Purpose)",
    )
    source_study_ids: list[str] = Field(
        default_factory=list,
        description="Study IDs this template was derived from",
    )
    pattern_distribution: dict[str, int] = Field(
        default_factory=dict,
        description="Count of each mapping pattern (e.g., {'direct': 8, 'assign': 3})",
    )
    variable_patterns: list[VariablePattern] = Field(
        default_factory=list,
        description="Per-variable mapping patterns",
    )
    accuracy_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Average accuracy rate from source study metrics",
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(tz=UTC).isoformat(),
        description="ISO 8601 timestamp of template creation",
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(tz=UTC).isoformat(),
        description="ISO 8601 timestamp of last update",
    )


def _extract_keywords(text: str) -> list[str]:
    """Extract lowercase keywords from a variable name or mapping logic string.

    Splits on underscores, spaces, dots, and other non-alphanumeric chars.
    Filters out short tokens (length < 2) and common stop words.

    Args:
        text: Variable name, label, or mapping logic string.

    Returns:
        Deduplicated list of lowercase keyword strings.
    """
    stop_words = frozenset(
        {
            "the",
            "a",
            "an",
            "is",
            "in",
            "to",
            "of",
            "for",
            "and",
            "or",
            "from",
            "with",
            "on",
            "at",
            "by",
            "as",
            "if",
            "be",
            "no",
            "not",
        }
    )
    tokens = re.split(r"[_\s\.\-,;:()\"'/]+", text.lower())
    keywords = [t for t in tokens if len(t) >= 2 and t not in stop_words]
    # Deduplicate preserving order
    seen: set[str] = set()
    result: list[str] = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            result.append(kw)
    return result


class TemplateLibrary:
    """SQLite-backed library for domain mapping templates.

    Stores and retrieves reusable domain templates built from completed
    mapping specifications. Templates can be built from one or more
    DomainMappingSpecs (from different studies, same domain) and updated
    incrementally as new studies are processed.
    """

    def __init__(self, db_path: Path) -> None:
        """Open or create the SQLite database for template storage.

        Args:
            db_path: Path to the SQLite database file.
                     Parent directory is created if needed.
        """
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Create the domain_templates table if it does not exist."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS domain_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_id TEXT UNIQUE NOT NULL,
                domain TEXT UNIQUE NOT NULL,
                domain_class TEXT NOT NULL,
                source_study_ids_json TEXT NOT NULL,
                pattern_distribution_json TEXT NOT NULL,
                variable_patterns_json TEXT NOT NULL,
                accuracy_rate REAL NOT NULL DEFAULT 0.0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        self._conn.commit()

    def build_template(
        self,
        domain: str,
        specs: list[DomainMappingSpec],
        metrics: list[StudyMetrics] | None = None,
    ) -> DomainTemplate:
        """Build a domain template from one or more completed mapping specs.

        For each SDTM variable that appears across the specs, determines the
        typical mapping pattern (mode), extracts source keywords, and captures
        derivation logic. Computes the overall pattern distribution and averages
        accuracy from metrics.

        Args:
            domain: SDTM domain code (e.g., 'AE').
            specs: One or more DomainMappingSpecs from completed studies.
            metrics: Optional list of StudyMetrics for accuracy calculation.

        Returns:
            DomainTemplate with patterns derived from the specs.
        """
        # Collect study IDs
        study_ids = list(dict.fromkeys(s.study_id for s in specs))

        # Determine domain_class from first spec
        domain_class = specs[0].domain_class if specs else "Unknown"

        # Gather all variable mappings grouped by SDTM variable
        var_mappings: dict[str, list[Any]] = {}
        for spec in specs:
            for vm in spec.variable_mappings:
                var_mappings.setdefault(vm.sdtm_variable, []).append(vm)

        # Build variable patterns
        variable_patterns: list[VariablePattern] = []
        pattern_counter: Counter[str] = Counter()

        for sdtm_var, mappings in var_mappings.items():
            # Count patterns for this variable to find the mode
            var_pattern_counts = Counter(m.mapping_pattern for m in mappings)
            typical_pattern = var_pattern_counts.most_common(1)[0][0]

            # Extract keywords from source variable names and mapping logic
            all_keywords: list[str] = []
            for m in mappings:
                if m.source_variable:
                    all_keywords.extend(_extract_keywords(m.source_variable))
                if m.mapping_logic:
                    all_keywords.extend(_extract_keywords(m.mapping_logic))

            # Deduplicate keywords preserving order
            seen: set[str] = set()
            unique_keywords: list[str] = []
            for kw in all_keywords:
                if kw not in seen:
                    seen.add(kw)
                    unique_keywords.append(kw)

            # Get derivation template from the most common derivation rule
            derivation_template = None
            derivation_rules = [m.derivation_rule for m in mappings if m.derivation_rule]
            if derivation_rules:
                rule_counts = Counter(derivation_rules)
                derivation_template = rule_counts.most_common(1)[0][0]

            variable_patterns.append(
                VariablePattern(
                    sdtm_variable=sdtm_var,
                    typical_pattern=typical_pattern,
                    typical_source_keywords=unique_keywords,
                    derivation_template=derivation_template,
                    common_issues=[],
                )
            )

            # Accumulate pattern distribution across all variables
            for m in mappings:
                pattern_counter[m.mapping_pattern] += 1

        # Compute pattern distribution
        pattern_distribution = dict(pattern_counter)

        # Compute accuracy rate from metrics
        accuracy_rate = 0.0
        if metrics:
            domain_metrics = [m for m in metrics if m.domain == domain]
            if domain_metrics:
                accuracy_rate = sum(m.accuracy_rate for m in domain_metrics) / len(domain_metrics)

        now = datetime.now(tz=UTC).isoformat()
        return DomainTemplate(
            domain=domain,
            domain_class=domain_class,
            source_study_ids=study_ids,
            pattern_distribution=pattern_distribution,
            variable_patterns=variable_patterns,
            accuracy_rate=accuracy_rate,
            created_at=now,
            updated_at=now,
        )

    def save_template(self, template: DomainTemplate) -> None:
        """Save or update a domain template in the database.

        Uses INSERT OR REPLACE keyed on domain (one template per domain).

        Args:
            template: The domain template to persist.
        """
        self._conn.execute(
            """INSERT OR REPLACE INTO domain_templates
               (template_id, domain, domain_class, source_study_ids_json,
                pattern_distribution_json, variable_patterns_json,
                accuracy_rate, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                template.template_id,
                template.domain,
                template.domain_class,
                json.dumps(template.source_study_ids),
                json.dumps(template.pattern_distribution),
                json.dumps([vp.model_dump() for vp in template.variable_patterns]),
                template.accuracy_rate,
                template.created_at,
                template.updated_at,
            ),
        )
        self._conn.commit()

    def get_template(self, domain: str) -> DomainTemplate | None:
        """Retrieve a domain template by domain code.

        Args:
            domain: SDTM domain code (e.g., 'AE').

        Returns:
            DomainTemplate if found, None otherwise.
        """
        row = self._conn.execute(
            "SELECT * FROM domain_templates WHERE domain = ?",
            (domain,),
        ).fetchone()

        if row is None:
            return None

        return self._row_to_template(row)

    def get_all_templates(self) -> list[DomainTemplate]:
        """Retrieve all stored domain templates.

        Returns:
            List of all DomainTemplate objects, ordered by domain.
        """
        rows = self._conn.execute("SELECT * FROM domain_templates ORDER BY domain").fetchall()

        return [self._row_to_template(row) for row in rows]

    def update_template(
        self,
        domain: str,
        new_spec: DomainMappingSpec,
        new_metrics: StudyMetrics | None = None,
    ) -> DomainTemplate:
        """Update an existing template with data from a new study.

        Merges the new spec's patterns into the existing template:
        - Adds the new study_id to source_study_ids
        - Updates pattern_distribution with new variable patterns
        - Merges variable_patterns (new variables added, existing updated)
        - Recalculates accuracy_rate as weighted average

        If no template exists for the domain, builds one from the new spec.

        Args:
            domain: SDTM domain code.
            new_spec: New DomainMappingSpec from a completed study.
            new_metrics: Optional new StudyMetrics for accuracy recalculation.

        Returns:
            Updated DomainTemplate.
        """
        existing = self.get_template(domain)

        if existing is None:
            metrics_list = [new_metrics] if new_metrics else None
            template = self.build_template(domain, [new_spec], metrics_list)
            self.save_template(template)
            return template

        # Add new study_id
        study_ids = list(existing.source_study_ids)
        if new_spec.study_id not in study_ids:
            study_ids.append(new_spec.study_id)

        # Update pattern distribution
        pattern_dist = dict(existing.pattern_distribution)
        for vm in new_spec.variable_mappings:
            pattern_key = vm.mapping_pattern
            pattern_dist[pattern_key] = pattern_dist.get(pattern_key, 0) + 1

        # Merge variable patterns
        existing_patterns = {vp.sdtm_variable: vp for vp in existing.variable_patterns}
        for vm in new_spec.variable_mappings:
            keywords: list[str] = []
            if vm.source_variable:
                keywords.extend(_extract_keywords(vm.source_variable))
            if vm.mapping_logic:
                keywords.extend(_extract_keywords(vm.mapping_logic))

            if vm.sdtm_variable in existing_patterns:
                # Update existing -- keep existing typical_pattern unless new
                # data changes the majority (simple: keep existing for now,
                # a more sophisticated approach would track counts)
                ep = existing_patterns[vm.sdtm_variable]
                merged_keywords = list(ep.typical_source_keywords)
                seen = set(merged_keywords)
                for kw in keywords:
                    if kw not in seen:
                        seen.add(kw)
                        merged_keywords.append(kw)

                derivation = ep.derivation_template
                if vm.derivation_rule and not derivation:
                    derivation = vm.derivation_rule

                existing_patterns[vm.sdtm_variable] = VariablePattern(
                    sdtm_variable=vm.sdtm_variable,
                    typical_pattern=ep.typical_pattern,
                    typical_source_keywords=merged_keywords,
                    derivation_template=derivation,
                    common_issues=ep.common_issues,
                )
            else:
                # New variable not seen before
                seen_kw: set[str] = set()
                unique_kw: list[str] = []
                for kw in keywords:
                    if kw not in seen_kw:
                        seen_kw.add(kw)
                        unique_kw.append(kw)

                existing_patterns[vm.sdtm_variable] = VariablePattern(
                    sdtm_variable=vm.sdtm_variable,
                    typical_pattern=vm.mapping_pattern,
                    typical_source_keywords=unique_kw,
                    derivation_template=vm.derivation_rule,
                    common_issues=[],
                )

        # Recalculate accuracy_rate (weighted average)
        prev_weight = len(existing.source_study_ids)
        if new_metrics:
            new_accuracy = new_metrics.accuracy_rate
            accuracy_rate = (existing.accuracy_rate * prev_weight + new_accuracy) / (
                prev_weight + 1
            )
        else:
            accuracy_rate = existing.accuracy_rate

        now = datetime.now(tz=UTC).isoformat()
        updated = DomainTemplate(
            template_id=existing.template_id,
            domain=domain,
            domain_class=existing.domain_class,
            source_study_ids=study_ids,
            pattern_distribution=pattern_dist,
            variable_patterns=list(existing_patterns.values()),
            accuracy_rate=accuracy_rate,
            created_at=existing.created_at,
            updated_at=now,
        )

        self.save_template(updated)
        return updated

    def close(self) -> None:
        """Close the SQLite database connection."""
        self._conn.close()

    def _row_to_template(self, row: sqlite3.Row) -> DomainTemplate:
        """Convert a SQLite row to a DomainTemplate object.

        Args:
            row: SQLite Row from the domain_templates table.

        Returns:
            DomainTemplate reconstructed from stored JSON.
        """
        return DomainTemplate(
            template_id=row["template_id"],
            domain=row["domain"],
            domain_class=row["domain_class"],
            source_study_ids=json.loads(row["source_study_ids_json"]),
            pattern_distribution=json.loads(row["pattern_distribution_json"]),
            variable_patterns=[
                VariablePattern(**vp) for vp in json.loads(row["variable_patterns_json"])
            ],
            accuracy_rate=row["accuracy_rate"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
