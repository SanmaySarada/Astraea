"""Validate-fix-revalidate loop engine.

Orchestrates the auto-fix cycle: validate all domains, apply auto-fixes,
re-validate to confirm fixes worked, repeat up to max_iterations. Produces
a comprehensive FixLoopResult with accumulated fix actions, remaining issues,
human-action items, and the final validation report.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pyreadstat
from loguru import logger
from pydantic import BaseModel, Field

from astraea.models.mapping import DomainMappingSpec
from astraea.validation.autofix import (
    AutoFixer,
    FixAction,
    FixClassification,
    IssueClassification,
)
from astraea.validation.engine import ValidationEngine
from astraea.validation.report import ValidationReport
from astraea.validation.rules.base import RuleResult


class IterationResult(BaseModel):
    """Per-iteration breakdown of the fix loop.

    Tracks how many issues were found, fixed, and remaining for each
    iteration so progress can be visualized.
    """

    iteration: int = Field(..., description="1-indexed iteration number")
    issues_found: int = Field(
        ..., description="Total issues found in this iteration's validation"
    )
    auto_fixed: int = Field(
        ..., description="Number of issues auto-fixed in this iteration"
    )
    remaining_auto_fixable: int = Field(
        ...,
        description="Auto-fixable issues not yet addressed (should decrease)",
    )
    needs_human: int = Field(
        ..., description="Issues requiring human intervention"
    )
    fix_actions: list[FixAction] = Field(
        default_factory=list, description="Fixes applied in this iteration"
    )


class FixLoopResult(BaseModel):
    """Comprehensive result from the validate-fix-revalidate loop.

    Contains the full audit trail, iteration breakdown, remaining issues,
    and the final validation report after all iterations complete.
    """

    iterations_run: int = Field(
        ..., description="How many iterations were executed"
    )
    max_iterations: int = Field(
        default=3, description="Configured max iterations"
    )
    converged: bool = Field(
        ...,
        description="True if loop stopped because no more auto-fixable issues",
    )
    total_fixed: int = Field(
        ..., description="Total fixes across all iterations"
    )
    remaining_issues: list[RuleResult] = Field(
        default_factory=list,
        description="Issues that still exist after all iterations",
    )
    needs_human_issues: list[IssueClassification] = Field(
        default_factory=list,
        description="Classified needs-human issues with context",
    )
    all_fix_actions: list[FixAction] = Field(
        default_factory=list,
        description="Accumulated audit trail from all iterations",
    )
    iteration_details: list[IterationResult] = Field(
        default_factory=list, description="Per-iteration breakdown"
    )
    final_report: ValidationReport = Field(
        ..., description="Validation report after the last iteration"
    )


class FixLoopEngine:
    """Orchestrates the validate-fix-revalidate loop.

    Runs validation, classifies issues, applies auto-fixes, and repeats
    until convergence (no more auto-fixable issues) or max iterations
    reached. Optionally writes fixed datasets to XPT and audit trail
    to JSON.
    """

    def __init__(
        self,
        *,
        engine: ValidationEngine,
        auto_fixer: AutoFixer,
        max_iterations: int = 3,
    ) -> None:
        """Initialize the fix loop engine.

        Args:
            engine: ValidationEngine for running validation rules.
            auto_fixer: AutoFixer for classifying and fixing issues.
            max_iterations: Maximum number of validate-fix-revalidate cycles.
        """
        self._engine = engine
        self._auto_fixer = auto_fixer
        self._max_iterations = max_iterations

    def run_fix_loop(
        self,
        domains: dict[str, tuple[pd.DataFrame, DomainMappingSpec]],
        *,
        output_dir: Path | None = None,
        study_id: str = "UNKNOWN",
    ) -> FixLoopResult:
        """Run the validate-fix-revalidate loop.

        Iterates up to max_iterations times:
        1. Validate all domains
        2. Classify all issues as auto-fixable or needs-human
        3. If no auto-fixable issues, stop (converged)
        4. Apply fixes per domain, updating the domains dict in-place
        5. Record iteration details

        After the loop, runs a final validation pass and optionally
        writes fixed datasets and audit trail.

        Args:
            domains: Mapping of domain code to (DataFrame, DomainMappingSpec).
                DataFrames are replaced in-place as fixes are applied.
            output_dir: If provided, write fixed XPTs and audit JSON here.
            study_id: Study identifier for the validation report.

        Returns:
            FixLoopResult with full breakdown of the fix loop execution.
        """
        all_fix_actions: list[FixAction] = []
        iteration_details: list[IterationResult] = []
        converged = False
        last_needs_human: list[IssueClassification] = []

        for iteration in range(1, self._max_iterations + 1):
            logger.info(
                "Fix loop iteration {}/{} starting",
                iteration,
                self._max_iterations,
            )

            # Step 1: Validate all domains
            results = self._engine.validate_all(domains)

            # Step 2: Classify all issues
            classifications = [
                self._auto_fixer.classify_issue(r) for r in results
            ]
            auto_fixable = [
                c
                for c in classifications
                if c.classification == FixClassification.AUTO_FIXABLE
            ]
            needs_human = [
                c
                for c in classifications
                if c.classification == FixClassification.NEEDS_HUMAN
            ]
            last_needs_human = needs_human

            # Step 3: If no auto-fixable issues, stop
            if not auto_fixable:
                logger.info(
                    "Fix loop converged at iteration {}: no auto-fixable issues remain",
                    iteration,
                )
                iteration_details.append(
                    IterationResult(
                        iteration=iteration,
                        issues_found=len(results),
                        auto_fixed=0,
                        remaining_auto_fixable=0,
                        needs_human=len(needs_human),
                        fix_actions=[],
                    )
                )
                converged = True
                break

            # Step 4: Apply fixes per domain
            iteration_fix_actions: list[FixAction] = []
            for domain_code, (df, spec) in domains.items():
                domain_issues = [
                    c.result
                    for c in auto_fixable
                    if c.result.domain == domain_code
                ]
                if not domain_issues:
                    continue
                fixed_df, fixed_spec, fix_actions = self._auto_fixer.apply_fixes(
                    domain_code, df, spec, domain_issues
                )
                domains[domain_code] = (fixed_df, fixed_spec)
                iteration_fix_actions.extend(fix_actions)

            all_fix_actions.extend(iteration_fix_actions)

            # Record iteration detail
            iteration_details.append(
                IterationResult(
                    iteration=iteration,
                    issues_found=len(results),
                    auto_fixed=len(iteration_fix_actions),
                    remaining_auto_fixable=len(auto_fixable)
                    - len(iteration_fix_actions),
                    needs_human=len(needs_human),
                    fix_actions=iteration_fix_actions,
                )
            )

            logger.info(
                "Iteration {}: fixed {} issues, {} needs-human remain",
                iteration,
                len(iteration_fix_actions),
                len(needs_human),
            )

        # Step 5: Final validation pass
        logger.info("Running final validation pass after fix loop")
        final_results = self._engine.validate_all(domains)
        final_report = ValidationReport.from_results(
            study_id, final_results, list(domains.keys())
        )

        # Step 6: Write fixed DataFrames to XPT if output_dir given
        if output_dir is not None:
            _write_fixed_datasets(domains, output_dir)

        # Step 7: Write audit trail to JSON
        if output_dir is not None:
            _write_audit_trail(all_fix_actions, output_dir)

        iterations_run = len(iteration_details)

        return FixLoopResult(
            iterations_run=iterations_run,
            max_iterations=self._max_iterations,
            converged=converged,
            total_fixed=len(all_fix_actions),
            remaining_issues=final_results,
            needs_human_issues=last_needs_human,
            all_fix_actions=all_fix_actions,
            iteration_details=iteration_details,
            final_report=final_report,
        )


def _write_fixed_datasets(
    domains: dict[str, tuple[pd.DataFrame, DomainMappingSpec]],
    output_dir: Path,
) -> None:
    """Write fixed DataFrames to XPT files in output_dir.

    Uses pyreadstat.write_xport directly (not the full xpt_writer which
    does strict validation -- fixes may not satisfy all XPT constraints yet).
    Column labels are derived from the mapping spec's variable_mappings.

    Args:
        domains: Mapping of domain code to (DataFrame, DomainMappingSpec).
        output_dir: Directory to write XPT files to.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    for domain_code, (df, spec) in domains.items():
        xpt_path = output_dir / f"{domain_code.lower()}.xpt"

        # Build column labels from spec
        column_labels: dict[str, str] = {}
        for vm in spec.variable_mappings:
            col_upper = vm.sdtm_variable.upper()
            if col_upper in {str(c).upper() for c in df.columns}:
                column_labels[col_upper] = vm.sdtm_label[:40]

        # Uppercase columns for SDTM convention
        df_out = df.copy()
        rename_map = {col: str(col).upper() for col in df_out.columns}
        df_out = df_out.rename(columns=rename_map)

        try:
            pyreadstat.write_xport(
                df_out,
                str(xpt_path),
                table_name=domain_code.upper(),
                column_labels=column_labels,
                file_format_version=5,
            )
            logger.info(
                "Wrote fixed dataset: {} ({} rows) -> {}",
                domain_code,
                len(df_out),
                xpt_path,
            )
        except Exception as exc:
            logger.error(
                "Failed to write XPT for domain {}: {}", domain_code, exc
            )


def _write_audit_trail(
    fix_actions: list[FixAction],
    output_dir: Path,
) -> None:
    """Write all FixActions to autofix_audit.json.

    Args:
        fix_actions: List of FixAction records to serialize.
        output_dir: Directory to write the audit file to.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    audit_path = output_dir / "autofix_audit.json"

    audit_data = [action.model_dump() for action in fix_actions]

    with open(audit_path, "w") as f:
        json.dump(audit_data, f, indent=2, default=str)

    logger.info(
        "Wrote audit trail: {} fix action(s) -> {}",
        len(fix_actions),
        audit_path,
    )


def format_needs_human_report(
    issues: list[IssueClassification],
) -> str:
    """Format needs-human issues for CLI display.

    Groups issues by domain and presents each with rule ID, variable,
    message, and suggested fix in a readable format.

    Args:
        issues: List of IssueClassification items (needs-human only).

    Returns:
        Formatted string suitable for terminal output.
    """
    if not issues:
        return "No issues requiring human intervention."

    # Group by domain
    by_domain: dict[str, list[IssueClassification]] = {}
    for ic in issues:
        domain = ic.result.domain or "GENERAL"
        by_domain.setdefault(domain, []).append(ic)

    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("ISSUES REQUIRING HUMAN INTERVENTION")
    lines.append("=" * 60)
    lines.append("")

    total = len(issues)
    lines.append(f"Total: {total} issue(s) across {len(by_domain)} domain(s)")
    lines.append("")

    for domain in sorted(by_domain):
        domain_issues = by_domain[domain]
        lines.append(f"--- {domain} ({len(domain_issues)} issue(s)) ---")
        lines.append("")

        for i, ic in enumerate(domain_issues, 1):
            r = ic.result
            lines.append(f"  {i}. [{r.rule_id}] {r.severity.display_name}")
            if r.variable:
                lines.append(f"     Variable: {r.variable}")
            lines.append(f"     Message:  {r.message}")
            lines.append(f"     Reason:   {ic.reason}")
            if ic.suggested_fix:
                lines.append(f"     Suggested: {ic.suggested_fix}")
            lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)
