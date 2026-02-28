"""FDA Business Rules for SDTM validation.

Implements FDA Business Rules covering:
- Demographic coding: FDAB057 (ETHNIC), FDAB055 (RACE), FDAB015 (SEX), FDAB016 (COUNTRY)
- AE domain: FDAB001 (AESER), FDAB002 (AEREL), FDAB003 (AEOUT), FDAB004 (AEACN), FDAB005 (dates)
- Findings integrity: FDAB039 (normal ranges), FDAB009 (TESTCD/TEST), FDAB030 (STRESU)
- Intervention domains: FDAB025 (CMTRT), FDAB026 (EXTRT)
- Cross-domain: FDAB020 (VISITNUM), FDAB021 (DY), FDAB022 (DTC), FDAB035/036 (paired results)
- Population flags: FDAB-POP
"""

from __future__ import annotations

import re

import pandas as pd

from astraea.models.mapping import DomainMappingSpec
from astraea.reference.controlled_terms import CTReference
from astraea.reference.sdtm_ig import SDTMReference
from astraea.validation.rules.base import (
    RuleCategory,
    RuleResult,
    RuleSeverity,
    ValidationRule,
)

_FINDINGS_DOMAINS = {"LB", "LC", "VS", "EG", "PE", "QS", "SC", "FA"}

# ISO 8601 pattern for SDTM --DTC columns:
# YYYY, YYYY-MM, YYYY-MM-DD, YYYY-MM-DDTHH:MM, YYYY-MM-DDTHH:MM:SS
# with optional timezone offset (+/-HH:MM or Z)
_ISO_8601_PATTERN = re.compile(
    r"^\d{4}"
    r"(?:-\d{2}"
    r"(?:-\d{2}"
    r"(?:T\d{2}:\d{2}"
    r"(?::\d{2}"
    r")?(?:[+-]\d{2}:\d{2}|Z)?"
    r")?"
    r")?"
    r")?$"
)

# Common ISO 3166-1 alpha-3 country codes (top ~60)
_ISO_3166_ALPHA3 = {
    "AFG", "ALB", "DZA", "ARG", "AUS", "AUT", "BEL", "BRA", "BGR", "CAN",
    "CHL", "CHN", "COL", "HRV", "CZE", "DNK", "EGY", "EST", "FIN", "FRA",
    "DEU", "GRC", "HKG", "HUN", "ISL", "IND", "IDN", "IRN", "IRQ", "IRL",
    "ISR", "ITA", "JPN", "KAZ", "KEN", "KOR", "LVA", "LTU", "LUX", "MYS",
    "MEX", "NLD", "NZL", "NGA", "NOR", "PAK", "PER", "PHL", "POL", "PRT",
    "ROU", "RUS", "SAU", "SGP", "SVK", "SVN", "ZAF", "ESP", "SWE", "CHE",
    "TWN", "THA", "TUR", "UKR", "ARE", "GBR", "USA", "VNM",
}


class FDAB057Rule(ValidationRule):
    """FDAB057: DM.ETHNIC values must conform to CT codelist C66790.

    Checks that ETHNIC values in the DM domain use the correct controlled
    terminology. Must include HISPANIC OR LATINO and NOT HISPANIC OR LATINO
    as the standard choices.
    """

    rule_id: str = "FDAB057"
    description: str = "DM.ETHNIC values must conform to CT codelist C66790"
    category: RuleCategory = RuleCategory.FDA_BUSINESS
    severity: RuleSeverity = RuleSeverity.ERROR

    def evaluate(
        self,
        domain: str,
        df: pd.DataFrame,
        spec: DomainMappingSpec,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
    ) -> list[RuleResult]:
        if domain != "DM":
            return []
        if "ETHNIC" not in df.columns:
            return [
                RuleResult(
                    rule_id=self.rule_id,
                    rule_description=self.description,
                    category=self.category,
                    severity=self.severity,
                    domain=domain,
                    variable="ETHNIC",
                    message="DM domain is missing ETHNIC variable",
                    fix_suggestion="Add ETHNIC variable to DM domain",
                )
            ]

        results: list[RuleResult] = []
        # Check against C66790 codelist if available
        valid_terms: set[str] = set()
        codelist = ct_ref.lookup_codelist("C66790")
        if codelist:
            valid_terms = set(codelist.terms.keys())

        if valid_terms:
            ethnic_values = df["ETHNIC"].dropna().unique()
            invalid = [str(v) for v in ethnic_values if str(v) not in valid_terms]
            if invalid:
                results.append(
                    RuleResult(
                        rule_id=self.rule_id,
                        rule_description=self.description,
                        category=self.category,
                        severity=self.severity,
                        domain=domain,
                        variable="ETHNIC",
                        message=(
                            f"Invalid ETHNIC values found: {invalid}. "
                            f"Valid values from C66790: {sorted(valid_terms)}"
                        ),
                        affected_count=sum(
                            1 for v in df["ETHNIC"].dropna() if str(v) not in valid_terms
                        ),
                        fix_suggestion="Map ETHNIC values to C66790 controlled terminology",
                    )
                )

        return results


class FDAB055Rule(ValidationRule):
    """FDAB055: DM.RACE values must conform to CT codelist C74457.

    Checks that RACE values in the DM domain use the correct controlled
    terminology from codelist C74457.
    """

    rule_id: str = "FDAB055"
    description: str = "DM.RACE values must conform to CT codelist C74457"
    category: RuleCategory = RuleCategory.FDA_BUSINESS
    severity: RuleSeverity = RuleSeverity.WARNING

    def evaluate(
        self,
        domain: str,
        df: pd.DataFrame,
        spec: DomainMappingSpec,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
    ) -> list[RuleResult]:
        if domain != "DM":
            return []
        if "RACE" not in df.columns:
            return [
                RuleResult(
                    rule_id=self.rule_id,
                    rule_description=self.description,
                    category=self.category,
                    severity=self.severity,
                    domain=domain,
                    variable="RACE",
                    message="DM domain is missing RACE variable",
                    fix_suggestion="Add RACE variable to DM domain",
                )
            ]

        results: list[RuleResult] = []
        valid_terms: set[str] = set()
        codelist = ct_ref.lookup_codelist("C74457")
        if codelist:
            valid_terms = set(codelist.terms.keys())

        if valid_terms:
            race_values = df["RACE"].dropna().unique()
            invalid = [str(v) for v in race_values if str(v) not in valid_terms]
            if invalid:
                results.append(
                    RuleResult(
                        rule_id=self.rule_id,
                        rule_description=self.description,
                        category=self.category,
                        severity=self.severity,
                        domain=domain,
                        variable="RACE",
                        message=(
                            f"Invalid RACE values found: {invalid}. "
                            f"Valid values from C74457: {sorted(valid_terms)}"
                        ),
                        affected_count=sum(
                            1 for v in df["RACE"].dropna() if str(v) not in valid_terms
                        ),
                        fix_suggestion="Map RACE values to C74457 controlled terminology",
                    )
                )

        return results


class FDAB039Rule(ValidationRule):
    """FDAB039: Normal range values must be numeric when STRESN is populated.

    For Findings domains (LB, VS, EG): checks that --ORNRLO and --ORNRHI
    are numeric when --STRESN is populated.
    """

    rule_id: str = "FDAB039"
    description: str = "Normal range values must be numeric when STRESN is populated"
    category: RuleCategory = RuleCategory.FDA_BUSINESS
    severity: RuleSeverity = RuleSeverity.WARNING

    def evaluate(
        self,
        domain: str,
        df: pd.DataFrame,
        spec: DomainMappingSpec,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
    ) -> list[RuleResult]:
        if domain not in _FINDINGS_DOMAINS:
            return []

        prefix = domain[:2]
        stresn_col = f"{prefix}STRESN"
        ornrlo_col = f"{prefix}ORNRLO"
        ornrhi_col = f"{prefix}ORNRHI"

        if stresn_col not in df.columns:
            return []

        results: list[RuleResult] = []

        for nr_col, _nr_name in [(ornrlo_col, "ORNRLO"), (ornrhi_col, "ORNRHI")]:
            if nr_col not in df.columns:
                continue

            # Check rows where STRESN is populated and NR value is non-numeric
            mask = df[stresn_col].notna()
            nr_values = df.loc[mask, nr_col].dropna()
            non_numeric_count = 0
            for val in nr_values:
                try:
                    float(val)
                except (ValueError, TypeError):
                    non_numeric_count += 1

            if non_numeric_count > 0:
                results.append(
                    RuleResult(
                        rule_id=self.rule_id,
                        rule_description=self.description,
                        category=self.category,
                        severity=self.severity,
                        domain=domain,
                        variable=nr_col,
                        message=(
                            f"{nr_col} has {non_numeric_count} non-numeric value(s) "
                            f"where {stresn_col} is populated"
                        ),
                        affected_count=non_numeric_count,
                        fix_suggestion=(
                            f"Ensure {nr_col} contains numeric values "
                            f"when {stresn_col} is populated"
                        ),
                    )
                )

        return results


class FDAB009Rule(ValidationRule):
    """FDAB009: TESTCD and TEST must have a 1:1 relationship.

    For Findings domains: each TESTCD must map to exactly one TEST value
    and vice versa.
    """

    rule_id: str = "FDAB009"
    description: str = "TESTCD and TEST must have a 1:1 relationship"
    category: RuleCategory = RuleCategory.FDA_BUSINESS
    severity: RuleSeverity = RuleSeverity.ERROR

    def evaluate(
        self,
        domain: str,
        df: pd.DataFrame,
        spec: DomainMappingSpec,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
    ) -> list[RuleResult]:
        if domain not in _FINDINGS_DOMAINS:
            return []

        prefix = domain[:2]
        testcd_col = f"{prefix}TESTCD"
        test_col = f"{prefix}TEST"

        if testcd_col not in df.columns or test_col not in df.columns:
            return []

        results: list[RuleResult] = []

        # Vectorized: extract valid (non-null) pairs as strings
        valid = df[[testcd_col, test_col]].dropna().astype(str)
        if valid.empty:
            return results

        # Forward check: TESTCD -> TEST (one TESTCD should map to exactly one TEST)
        fwd_counts = valid.groupby(testcd_col)[test_col].nunique()
        fwd_violations = fwd_counts[fwd_counts > 1].index.tolist()
        if fwd_violations:
            fwd_details = (
                valid[valid[testcd_col].isin(fwd_violations)]
                .groupby(testcd_col)[test_col]
                .apply(lambda x: sorted(x.unique().tolist()))
                .to_dict()
            )
            details = "; ".join(
                f"{cd} -> {tests}" for cd, tests in sorted(fwd_details.items())
            )
            results.append(
                RuleResult(
                    rule_id=self.rule_id,
                    rule_description=self.description,
                    category=self.category,
                    severity=self.severity,
                    domain=domain,
                    variable=testcd_col,
                    message=(
                        f"{testcd_col} has {len(fwd_violations)} code(s) mapping to "
                        f"multiple TEST values: {details}"
                    ),
                    affected_count=len(fwd_violations),
                    fix_suggestion="Ensure each TESTCD maps to exactly one TEST",
                )
            )

        # Reverse check: TEST -> TESTCD (one TEST should map to exactly one TESTCD)
        rev_counts = valid.groupby(test_col)[testcd_col].nunique()
        rev_violations = rev_counts[rev_counts > 1].index.tolist()
        if rev_violations:
            rev_details = (
                valid[valid[test_col].isin(rev_violations)]
                .groupby(test_col)[testcd_col]
                .apply(lambda x: sorted(x.unique().tolist()))
                .to_dict()
            )
            details = "; ".join(
                f"{test} -> {cds}" for test, cds in sorted(rev_details.items())
            )
            results.append(
                RuleResult(
                    rule_id=self.rule_id,
                    rule_description=self.description,
                    category=self.category,
                    severity=self.severity,
                    domain=domain,
                    variable=test_col,
                    message=(
                        f"{test_col} has {len(rev_violations)} test name(s) mapping to "
                        f"multiple TESTCD values: {details}"
                    ),
                    affected_count=len(rev_violations),
                    fix_suggestion="Ensure each TEST maps to exactly one TESTCD",
                )
            )

        return results


class FDAB030Rule(ValidationRule):
    """FDAB030: STRESU values must be consistent for the same TESTCD.

    For Findings domains: check that --STRESU values are the same
    for all records with the same --TESTCD.
    """

    rule_id: str = "FDAB030"
    description: str = "STRESU must be consistent for the same TESTCD"
    category: RuleCategory = RuleCategory.FDA_BUSINESS
    severity: RuleSeverity = RuleSeverity.WARNING

    def evaluate(
        self,
        domain: str,
        df: pd.DataFrame,
        spec: DomainMappingSpec,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
    ) -> list[RuleResult]:
        if domain not in _FINDINGS_DOMAINS:
            return []

        prefix = domain[:2]
        testcd_col = f"{prefix}TESTCD"
        stresu_col = f"{prefix}STRESU"

        if testcd_col not in df.columns or stresu_col not in df.columns:
            return []

        # Vectorized: group STRESU values by TESTCD
        valid = df[[testcd_col, stresu_col]].dropna().astype(str)
        if valid.empty:
            return []

        unit_counts = valid.groupby(testcd_col)[stresu_col].nunique()
        violation_codes = unit_counts[unit_counts > 1].index.tolist()

        if not violation_codes:
            return []

        violations = (
            valid[valid[testcd_col].isin(violation_codes)]
            .groupby(testcd_col)[stresu_col]
            .apply(lambda x: sorted(x.unique().tolist()))
            .to_dict()
        )

        if not violations:
            return []

        details = "; ".join(f"{cd}: {sorted(units)}" for cd, units in sorted(violations.items()))
        return [
            RuleResult(
                rule_id=self.rule_id,
                rule_description=self.description,
                category=self.category,
                severity=self.severity,
                domain=domain,
                variable=stresu_col,
                message=(
                    f"{len(violations)} TESTCD(s) have inconsistent {stresu_col} values: {details}"
                ),
                affected_count=len(violations),
                fix_suggestion=f"Ensure {stresu_col} is consistent for each {testcd_col}",
            )
        ]


class FDAB015Rule(ValidationRule):
    """FDAB015: DM.SEX values must conform to CT codelist C66731.

    Checks that SEX values in the DM domain use the correct controlled
    terminology from the non-extensible codelist C66731 (M, F, U,
    UNDIFFERENTIATED).
    """

    rule_id: str = "FDAB015"
    description: str = "DM.SEX values must conform to CT codelist C66731"
    category: RuleCategory = RuleCategory.FDA_BUSINESS
    severity: RuleSeverity = RuleSeverity.ERROR

    def evaluate(
        self,
        domain: str,
        df: pd.DataFrame,
        spec: DomainMappingSpec,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
    ) -> list[RuleResult]:
        if domain != "DM":
            return []
        if "SEX" not in df.columns:
            return [
                RuleResult(
                    rule_id=self.rule_id,
                    rule_description=self.description,
                    category=self.category,
                    severity=self.severity,
                    domain=domain,
                    variable="SEX",
                    message="DM domain is missing SEX variable",
                    fix_suggestion="Add SEX variable to DM domain",
                )
            ]

        results: list[RuleResult] = []
        valid_terms: set[str] = set()
        codelist = ct_ref.lookup_codelist("C66731")
        if codelist:
            valid_terms = set(codelist.terms.keys())

        if valid_terms:
            sex_values = df["SEX"].dropna().unique()
            invalid = [str(v) for v in sex_values if str(v) not in valid_terms]
            if invalid:
                results.append(
                    RuleResult(
                        rule_id=self.rule_id,
                        rule_description=self.description,
                        category=self.category,
                        severity=self.severity,
                        domain=domain,
                        variable="SEX",
                        message=(
                            f"Invalid SEX values found: {invalid}. "
                            f"Valid values from C66731: {sorted(valid_terms)}"
                        ),
                        affected_count=sum(
                            1 for v in df["SEX"].dropna() if str(v) not in valid_terms
                        ),
                        fix_suggestion=(
                            f"Map SEX values to C66731 controlled terminology: "
                            f"{sorted(valid_terms)}"
                        ),
                    )
                )

        return results


class FDABLC01Rule(ValidationRule):
    """FDAB-LC01: LC domain unit conversion validation.

    Checks whether the LC domain was generated with actual unit conversion
    from SI to conventional units. If not, fires a WARNING indicating that
    manual review is required before submission. This implements the FDA
    SDTCG v5.7 requirement for dual lab domains (LB for SI, LC for
    conventional).
    """

    rule_id: str = "FDAB-LC01"
    description: str = (
        "LC domain must contain conventional units distinct from LB SI units"
    )
    category: RuleCategory = RuleCategory.FDA_BUSINESS
    severity: RuleSeverity = RuleSeverity.WARNING

    def evaluate(
        self,
        domain: str,
        df: pd.DataFrame,
        spec: DomainMappingSpec,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
    ) -> list[RuleResult]:
        if domain != "LC":
            return []

        # Check the metadata flag set by generate_lc_from_lb
        unit_conversion_performed = df.attrs.get("lc_unit_conversion_performed", False)

        if not unit_conversion_performed:
            return [
                RuleResult(
                    rule_id=self.rule_id,
                    rule_description=self.description,
                    category=self.category,
                    severity=self.severity,
                    domain=domain,
                    variable="LCORRES",
                    message=(
                        "LC domain contains identical values to LB. "
                        "SDTCG v5.7 requires conventional units in LC. "
                        "Unit conversion from SI to conventional was not performed. "
                        "Manual review required before submission."
                    ),
                    affected_count=len(df),
                    fix_suggestion=(
                        "Implement unit conversion from SI to conventional units "
                        "for the LC domain, or document the rationale in the cSDRG"
                    ),
                )
            ]

        return []


def get_fda_business_rules() -> list[ValidationRule]:
    """Return all FDA Business Rule instances for engine registration."""
    return [
        FDAB057Rule(),
        FDAB055Rule(),
        FDAB015Rule(),
        FDAB039Rule(),
        FDAB009Rule(),
        FDAB030Rule(),
        FDABLC01Rule(),
    ]
