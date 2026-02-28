"""Cross-domain consistency validation rules (VAL-03).

These rules differ from single-domain rules: they need access to ALL
generated DataFrames, not just one. The CrossDomainValidator runs checks
across multiple domains simultaneously (e.g., all USUBJIDs must exist in DM).
"""

from __future__ import annotations

import pandas as pd
from loguru import logger

from astraea.models.mapping import DomainMappingSpec
from astraea.validation.rules.base import RuleCategory, RuleResult, RuleSeverity


class CrossDomainValidator:
    """Validates consistency across multiple SDTM domains.

    Unlike ValidationRule subclasses (which operate on a single domain),
    this validator sees all generated DataFrames together and checks
    cross-domain invariants like USUBJID consistency and STUDYID uniformity.
    """

    def validate(
        self,
        domains: dict[str, pd.DataFrame],
        specs: dict[str, DomainMappingSpec],
    ) -> list[RuleResult]:
        """Run all cross-domain consistency checks.

        Args:
            domains: Mapping of domain code to generated DataFrame.
            specs: Mapping of domain code to DomainMappingSpec.

        Returns:
            List of RuleResult findings from all cross-domain checks.
        """
        results: list[RuleResult] = []

        results.extend(self._check_usubjid_consistency(domains))
        results.extend(self._check_studyid_consistency(domains))
        results.extend(self._check_rfstdtc_consistency(domains))
        results.extend(self._check_domain_column_consistency(domains, specs))
        results.extend(self._check_studyday_consistency(domains))

        return results

    def _check_usubjid_consistency(self, domains: dict[str, pd.DataFrame]) -> list[RuleResult]:
        """ASTR-C001: All USUBJIDs in every domain must exist in DM.USUBJID.

        Severity: ERROR. P21 equivalent: SD0085.
        """
        results: list[RuleResult] = []

        if "DM" not in domains:
            results.append(
                RuleResult(
                    rule_id="ASTR-C001",
                    rule_description="Cross-domain USUBJID consistency",
                    category=RuleCategory.CONSISTENCY,
                    severity=RuleSeverity.ERROR,
                    message="DM domain not present -- cannot check USUBJID consistency",
                    fix_suggestion="Generate the DM domain before running cross-domain validation",
                )
            )
            return results

        dm_df = domains["DM"]
        if "USUBJID" not in dm_df.columns:
            results.append(
                RuleResult(
                    rule_id="ASTR-C001",
                    rule_description="Cross-domain USUBJID consistency",
                    category=RuleCategory.CONSISTENCY,
                    severity=RuleSeverity.ERROR,
                    domain="DM",
                    variable="USUBJID",
                    message="DM domain is missing USUBJID column",
                )
            )
            return results

        dm_usubjids = set(dm_df["USUBJID"].dropna().unique())

        for domain_code, df in domains.items():
            if domain_code == "DM":
                continue
            if "USUBJID" not in df.columns:
                continue

            domain_usubjids = set(df["USUBJID"].dropna().unique())
            orphans = domain_usubjids - dm_usubjids
            if orphans:
                results.append(
                    RuleResult(
                        rule_id="ASTR-C001",
                        rule_description="Cross-domain USUBJID consistency",
                        category=RuleCategory.CONSISTENCY,
                        severity=RuleSeverity.ERROR,
                        domain=domain_code,
                        variable="USUBJID",
                        message=(
                            f"{domain_code} has {len(orphans)} USUBJID(s) not in DM: "
                            f"{sorted(orphans)[:5]}"
                        ),
                        affected_count=len(orphans),
                        fix_suggestion="Ensure all subjects in this domain are also in DM",
                        p21_equivalent="SD0085",
                    )
                )
                logger.warning("ASTR-C001: {} has {} orphan USUBJIDs", domain_code, len(orphans))

        return results

    def _check_studyid_consistency(self, domains: dict[str, pd.DataFrame]) -> list[RuleResult]:
        """ASTR-C002: STUDYID must have exactly one unique value across all domains.

        Severity: ERROR.
        """
        results: list[RuleResult] = []
        all_studyids: set[str] = set()

        for _domain_code, df in domains.items():
            if "STUDYID" not in df.columns:
                continue
            domain_studyids = set(df["STUDYID"].dropna().unique())
            all_studyids.update(domain_studyids)

        if len(all_studyids) > 1:
            results.append(
                RuleResult(
                    rule_id="ASTR-C002",
                    rule_description="Cross-domain STUDYID consistency",
                    category=RuleCategory.CONSISTENCY,
                    severity=RuleSeverity.ERROR,
                    message=(
                        f"Multiple STUDYID values found across domains: {sorted(all_studyids)}"
                    ),
                    affected_count=len(all_studyids),
                    fix_suggestion="Ensure all domains use the same STUDYID value",
                )
            )
        elif len(all_studyids) == 0:
            results.append(
                RuleResult(
                    rule_id="ASTR-C002",
                    rule_description="Cross-domain STUDYID consistency",
                    category=RuleCategory.CONSISTENCY,
                    severity=RuleSeverity.ERROR,
                    message="No STUDYID values found in any domain",
                    fix_suggestion="Ensure STUDYID is populated in all domains",
                )
            )

        return results

    def _check_rfstdtc_consistency(self, domains: dict[str, pd.DataFrame]) -> list[RuleResult]:
        """ASTR-C003: RFSTDTC should equal earliest EXSTDTC per subject.

        If DM has RFSTDTC and EX has EXSTDTC, verify consistency.
        Severity: WARNING (may have legitimate explanations).
        """
        results: list[RuleResult] = []

        if "DM" not in domains:
            return results
        dm_df = domains["DM"]
        if "RFSTDTC" not in dm_df.columns or "USUBJID" not in dm_df.columns:
            return results

        # Build USUBJID -> RFSTDTC lookup
        rfstdtc_map: dict[str, str] = {}
        for _, row in dm_df.iterrows():
            usubjid = row.get("USUBJID")
            rfstdtc = row.get("RFSTDTC")
            if pd.notna(usubjid) and pd.notna(rfstdtc) and str(rfstdtc).strip():
                rfstdtc_map[str(usubjid)] = str(rfstdtc)

        if not rfstdtc_map:
            return results

        # Check EX domain if present
        if "EX" in domains:
            ex_df = domains["EX"]
            if "EXSTDTC" in ex_df.columns and "USUBJID" in ex_df.columns:
                mismatches = 0
                for usubjid, rfstdtc in rfstdtc_map.items():
                    subj_ex = ex_df[ex_df["USUBJID"] == usubjid]
                    if subj_ex.empty:
                        continue
                    ex_dates = subj_ex["EXSTDTC"].dropna().astype(str)
                    ex_dates_sorted = sorted(
                        [d for d in ex_dates if d.strip()],
                    )
                    if ex_dates_sorted and ex_dates_sorted[0] != rfstdtc:
                        mismatches += 1

                if mismatches > 0:
                    results.append(
                        RuleResult(
                            rule_id="ASTR-C003",
                            rule_description="RFSTDTC vs earliest EXSTDTC consistency",
                            category=RuleCategory.CONSISTENCY,
                            severity=RuleSeverity.WARNING,
                            domain="DM",
                            variable="RFSTDTC",
                            message=(
                                f"{mismatches} subject(s) have RFSTDTC that does not "
                                f"match their earliest EXSTDTC"
                            ),
                            affected_count=mismatches,
                            fix_suggestion=(
                                "Verify RFSTDTC is set to the earliest exposure date "
                                "for each subject"
                            ),
                        )
                    )

        return results

    def _check_domain_column_consistency(
        self,
        domains: dict[str, pd.DataFrame],
        specs: dict[str, DomainMappingSpec],
    ) -> list[RuleResult]:
        """ASTR-C004: Each domain's DOMAIN column must contain only its domain code.

        Severity: ERROR.
        """
        results: list[RuleResult] = []

        for domain_code, df in domains.items():
            if "DOMAIN" not in df.columns:
                continue
            domain_values = set(df["DOMAIN"].dropna().unique())
            unexpected = domain_values - {domain_code}
            if unexpected:
                results.append(
                    RuleResult(
                        rule_id="ASTR-C004",
                        rule_description="DOMAIN column value consistency",
                        category=RuleCategory.CONSISTENCY,
                        severity=RuleSeverity.ERROR,
                        domain=domain_code,
                        variable="DOMAIN",
                        message=(
                            f"{domain_code} DOMAIN column contains unexpected values: "
                            f"{sorted(unexpected)}"
                        ),
                        affected_count=sum(1 for v in df["DOMAIN"].dropna() if v != domain_code),
                        fix_suggestion=f"Set all DOMAIN values to '{domain_code}'",
                    )
                )

        return results

    def _check_studyday_consistency(self, domains: dict[str, pd.DataFrame]) -> list[RuleResult]:
        """ASTR-C005: Study day signs must be consistent with RFSTDTC.

        If --DY columns exist, positive values should be on/after RFSTDTC,
        negative values should be before RFSTDTC. Severity: WARNING.
        """
        results: list[RuleResult] = []

        if "DM" not in domains:
            return results
        dm_df = domains["DM"]
        if "RFSTDTC" not in dm_df.columns or "USUBJID" not in dm_df.columns:
            return results

        # Build USUBJID -> RFSTDTC lookup
        rfstdtc_map: dict[str, str] = {}
        for _, row in dm_df.iterrows():
            usubjid = row.get("USUBJID")
            rfstdtc = row.get("RFSTDTC")
            if pd.notna(usubjid) and pd.notna(rfstdtc) and str(rfstdtc).strip():
                rfstdtc_map[str(usubjid)] = str(rfstdtc)[:10]  # date part only

        if not rfstdtc_map:
            return results

        for domain_code, df in domains.items():
            if domain_code == "DM":
                continue
            if "USUBJID" not in df.columns:
                continue

            # Find --DY columns and their corresponding --DTC columns
            dy_cols = [c for c in df.columns if c.endswith("DY")]
            for dy_col in dy_cols:
                # Corresponding DTC column: replace DY suffix with DTC
                dtc_col = dy_col[:-2] + "DTC"
                if dtc_col not in df.columns:
                    continue

                inconsistent_count = 0
                for _, row in df.iterrows():
                    usubjid = row.get("USUBJID")
                    dy_val = row.get(dy_col)
                    dtc_val = row.get(dtc_col)

                    if pd.isna(dy_val) or pd.isna(dtc_val) or pd.isna(usubjid):
                        continue
                    if str(usubjid) not in rfstdtc_map:
                        continue

                    rfstdtc = rfstdtc_map[str(usubjid)]
                    dtc_date = str(dtc_val)[:10]

                    try:
                        dy_num = int(float(dy_val))
                    except (ValueError, TypeError):
                        continue

                    # Positive DY should be on/after RFSTDTC;
                    # Negative DY should be before RFSTDTC
                    if (dy_num > 0 and dtc_date < rfstdtc) or (dy_num < 0 and dtc_date > rfstdtc):
                        inconsistent_count += 1

                if inconsistent_count > 0:
                    results.append(
                        RuleResult(
                            rule_id="ASTR-C005",
                            rule_description="Study day sign consistency with RFSTDTC",
                            category=RuleCategory.CONSISTENCY,
                            severity=RuleSeverity.WARNING,
                            domain=domain_code,
                            variable=dy_col,
                            message=(
                                f"{domain_code}.{dy_col} has {inconsistent_count} "
                                f"record(s) where study day sign is inconsistent "
                                f"with the date relative to RFSTDTC"
                            ),
                            affected_count=inconsistent_count,
                            fix_suggestion=(
                                "Verify study day calculation: positive DY for "
                                "dates on/after RFSTDTC, negative for dates before"
                            ),
                        )
                    )

        return results


def get_consistency_rules() -> list:
    """Return an empty list -- consistency rules use CrossDomainValidator, not ValidationRule.

    The CrossDomainValidator is invoked directly by ValidationEngine.validate_cross_domain(),
    not through the per-domain rule registry.
    """
    return []
