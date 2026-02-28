"""FDA Technical Rejection Criteria (TRC) pre-checks.

These checks verify submission-level artifacts that, if missing or incorrect,
will cause immediate FDA technical rejection. TRCPreCheck is NOT a
ValidationRule subclass -- it checks submission-level artifacts, not
individual domain datasets.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from astraea.validation.rules.base import RuleCategory, RuleResult, RuleSeverity, ValidationRule


class TRCPreCheck:
    """FDA Technical Rejection Criteria pre-check.

    Validates submission-level requirements that cause immediate FDA rejection
    if not met. These are the most critical checks in the validation pipeline.
    """

    def check_all(
        self,
        generated_domains: dict[str, pd.DataFrame],
        output_dir: Path,
        study_id: str,
    ) -> list[RuleResult]:
        """Run all TRC pre-checks.

        Args:
            generated_domains: Mapping of domain code to generated DataFrame.
            output_dir: Path to the output directory where XPT/define.xml live.
            study_id: Expected study identifier for consistency check.

        Returns:
            List of RuleResult findings. All failures are ERROR severity.
        """
        results: list[RuleResult] = []

        results.extend(self._check_dm_present(generated_domains))
        results.extend(self._check_ts_present(generated_domains))
        results.extend(self._check_define_xml_present(output_dir))
        results.extend(self._check_studyid_consistent(generated_domains, study_id))
        results.extend(self._check_filename_convention(output_dir))

        return results

    def _check_dm_present(self, generated_domains: dict[str, pd.DataFrame]) -> list[RuleResult]:
        """FDA-TRC-1736: DM domain must be present in submission."""
        if "DM" not in generated_domains:
            return [
                RuleResult(
                    rule_id="FDA-TRC-1736",
                    rule_description="DM domain must be present",
                    category=RuleCategory.FDA_TRC,
                    severity=RuleSeverity.ERROR,
                    message="DM (Demographics) domain is missing -- FDA will reject submission",
                    fix_suggestion="Generate the DM domain before submission",
                )
            ]

        dm_df = generated_domains["DM"]
        if dm_df.empty:
            return [
                RuleResult(
                    rule_id="FDA-TRC-1736",
                    rule_description="DM domain must be present",
                    category=RuleCategory.FDA_TRC,
                    severity=RuleSeverity.ERROR,
                    domain="DM",
                    message="DM domain exists but has zero records",
                    fix_suggestion="Populate the DM domain with subject data",
                )
            ]

        return []

    def _check_ts_present(self, generated_domains: dict[str, pd.DataFrame]) -> list[RuleResult]:
        """FDA-TRC-1734: TS domain must be present with SSTDTC parameter."""
        results: list[RuleResult] = []

        if "TS" not in generated_domains:
            results.append(
                RuleResult(
                    rule_id="FDA-TRC-1734",
                    rule_description="TS domain must be present with SSTDTC",
                    category=RuleCategory.FDA_TRC,
                    severity=RuleSeverity.ERROR,
                    message="TS (Trial Summary) domain is missing -- FDA will reject submission",
                    fix_suggestion="Generate the TS domain with required parameters",
                )
            )
            return results

        ts_df = generated_domains["TS"]
        if "TSPARMCD" not in ts_df.columns:
            results.append(
                RuleResult(
                    rule_id="FDA-TRC-1734",
                    rule_description="TS domain must be present with SSTDTC",
                    category=RuleCategory.FDA_TRC,
                    severity=RuleSeverity.ERROR,
                    domain="TS",
                    message="TS domain is missing TSPARMCD column",
                    fix_suggestion="Add TSPARMCD column to TS domain",
                )
            )
            return results

        # Check for SSTDTC parameter
        tsparmcds = set(ts_df["TSPARMCD"].dropna().astype(str).str.upper())
        if "SSTDTC" not in tsparmcds:
            results.append(
                RuleResult(
                    rule_id="FDA-TRC-1734",
                    rule_description="TS domain must be present with SSTDTC",
                    category=RuleCategory.FDA_TRC,
                    severity=RuleSeverity.ERROR,
                    domain="TS",
                    variable="TSPARMCD",
                    message="TS domain is missing SSTDTC parameter (Study Start Date)",
                    fix_suggestion="Add SSTDTC parameter to TS domain",
                )
            )

        return results

    def _check_define_xml_present(self, output_dir: Path) -> list[RuleResult]:
        """FDA-TRC-1735: define.xml must be present in submission directory."""
        define_path = output_dir / "define.xml"
        if not define_path.exists():
            return [
                RuleResult(
                    rule_id="FDA-TRC-1735",
                    rule_description="define.xml must be present",
                    category=RuleCategory.FDA_TRC,
                    severity=RuleSeverity.ERROR,
                    message=f"define.xml not found at {define_path}",
                    fix_suggestion="Generate define.xml before submission",
                )
            ]
        return []

    def _check_studyid_consistent(
        self,
        generated_domains: dict[str, pd.DataFrame],
        study_id: str,
    ) -> list[RuleResult]:
        """FDA-TRC-STUDYID: STUDYID must be consistent across all domains."""
        results: list[RuleResult] = []
        mismatched_domains: list[str] = []

        for domain_code, df in generated_domains.items():
            if "STUDYID" not in df.columns:
                continue
            domain_studyids = set(df["STUDYID"].dropna().unique())
            if domain_studyids and domain_studyids != {study_id}:
                mismatched_domains.append(domain_code)

        if mismatched_domains:
            results.append(
                RuleResult(
                    rule_id="FDA-TRC-STUDYID",
                    rule_description="STUDYID must be consistent across all domains",
                    category=RuleCategory.FDA_TRC,
                    severity=RuleSeverity.ERROR,
                    message=(
                        f"STUDYID mismatch in domain(s): {sorted(mismatched_domains)}. "
                        f"Expected: '{study_id}'"
                    ),
                    affected_count=len(mismatched_domains),
                    fix_suggestion=f"Set STUDYID to '{study_id}' in all domains",
                )
            )

        return results

    def _check_filename_convention(self, output_dir: Path) -> list[RuleResult]:
        """FDA-TRC-FILENAME: Dataset filenames must be lowercase .xpt."""
        results: list[RuleResult] = []

        if not output_dir.exists():
            return results

        xpt_files = list(output_dir.glob("*.xpt")) + list(output_dir.glob("*.XPT"))
        non_lowercase: list[str] = []

        for xpt_file in xpt_files:
            if xpt_file.name != xpt_file.name.lower():
                non_lowercase.append(xpt_file.name)

        if non_lowercase:
            results.append(
                RuleResult(
                    rule_id="FDA-TRC-FILENAME",
                    rule_description="Dataset filenames must be lowercase",
                    category=RuleCategory.FDA_TRC,
                    severity=RuleSeverity.ERROR,
                    message=f"Non-lowercase filenames found: {non_lowercase}",
                    affected_count=len(non_lowercase),
                    fix_suggestion="Rename files to lowercase (e.g., DM.xpt -> dm.xpt)",
                )
            )

        return results


def get_fda_trc_rules() -> list[ValidationRule]:
    """Return an empty list -- TRC uses TRCPreCheck, not ValidationRule.

    TRCPreCheck is invoked directly for submission-level checks,
    not through the per-domain rule registry.
    """
    return []
