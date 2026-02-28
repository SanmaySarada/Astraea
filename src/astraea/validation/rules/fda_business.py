"""FDA Business Rules for SDTM validation.

Implements FDA Business Rules FDAB057, FDAB055, FDAB039, FDAB009, FDAB030
as ValidationRule subclasses. These check demographic coding compliance
and Findings domain data integrity requirements.
"""

from __future__ import annotations

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

_FINDINGS_DOMAINS = {"LB", "VS", "EG", "PE", "QS", "SC", "FA"}


class FDAB057Rule(ValidationRule):
    """FDAB057: DM.ETHNIC values must conform to CT codelist C66790.

    Checks that ETHNIC values in the DM domain use the correct controlled
    terminology. Must include HISPANIC OR LATINO and NOT HISPANIC OR LATINO
    as the standard choices.
    """

    rule_id: str = "FDAB057"
    description: str = "DM.ETHNIC values must conform to CT codelist C66790"
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

        # Check TESTCD -> TEST (one TESTCD should map to exactly one TEST)
        testcd_to_test: dict[str, set[str]] = {}
        for _, row in df.iterrows():
            cd = row.get(testcd_col)
            test = row.get(test_col)
            if pd.notna(cd) and pd.notna(test):
                cd_str = str(cd)
                testcd_to_test.setdefault(cd_str, set()).add(str(test))

        violations_cd = {cd: tests for cd, tests in testcd_to_test.items() if len(tests) > 1}
        if violations_cd:
            details = "; ".join(
                f"{cd} -> {sorted(tests)}" for cd, tests in sorted(violations_cd.items())
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
                        f"{testcd_col} has {len(violations_cd)} code(s) mapping to "
                        f"multiple TEST values: {details}"
                    ),
                    affected_count=len(violations_cd),
                    fix_suggestion="Ensure each TESTCD maps to exactly one TEST",
                )
            )

        # Check TEST -> TESTCD (one TEST should map to exactly one TESTCD)
        test_to_testcd: dict[str, set[str]] = {}
        for _, row in df.iterrows():
            cd = row.get(testcd_col)
            test = row.get(test_col)
            if pd.notna(cd) and pd.notna(test):
                test_str = str(test)
                test_to_testcd.setdefault(test_str, set()).add(str(cd))

        violations_test = {test: cds for test, cds in test_to_testcd.items() if len(cds) > 1}
        if violations_test:
            details = "; ".join(
                f"{test} -> {sorted(cds)}" for test, cds in sorted(violations_test.items())
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
                        f"{test_col} has {len(violations_test)} test name(s) mapping to "
                        f"multiple TESTCD values: {details}"
                    ),
                    affected_count=len(violations_test),
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

        # Group STRESU values by TESTCD
        testcd_units: dict[str, set[str]] = {}
        for _, row in df.iterrows():
            cd = row.get(testcd_col)
            unit = row.get(stresu_col)
            if pd.notna(cd) and pd.notna(unit):
                testcd_units.setdefault(str(cd), set()).add(str(unit))

        violations = {cd: units for cd, units in testcd_units.items() if len(units) > 1}

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


def get_fda_business_rules() -> list[ValidationRule]:
    """Return all FDA Business Rule instances for engine registration."""
    return [
        FDAB057Rule(),
        FDAB055Rule(),
        FDAB039Rule(),
        FDAB009Rule(),
        FDAB030Rule(),
    ]
