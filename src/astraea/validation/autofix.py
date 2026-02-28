"""Auto-fixer for deterministic SDTM validation issues.

Classifies validation RuleResults as auto-fixable or needs-human,
applies deterministic fixes (CT case normalization, missing columns,
name/label truncation, ASCII cleanup), and produces an audit trail
of all changes via FixAction records.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import StrEnum

import pandas as pd
from loguru import logger
from pydantic import BaseModel, Field

from astraea.models.mapping import DomainMappingSpec
from astraea.reference.controlled_terms import CTReference
from astraea.reference.sdtm_ig import SDTMReference
from astraea.transforms.ascii_validation import fix_common_non_ascii
from astraea.validation.rules.base import RuleResult


class FixClassification(StrEnum):
    """Whether a validation issue can be auto-fixed or needs human review."""

    AUTO_FIXABLE = "auto_fixable"
    NEEDS_HUMAN = "needs_human"


class FixAction(BaseModel):
    """Audit trail record for a single auto-fix action.

    Captures before/after state so every change is traceable and
    reversible if needed.
    """

    rule_id: str = Field(..., description="Which rule triggered this fix")
    domain: str = Field(..., description="Domain being fixed")
    variable: str | None = Field(default=None, description="Variable being fixed")
    fix_type: str = Field(
        ...,
        description=(
            "Fix category: ct_case_normalize, add_missing_column, "
            "truncate_label, truncate_name, fix_ascii, fix_domain_value, "
            "fix_date_format"
        ),
    )
    before_value: str = Field(..., description="Value/state before fix")
    after_value: str = Field(..., description="Value/state after fix")
    affected_count: int = Field(..., description="Number of rows affected")
    timestamp: str = Field(..., description="ISO 8601 timestamp of fix")


class IssueClassification(BaseModel):
    """Classification result for a single validation RuleResult."""

    result: RuleResult = Field(..., description="The original validation result")
    classification: FixClassification = Field(..., description="Auto-fixable or needs human")
    reason: str = Field(..., description="Why it is classified this way")
    suggested_fix: str | None = Field(default=None, description="For needs-human, provide context")


# Rule IDs that are auto-fixable for specific variables only
_AUTO_FIXABLE_MISSING_VARS = {"STUDYID", "DOMAIN", "USUBJID"}


class AutoFixer:
    """Classifies validation issues and applies deterministic fixes.

    Each fix function is a pure transformation that returns a copy
    of the data. The audit trail captures every change.
    """

    def __init__(
        self,
        *,
        ct_ref: CTReference,
        sdtm_ref: SDTMReference,
    ) -> None:
        """Initialize AutoFixer with reference data.

        Args:
            ct_ref: Controlled Terminology reference for codelist lookups.
            sdtm_ref: SDTM-IG reference for domain/variable lookups.
        """
        self._ct_ref = ct_ref
        self._sdtm_ref = sdtm_ref

    def classify_issue(self, result: RuleResult) -> IssueClassification:
        """Classify a single RuleResult as auto-fixable or needs-human.

        Args:
            result: The validation finding to classify.

        Returns:
            IssueClassification with the classification and reason.
        """
        rule_id = result.rule_id

        # ASTR-T001: CT value mismatch -- auto-fixable only if case mismatch
        if rule_id == "ASTR-T001":
            return self._classify_ct_issue(result)

        # ASTR-T002: DOMAIN column wrong/missing -- always auto-fixable
        if rule_id == "ASTR-T002":
            return IssueClassification(
                result=result,
                classification=FixClassification.AUTO_FIXABLE,
                reason="DOMAIN column can be set to the domain code deterministically",
            )

        # ASTR-P001: Required variable missing -- auto-fixable for STUDYID/DOMAIN/USUBJID only
        if rule_id == "ASTR-P001":
            var = (result.variable or "").upper()
            if var in _AUTO_FIXABLE_MISSING_VARS:
                return IssueClassification(
                    result=result,
                    classification=FixClassification.AUTO_FIXABLE,
                    reason=f"{var} has a deterministic value that can be added automatically",
                )
            return IssueClassification(
                result=result,
                classification=FixClassification.NEEDS_HUMAN,
                reason=f"Required variable {var} needs domain expertise to populate",
                suggested_fix=result.fix_suggestion,
            )

        # ASTR-L001: Variable name >8 chars -- auto-fixable
        if rule_id == "ASTR-L001":
            return IssueClassification(
                result=result,
                classification=FixClassification.AUTO_FIXABLE,
                reason="Variable name can be truncated to 8 characters",
            )

        # ASTR-L002: Variable label >40 chars -- auto-fixable
        if rule_id == "ASTR-L002":
            return IssueClassification(
                result=result,
                classification=FixClassification.AUTO_FIXABLE,
                reason="Variable label can be truncated to 40 characters",
            )

        # ASTR-L003: Character value >200 bytes -- needs human
        if rule_id == "ASTR-L003":
            return IssueClassification(
                result=result,
                classification=FixClassification.NEEDS_HUMAN,
                reason="Truncating data values is lossy and may require SUPPQUAL split",
                suggested_fix=result.fix_suggestion,
            )

        # ASTR-F001: Date format -- needs human
        if rule_id == "ASTR-F001":
            return IssueClassification(
                result=result,
                classification=FixClassification.NEEDS_HUMAN,
                reason="Date conversion requires understanding the source format",
                suggested_fix=result.fix_suggestion,
            )

        # ASTR-F002: ASCII -- auto-fixable
        if rule_id == "ASTR-F002":
            return IssueClassification(
                result=result,
                classification=FixClassification.AUTO_FIXABLE,
                reason="Common non-ASCII characters can be replaced with ASCII equivalents",
            )

        # ASTR-F003: File naming -- auto-fixable as metadata note
        if rule_id == "ASTR-F003":
            return IssueClassification(
                result=result,
                classification=FixClassification.AUTO_FIXABLE,
                reason="File naming tracked as metadata; actual rename deferred to loop engine",
            )

        # FDA Business Rules (FDAB*) -- needs human
        if rule_id.startswith("FDAB"):
            return IssueClassification(
                result=result,
                classification=FixClassification.NEEDS_HUMAN,
                reason="FDA Business Rules require domain expertise to resolve",
                suggested_fix=result.fix_suggestion,
            )

        # Cross-domain rules (ASTR-C*) -- needs human
        if rule_id.startswith("ASTR-C"):
            return IssueClassification(
                result=result,
                classification=FixClassification.NEEDS_HUMAN,
                reason="Cross-domain issues require multi-domain context to resolve",
                suggested_fix=result.fix_suggestion,
            )

        # Everything else -- needs human
        return IssueClassification(
            result=result,
            classification=FixClassification.NEEDS_HUMAN,
            reason=f"Rule {rule_id} has no auto-fix implementation",
            suggested_fix=result.fix_suggestion,
        )

    def _classify_ct_issue(self, result: RuleResult) -> IssueClassification:
        """Classify a CT value mismatch as case-fixable or needs-human.

        Checks if the invalid values in the message are case-mismatches
        against the codelist. If ALL invalid values match a term when
        compared case-insensitively, it's auto-fixable.
        """
        var_name = result.variable
        if not var_name:
            return IssueClassification(
                result=result,
                classification=FixClassification.NEEDS_HUMAN,
                reason="No variable specified for CT validation",
                suggested_fix=result.fix_suggestion,
            )

        # Try to find the codelist via variable-to-codelist reverse lookup
        cl = self._ct_ref.get_codelist_for_variable(var_name)
        if cl is None:
            return IssueClassification(
                result=result,
                classification=FixClassification.NEEDS_HUMAN,
                reason=f"Cannot find codelist for variable {var_name}",
                suggested_fix=result.fix_suggestion,
            )

        # Build case-insensitive lookup
        case_map = {term.upper(): term for term in cl.terms}

        # Extract invalid values from message -- they appear as repr() strings
        # The message format is: "Invalid CT value(s) in VAR: 'val1', 'val2'"
        # Parse quoted values from the message
        quoted_values = re.findall(r"'([^']*)'", result.message)
        if not quoted_values:
            # Can't parse values from message, be conservative
            return IssueClassification(
                result=result,
                classification=FixClassification.NEEDS_HUMAN,
                reason="Cannot determine invalid values from message",
                suggested_fix=result.fix_suggestion,
            )

        # Check if ALL invalid values are just case mismatches
        all_case_fixable = all(v not in cl.terms and v.upper() in case_map for v in quoted_values)

        if all_case_fixable:
            return IssueClassification(
                result=result,
                classification=FixClassification.AUTO_FIXABLE,
                reason="All invalid values are case mismatches that can be normalized",
            )

        return IssueClassification(
            result=result,
            classification=FixClassification.NEEDS_HUMAN,
            reason="Some values do not match any codelist term even case-insensitively",
            suggested_fix=result.fix_suggestion,
        )

    def apply_fixes(
        self,
        domain: str,
        df: pd.DataFrame,
        spec: DomainMappingSpec,
        issues: list[RuleResult],
    ) -> tuple[pd.DataFrame, DomainMappingSpec, list[FixAction]]:
        """Apply all auto-fixable fixes to a domain dataset.

        Classifies each issue, applies the appropriate fix function for
        auto-fixable ones, and returns the modified DataFrame, spec, and
        a complete audit trail.

        Args:
            domain: SDTM domain code.
            df: The generated SDTM DataFrame (not modified in place).
            spec: The mapping specification (not modified in place).
            issues: List of validation RuleResults to process.

        Returns:
            Tuple of (fixed_df, fixed_spec, fix_actions).
            fixed_df and fixed_spec are copies; originals are unchanged.
        """
        fixed_df = df.copy()
        fixed_spec = spec.model_copy(deep=True)
        all_actions: list[FixAction] = []

        for issue in issues:
            classification = self.classify_issue(issue)
            if classification.classification != FixClassification.AUTO_FIXABLE:
                logger.debug(
                    "Skipping {} ({}): {}",
                    issue.rule_id,
                    issue.variable or "n/a",
                    classification.reason,
                )
                continue

            rule_id = issue.rule_id
            actions: list[FixAction] = []

            if rule_id == "ASTR-T001":
                fixed_df, actions = self._fix_ct_case(domain, fixed_df, issue, fixed_spec)
            elif rule_id == "ASTR-T002":
                fixed_df, actions = self._fix_domain_column(domain, fixed_df, issue)
            elif rule_id == "ASTR-P001":
                var = (issue.variable or "").upper()
                if var == "STUDYID":
                    fixed_df, actions = self._fix_missing_studyid(domain, fixed_df, fixed_spec)
                elif var == "DOMAIN":
                    # Reuse domain column fix
                    fixed_df, actions = self._fix_domain_column(domain, fixed_df, issue)
                elif var == "USUBJID":
                    # USUBJID requires source data; skip if not derivable
                    logger.warning("USUBJID auto-fix requires source data -- skipping")
                    continue
            elif rule_id == "ASTR-L001":
                fixed_df, actions = self._fix_variable_name_length(domain, fixed_df, issue)
            elif rule_id == "ASTR-L002":
                fixed_spec, actions = self._fix_variable_label_length(domain, fixed_spec, issue)
            elif rule_id == "ASTR-F002":
                fixed_df, actions = self._fix_ascii(domain, fixed_df, issue)
            elif rule_id == "ASTR-F003":
                actions = self._fix_file_naming(domain, issue)

            all_actions.extend(actions)

        if all_actions:
            logger.info(
                "Applied {} auto-fix(es) to domain {}",
                len(all_actions),
                domain,
            )
        else:
            logger.debug("No auto-fixes applied to domain {}", domain)

        return fixed_df, fixed_spec, all_actions

    # ------------------------------------------------------------------ #
    # Private fix functions
    # ------------------------------------------------------------------ #

    def _fix_ct_case(
        self,
        domain: str,
        df: pd.DataFrame,
        result: RuleResult,
        spec: DomainMappingSpec,
    ) -> tuple[pd.DataFrame, list[FixAction]]:
        """Fix CT values that differ only in case from valid codelist terms.

        Looks up the codelist from the spec's variable mapping. For each
        invalid value that matches a codelist term case-insensitively,
        replaces with the correct-case term.
        """
        actions: list[FixAction] = []
        var_name = result.variable
        if not var_name or var_name not in df.columns:
            return df, actions

        # Find the codelist code from the spec
        codelist_code: str | None = None
        for vm in spec.variable_mappings:
            if vm.sdtm_variable.upper() == var_name.upper() and vm.codelist_code:
                codelist_code = vm.codelist_code
                break

        if not codelist_code:
            return df, actions

        cl = self._ct_ref.lookup_codelist(codelist_code)
        if cl is None:
            return df, actions

        # Build case-insensitive lookup: upper(term) -> correct term
        case_map: dict[str, str] = {term.upper(): term for term in cl.terms}

        fixed_df = df.copy()
        non_null_mask = fixed_df[var_name].notna()
        total_fixed = 0

        for idx in fixed_df.index[non_null_mask]:
            val = str(fixed_df.at[idx, var_name])
            if val not in cl.terms and val.upper() in case_map:
                correct_val = case_map[val.upper()]
                fixed_df.at[idx, var_name] = correct_val
                total_fixed += 1

        if total_fixed > 0:
            now = datetime.now(tz=UTC).isoformat()
            actions.append(
                FixAction(
                    rule_id=result.rule_id,
                    domain=domain,
                    variable=var_name,
                    fix_type="ct_case_normalize",
                    before_value=f"Case-mismatched values in {var_name}",
                    after_value=f"Normalized to codelist {codelist_code} terms",
                    affected_count=total_fixed,
                    timestamp=now,
                )
            )
            logger.info(
                "CT case fix: {} values in {}.{} normalized to codelist {}",
                total_fixed,
                domain,
                var_name,
                codelist_code,
            )

        return fixed_df, actions

    def _fix_domain_column(
        self,
        domain: str,
        df: pd.DataFrame,
        result: RuleResult,
    ) -> tuple[pd.DataFrame, list[FixAction]]:
        """Add or correct the DOMAIN column.

        If DOMAIN is missing, adds it. If present with wrong values,
        sets all values to the domain code.
        """
        fixed_df = df.copy()
        now = datetime.now(tz=UTC).isoformat()

        if "DOMAIN" not in fixed_df.columns:
            fixed_df["DOMAIN"] = domain
            action = FixAction(
                rule_id=result.rule_id,
                domain=domain,
                variable="DOMAIN",
                fix_type="add_missing_column",
                before_value="Column missing",
                after_value=f"Added with value '{domain}'",
                affected_count=len(fixed_df),
                timestamp=now,
            )
            logger.info("Added missing DOMAIN column to {} with value '{}'", domain, domain)
            return fixed_df, [action]

        # Fix wrong values
        wrong_mask = fixed_df["DOMAIN"].astype(str) != domain
        wrong_count = int(wrong_mask.sum())
        if wrong_count > 0:
            old_values = fixed_df.loc[wrong_mask, "DOMAIN"].astype(str).unique().tolist()
            fixed_df["DOMAIN"] = domain
            action = FixAction(
                rule_id=result.rule_id,
                domain=domain,
                variable="DOMAIN",
                fix_type="fix_domain_value",
                before_value=f"Wrong values: {', '.join(repr(v) for v in old_values[:5])}",
                after_value=f"Set all to '{domain}'",
                affected_count=wrong_count,
                timestamp=now,
            )
            logger.info(
                "Fixed DOMAIN column in {}: {} rows corrected",
                domain,
                wrong_count,
            )
            return fixed_df, [action]

        return fixed_df, []

    def _fix_missing_studyid(
        self,
        domain: str,
        df: pd.DataFrame,
        spec: DomainMappingSpec,
    ) -> tuple[pd.DataFrame, list[FixAction]]:
        """Add STUDYID column with value from spec.study_id."""
        fixed_df = df.copy()
        now = datetime.now(tz=UTC).isoformat()

        fixed_df["STUDYID"] = spec.study_id
        action = FixAction(
            rule_id="ASTR-P001",
            domain=domain,
            variable="STUDYID",
            fix_type="add_missing_column",
            before_value="Column missing",
            after_value=f"Added with value '{spec.study_id}'",
            affected_count=len(fixed_df),
            timestamp=now,
        )
        logger.info(
            "Added missing STUDYID column to {} with value '{}'",
            domain,
            spec.study_id,
        )
        return fixed_df, [action]

    def _fix_variable_name_length(
        self,
        domain: str,
        df: pd.DataFrame,
        result: RuleResult,
    ) -> tuple[pd.DataFrame, list[FixAction]]:
        """Rename column to its first 8 characters. Appends digit on collision."""
        fixed_df = df.copy()
        var_name = result.variable
        if not var_name or var_name not in fixed_df.columns:
            return fixed_df, []

        truncated = var_name[:8]
        # Handle collision
        existing_cols = {str(c) for c in fixed_df.columns}
        if truncated in existing_cols and truncated != var_name:
            for i in range(1, 10):
                candidate = var_name[:7] + str(i)
                if candidate not in existing_cols:
                    truncated = candidate
                    break

        now = datetime.now(tz=UTC).isoformat()
        fixed_df = fixed_df.rename(columns={var_name: truncated})
        action = FixAction(
            rule_id=result.rule_id,
            domain=domain,
            variable=var_name,
            fix_type="truncate_name",
            before_value=f"'{var_name}' ({len(var_name)} chars)",
            after_value=f"'{truncated}' ({len(truncated)} chars)",
            affected_count=len(fixed_df),
            timestamp=now,
        )
        logger.info(
            "Renamed variable '{}' -> '{}' in domain {}",
            var_name,
            truncated,
            domain,
        )
        return fixed_df, [action]

    def _fix_variable_label_length(
        self,
        domain: str,
        spec: DomainMappingSpec,
        result: RuleResult,
    ) -> tuple[DomainMappingSpec, list[FixAction]]:
        """Truncate variable label in the spec to 40 characters."""
        fixed_spec = spec.model_copy(deep=True)
        var_name = result.variable
        if not var_name:
            return fixed_spec, []

        now = datetime.now(tz=UTC).isoformat()
        actions: list[FixAction] = []

        for vm in fixed_spec.variable_mappings:
            if vm.sdtm_variable.upper() == var_name.upper() and len(vm.sdtm_label) > 40:
                old_label = vm.sdtm_label
                vm.sdtm_label = vm.sdtm_label[:40]
                actions.append(
                    FixAction(
                        rule_id=result.rule_id,
                        domain=domain,
                        variable=var_name,
                        fix_type="truncate_label",
                        before_value=f"'{old_label}' ({len(old_label)} chars)",
                        after_value=f"'{vm.sdtm_label}' (40 chars)",
                        affected_count=0,
                        timestamp=now,
                    )
                )
                logger.info(
                    "Truncated label for {}.{} from {} to 40 chars",
                    domain,
                    var_name,
                    len(old_label),
                )

        return fixed_spec, actions

    def _fix_ascii(
        self,
        domain: str,
        df: pd.DataFrame,
        result: RuleResult,
    ) -> tuple[pd.DataFrame, list[FixAction]]:
        """Fix non-ASCII characters using fix_common_non_ascii()."""
        fixed_df = fix_common_non_ascii(df)
        now = datetime.now(tz=UTC).isoformat()

        action = FixAction(
            rule_id=result.rule_id,
            domain=domain,
            variable=result.variable,
            fix_type="fix_ascii",
            before_value=f"Non-ASCII characters in {result.variable or 'multiple columns'}",
            after_value="Replaced with ASCII equivalents",
            affected_count=result.affected_count,
            timestamp=now,
        )
        logger.info(
            "Fixed non-ASCII characters in domain {} ({})",
            domain,
            result.variable or "multiple columns",
        )
        return fixed_df, [action]

    def _fix_file_naming(
        self,
        domain: str,
        result: RuleResult,
    ) -> list[FixAction]:
        """Track file naming fix as metadata (actual rename deferred)."""
        now = datetime.now(tz=UTC).isoformat()
        action = FixAction(
            rule_id=result.rule_id,
            domain=domain,
            variable=None,
            fix_type="fix_file_naming",
            before_value=f"Domain code '{domain}' invalid for file naming",
            after_value=f"Tracked for rename to '{domain.lower()}.xpt'",
            affected_count=0,
            timestamp=now,
        )
        logger.info("File naming fix tracked for domain {}", domain)
        return [action]
