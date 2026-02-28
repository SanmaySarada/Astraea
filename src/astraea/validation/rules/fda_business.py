"""FDA Business Rules for SDTM validation.

Implements FDA Business Rules covering:
- Demographic coding: FDAB057 (ETHNIC), FDAB055 (RACE), FDAB015 (SEX), FDAB016 (COUNTRY)
- AE domain: FDAB001 (AESER), FDAB002 (AEREL), FDAB003 (AEOUT), FDAB004 (AEACN), FDAB005 (dates)
- Findings integrity: FDAB039 (normal ranges), FDAB009 (TESTCD/TEST), FDAB030 (STRESU)
- Intervention domains: FDAB025 (CMTRT), FDAB026 (EXTRT)
- Cross-domain: FDAB020 (VISITNUM), FDAB021 (DY), FDAB022 (DTC), FDAB035/036 (paired results)
- Population flags: FDAB-POP
- LC domain: FDAB-LC01 (unit conversion)
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

# ISO 8601 pattern for SDTM --DTC columns
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
    "AFG",
    "ALB",
    "DZA",
    "ARG",
    "AUS",
    "AUT",
    "BEL",
    "BRA",
    "BGR",
    "CAN",
    "CHL",
    "CHN",
    "COL",
    "HRV",
    "CZE",
    "DNK",
    "EGY",
    "EST",
    "FIN",
    "FRA",
    "DEU",
    "GRC",
    "HKG",
    "HUN",
    "ISL",
    "IND",
    "IDN",
    "IRN",
    "IRQ",
    "IRL",
    "ISR",
    "ITA",
    "JPN",
    "KAZ",
    "KEN",
    "KOR",
    "LVA",
    "LTU",
    "LUX",
    "MYS",
    "MEX",
    "NLD",
    "NZL",
    "NGA",
    "NOR",
    "PAK",
    "PER",
    "PHL",
    "POL",
    "PRT",
    "ROU",
    "RUS",
    "SAU",
    "SGP",
    "SVK",
    "SVN",
    "ZAF",
    "ESP",
    "SWE",
    "CHE",
    "TWN",
    "THA",
    "TUR",
    "UKR",
    "ARE",
    "GBR",
    "USA",
    "VNM",
}


# ---------------------------------------------------------------------------
# Original rules
# ---------------------------------------------------------------------------


class FDAB057Rule(ValidationRule):
    """FDAB057: DM.ETHNIC values must conform to CT codelist C66790."""

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
    """FDAB055: DM.RACE values must conform to CT codelist C74457."""

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
    """FDAB039: Normal range values must be numeric when STRESN is populated."""

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
                            f"{nr_col} has {non_numeric_count} non-numeric "
                            f"value(s) where {stresn_col} is populated"
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
    """FDAB009: TESTCD and TEST must have a 1:1 relationship."""

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
        valid = df[[testcd_col, test_col]].dropna().astype(str)
        if valid.empty:
            return results
        fwd_counts = valid.groupby(testcd_col)[test_col].nunique()
        fwd_violations = fwd_counts[fwd_counts > 1].index.tolist()
        if fwd_violations:
            fwd_details = (
                valid[valid[testcd_col].isin(fwd_violations)]
                .groupby(testcd_col)[test_col]
                .apply(lambda x: sorted(x.unique().tolist()))
                .to_dict()
            )
            details = "; ".join(f"{cd} -> {tests}" for cd, tests in sorted(fwd_details.items()))
            results.append(
                RuleResult(
                    rule_id=self.rule_id,
                    rule_description=self.description,
                    category=self.category,
                    severity=self.severity,
                    domain=domain,
                    variable=testcd_col,
                    message=(
                        f"{testcd_col} has {len(fwd_violations)} code(s) "
                        f"mapping to multiple TEST values: {details}"
                    ),
                    affected_count=len(fwd_violations),
                    fix_suggestion="Ensure each TESTCD maps to exactly one TEST",
                )
            )
        rev_counts = valid.groupby(test_col)[testcd_col].nunique()
        rev_violations = rev_counts[rev_counts > 1].index.tolist()
        if rev_violations:
            rev_details = (
                valid[valid[test_col].isin(rev_violations)]
                .groupby(test_col)[testcd_col]
                .apply(lambda x: sorted(x.unique().tolist()))
                .to_dict()
            )
            details = "; ".join(f"{test} -> {cds}" for test, cds in sorted(rev_details.items()))
            results.append(
                RuleResult(
                    rule_id=self.rule_id,
                    rule_description=self.description,
                    category=self.category,
                    severity=self.severity,
                    domain=domain,
                    variable=test_col,
                    message=(
                        f"{test_col} has {len(rev_violations)} test name(s) "
                        f"mapping to multiple TESTCD values: {details}"
                    ),
                    affected_count=len(rev_violations),
                    fix_suggestion="Ensure each TEST maps to exactly one TESTCD",
                )
            )
        return results


class FDAB030Rule(ValidationRule):
    """FDAB030: STRESU values must be consistent for the same TESTCD."""

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
                    f"{len(violations)} TESTCD(s) have inconsistent "
                    f"{stresu_col} values: {details}"
                ),
                affected_count=len(violations),
                fix_suggestion=f"Ensure {stresu_col} is consistent for each {testcd_col}",
            )
        ]


class FDAB015Rule(ValidationRule):
    """FDAB015: DM.SEX values must conform to CT codelist C66731."""

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
                            f"Map SEX values to C66731 controlled "
                            f"terminology: {sorted(valid_terms)}"
                        ),
                    )
                )
        return results


class FDABLC01Rule(ValidationRule):
    """FDAB-LC01: LC domain unit conversion validation."""

    rule_id: str = "FDAB-LC01"
    description: str = "LC domain must contain conventional units distinct from LB SI units"
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


# ---------------------------------------------------------------------------
# New AE domain rules (FDAB001-005)
# ---------------------------------------------------------------------------


class FDAB001Rule(ValidationRule):
    """FDAB001: AE.AESER must be Y or N."""

    rule_id: str = "FDAB001"
    description: str = "AE.AESER values must be Y or N"
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
        if domain != "AE":
            return []
        if "AESER" not in df.columns:
            return []
        valid_values = {"Y", "N"}
        ae_ser = df["AESER"].dropna()
        invalid = [str(v) for v in ae_ser.unique() if str(v) not in valid_values]
        if not invalid:
            return []
        return [
            RuleResult(
                rule_id=self.rule_id,
                rule_description=self.description,
                category=self.category,
                severity=self.severity,
                domain=domain,
                variable="AESER",
                message=f"Invalid AESER values found: {invalid}. Must be Y or N",
                affected_count=sum(1 for v in ae_ser if str(v) not in valid_values),
                fix_suggestion="Map AESER to Y or N",
            )
        ]


class FDAB002Rule(ValidationRule):
    """FDAB002: AE.AEREL must use controlled terminology for causality."""

    rule_id: str = "FDAB002"
    description: str = "AE.AEREL values must use causality CT"
    category: RuleCategory = RuleCategory.FDA_BUSINESS
    severity: RuleSeverity = RuleSeverity.ERROR

    _VALID_AEREL = {
        "RELATED",
        "NOT RELATED",
        "POSSIBLY RELATED",
        "PROBABLY RELATED",
        "UNLIKELY RELATED",
    }

    def evaluate(
        self,
        domain: str,
        df: pd.DataFrame,
        spec: DomainMappingSpec,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
    ) -> list[RuleResult]:
        if domain != "AE":
            return []
        if "AEREL" not in df.columns:
            return []
        ae_rel = df["AEREL"].dropna()
        invalid = [str(v) for v in ae_rel.unique() if str(v) not in self._VALID_AEREL]
        if not invalid:
            return []
        return [
            RuleResult(
                rule_id=self.rule_id,
                rule_description=self.description,
                category=self.category,
                severity=self.severity,
                domain=domain,
                variable="AEREL",
                message=(
                    f"Invalid AEREL values found: {invalid}. "
                    f"Valid values: {sorted(self._VALID_AEREL)}"
                ),
                affected_count=sum(1 for v in ae_rel if str(v) not in self._VALID_AEREL),
                fix_suggestion="Map AEREL to standard causality CT values",
            )
        ]


class FDAB003Rule(ValidationRule):
    """FDAB003: AE.AEOUT must use CT C101854 for outcome."""

    rule_id: str = "FDAB003"
    description: str = "AE.AEOUT values must use CT C101854"
    category: RuleCategory = RuleCategory.FDA_BUSINESS
    severity: RuleSeverity = RuleSeverity.ERROR

    _VALID_AEOUT = {
        "RECOVERED/RESOLVED",
        "RECOVERING/RESOLVING",
        "NOT RECOVERED/NOT RESOLVED",
        "RECOVERED/RESOLVED WITH SEQUELAE",
        "FATAL",
        "UNKNOWN",
    }

    def evaluate(
        self,
        domain: str,
        df: pd.DataFrame,
        spec: DomainMappingSpec,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
    ) -> list[RuleResult]:
        if domain != "AE":
            return []
        if "AEOUT" not in df.columns:
            return []
        ae_out = df["AEOUT"].dropna()
        invalid = [str(v) for v in ae_out.unique() if str(v) not in self._VALID_AEOUT]
        if not invalid:
            return []
        return [
            RuleResult(
                rule_id=self.rule_id,
                rule_description=self.description,
                category=self.category,
                severity=self.severity,
                domain=domain,
                variable="AEOUT",
                message=(
                    f"Invalid AEOUT values found: {invalid}. "
                    f"Valid values: {sorted(self._VALID_AEOUT)}"
                ),
                affected_count=sum(1 for v in ae_out if str(v) not in self._VALID_AEOUT),
                fix_suggestion="Map AEOUT to CT C101854 values",
            )
        ]


class FDAB004Rule(ValidationRule):
    """FDAB004: AE.AEACN must use CT for action taken."""

    rule_id: str = "FDAB004"
    description: str = "AE.AEACN values must use action taken CT"
    category: RuleCategory = RuleCategory.FDA_BUSINESS
    severity: RuleSeverity = RuleSeverity.ERROR

    _VALID_AEACN = {
        "DRUG WITHDRAWN",
        "DOSE REDUCED",
        "DOSE INCREASED",
        "DOSE NOT CHANGED",
        "UNKNOWN",
        "NOT APPLICABLE",
    }

    def evaluate(
        self,
        domain: str,
        df: pd.DataFrame,
        spec: DomainMappingSpec,
        sdtm_ref: SDTMReference,
        ct_ref: CTReference,
    ) -> list[RuleResult]:
        if domain != "AE":
            return []
        if "AEACN" not in df.columns:
            return []
        ae_acn = df["AEACN"].dropna()
        invalid = [str(v) for v in ae_acn.unique() if str(v) not in self._VALID_AEACN]
        if not invalid:
            return []
        return [
            RuleResult(
                rule_id=self.rule_id,
                rule_description=self.description,
                category=self.category,
                severity=self.severity,
                domain=domain,
                variable="AEACN",
                message=(
                    f"Invalid AEACN values found: {invalid}. "
                    f"Valid values: {sorted(self._VALID_AEACN)}"
                ),
                affected_count=sum(1 for v in ae_acn if str(v) not in self._VALID_AEACN),
                fix_suggestion="Map AEACN to action taken CT values",
            )
        ]


class FDAB005Rule(ValidationRule):
    """FDAB005: AE start date must not be after AE end date. WARNING."""

    rule_id: str = "FDAB005"
    description: str = "AESTDTC must not be after AEENDTC"
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
        if domain != "AE":
            return []
        if "AESTDTC" not in df.columns or "AEENDTC" not in df.columns:
            return []
        # Only compare complete dates (at least YYYY-MM-DD = 10 chars)
        mask = (
            df["AESTDTC"].notna()
            & df["AEENDTC"].notna()
            & (df["AESTDTC"].astype(str).str.len() >= 10)
            & (df["AEENDTC"].astype(str).str.len() >= 10)
        )
        subset = df.loc[mask]
        if subset.empty:
            return []
        violations = subset[subset["AESTDTC"].astype(str) > subset["AEENDTC"].astype(str)]
        if violations.empty:
            return []
        return [
            RuleResult(
                rule_id=self.rule_id,
                rule_description=self.description,
                category=self.category,
                severity=self.severity,
                domain=domain,
                variable="AESTDTC",
                message=f"{len(violations)} record(s) have AESTDTC after AEENDTC",
                affected_count=len(violations),
                fix_suggestion="Verify AE start and end dates are correctly mapped",
            )
        ]


# ---------------------------------------------------------------------------
# DM domain rule (FDAB016)
# ---------------------------------------------------------------------------


class FDAB016Rule(ValidationRule):
    """FDAB016: DM.COUNTRY should use ISO 3166-1 alpha-3 codes. WARNING."""

    rule_id: str = "FDAB016"
    description: str = "DM.COUNTRY should use ISO 3166-1 alpha-3 codes"
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
        if "COUNTRY" not in df.columns:
            return []
        country_values = df["COUNTRY"].dropna().unique()
        invalid = [str(v) for v in country_values if str(v) not in _ISO_3166_ALPHA3]
        if not invalid:
            return []
        return [
            RuleResult(
                rule_id=self.rule_id,
                rule_description=self.description,
                category=self.category,
                severity=self.severity,
                domain=domain,
                variable="COUNTRY",
                message=(
                    f"Non-standard COUNTRY values found: {invalid}. "
                    f"Expected ISO 3166-1 alpha-3 codes"
                ),
                affected_count=sum(
                    1 for v in df["COUNTRY"].dropna() if str(v) not in _ISO_3166_ALPHA3
                ),
                fix_suggestion="Map COUNTRY to ISO 3166-1 alpha-3 codes (e.g., USA, GBR, DEU)",
            )
        ]


# ---------------------------------------------------------------------------
# CM/EX domain rules (FDAB025, FDAB026)
# ---------------------------------------------------------------------------


class FDAB025Rule(ValidationRule):
    """FDAB025: CM.CMTRT must not be null/blank."""

    rule_id: str = "FDAB025"
    description: str = "CM.CMTRT must not be null or blank"
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
        if domain != "CM":
            return []
        if "CMTRT" not in df.columns:
            return []
        null_count = df["CMTRT"].isna().sum() + (df["CMTRT"].astype(str).str.strip() == "").sum()
        if null_count == 0:
            return []
        return [
            RuleResult(
                rule_id=self.rule_id,
                rule_description=self.description,
                category=self.category,
                severity=self.severity,
                domain=domain,
                variable="CMTRT",
                message=f"CMTRT has {null_count} null/blank value(s)",
                affected_count=int(null_count),
                fix_suggestion="Ensure CMTRT is populated for every CM record",
            )
        ]


class FDAB026Rule(ValidationRule):
    """FDAB026: EX.EXTRT must not be null/blank."""

    rule_id: str = "FDAB026"
    description: str = "EX.EXTRT must not be null or blank"
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
        if domain != "EX":
            return []
        if "EXTRT" not in df.columns:
            return []
        null_count = df["EXTRT"].isna().sum() + (df["EXTRT"].astype(str).str.strip() == "").sum()
        if null_count == 0:
            return []
        return [
            RuleResult(
                rule_id=self.rule_id,
                rule_description=self.description,
                category=self.category,
                severity=self.severity,
                domain=domain,
                variable="EXTRT",
                message=f"EXTRT has {null_count} null/blank value(s)",
                affected_count=int(null_count),
                fix_suggestion="Ensure EXTRT is populated for every EX record",
            )
        ]


# ---------------------------------------------------------------------------
# Cross-domain rules (FDAB020, FDAB021, FDAB022)
# ---------------------------------------------------------------------------


class FDAB020Rule(ValidationRule):
    """FDAB020: VISITNUM must be numeric when present."""

    rule_id: str = "FDAB020"
    description: str = "VISITNUM must be numeric when present"
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
        if "VISITNUM" not in df.columns:
            return []
        non_null = df["VISITNUM"].dropna()
        non_numeric = 0
        for val in non_null:
            try:
                float(val)
            except (ValueError, TypeError):
                non_numeric += 1
        if non_numeric == 0:
            return []
        return [
            RuleResult(
                rule_id=self.rule_id,
                rule_description=self.description,
                category=self.category,
                severity=self.severity,
                domain=domain,
                variable="VISITNUM",
                message=f"VISITNUM has {non_numeric} non-numeric value(s)",
                affected_count=non_numeric,
                fix_suggestion="Ensure all VISITNUM values are numeric",
            )
        ]


class FDAB021Rule(ValidationRule):
    """FDAB021: --DY must not include Day 0."""

    rule_id: str = "FDAB021"
    description: str = "Study day (--DY) must not include Day 0"
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
        results: list[RuleResult] = []
        dy_cols = [c for c in df.columns if c.endswith("DY")]
        for col in dy_cols:
            non_null = df[col].dropna()
            zero_count = 0
            for val in non_null:
                try:
                    if float(val) == 0:
                        zero_count += 1
                except (ValueError, TypeError):
                    pass
            if zero_count > 0:
                results.append(
                    RuleResult(
                        rule_id=self.rule_id,
                        rule_description=self.description,
                        category=self.category,
                        severity=self.severity,
                        domain=domain,
                        variable=col,
                        message=f"{col} has {zero_count} record(s) with Day 0",
                        affected_count=zero_count,
                        fix_suggestion=f"Day 0 does not exist in SDTM; {col} must be <0 or >0",
                    )
                )
        return results


class FDAB022Rule(ValidationRule):
    """FDAB022: --DTC must be ISO 8601 formatted."""

    rule_id: str = "FDAB022"
    description: str = "Date/time (--DTC) values must be ISO 8601"
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
        results: list[RuleResult] = []
        dtc_cols = [c for c in df.columns if c.endswith("DTC")]
        for col in dtc_cols:
            non_null = df[col].dropna().astype(str)
            if non_null.empty:
                continue
            invalid_mask = ~non_null.apply(lambda v: bool(_ISO_8601_PATTERN.match(v)))
            invalid_count = invalid_mask.sum()
            if invalid_count > 0:
                sample_invalid = non_null[invalid_mask].head(3).tolist()
                results.append(
                    RuleResult(
                        rule_id=self.rule_id,
                        rule_description=self.description,
                        category=self.category,
                        severity=self.severity,
                        domain=domain,
                        variable=col,
                        message=(
                            f"{col} has {invalid_count} non-ISO 8601 "
                            f"value(s). Examples: {sample_invalid}"
                        ),
                        affected_count=int(invalid_count),
                        fix_suggestion=f"Convert {col} values to ISO 8601 format (YYYY-MM-DD)",
                    )
                )
        return results


# ---------------------------------------------------------------------------
# LB paired result rules (FDAB035, FDAB036)
# ---------------------------------------------------------------------------


class FDAB035Rule(ValidationRule):
    """FDAB035: LB.LBORRES and LBORRESU must be paired. WARNING."""

    rule_id: str = "FDAB035"
    description: str = "LBORRES and LBORRESU must be paired"
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
        if domain != "LB":
            return []
        if "LBORRES" not in df.columns or "LBORRESU" not in df.columns:
            return []
        unpaired = df["LBORRES"].notna() & df["LBORRESU"].isna()
        count = unpaired.sum()
        if count == 0:
            return []
        return [
            RuleResult(
                rule_id=self.rule_id,
                rule_description=self.description,
                category=self.category,
                severity=self.severity,
                domain=domain,
                variable="LBORRESU",
                message=f"{count} record(s) have LBORRES without LBORRESU",
                affected_count=int(count),
                fix_suggestion="Ensure LBORRESU is populated when LBORRES has a value",
            )
        ]


class FDAB036Rule(ValidationRule):
    """FDAB036: LB.LBSTRESN and LBSTRESU must be paired. WARNING."""

    rule_id: str = "FDAB036"
    description: str = "LBSTRESN and LBSTRESU must be paired"
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
        if domain != "LB":
            return []
        if "LBSTRESN" not in df.columns or "LBSTRESU" not in df.columns:
            return []
        unpaired = df["LBSTRESN"].notna() & df["LBSTRESU"].isna()
        count = unpaired.sum()
        if count == 0:
            return []
        return [
            RuleResult(
                rule_id=self.rule_id,
                rule_description=self.description,
                category=self.category,
                severity=self.severity,
                domain=domain,
                variable="LBSTRESU",
                message=f"{count} record(s) have LBSTRESN without LBSTRESU",
                affected_count=int(count),
                fix_suggestion="Ensure LBSTRESU is populated when LBSTRESN has a value",
            )
        ]


# ---------------------------------------------------------------------------
# Population flag rule (FDAB-POP)
# ---------------------------------------------------------------------------


class PopulationFlagRule(ValidationRule):
    """FDAB-POP: Population flags must NOT appear in DM domain."""

    rule_id: str = "FDAB-POP"
    description: str = "Population flags must not appear in DM domain"
    category: RuleCategory = RuleCategory.FDA_BUSINESS
    severity: RuleSeverity = RuleSeverity.ERROR

    _POP_FLAGS = {"COMPLT", "FULLSET", "ITT", "PPROT", "SAFETY"}

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
        found = [c for c in df.columns if c in self._POP_FLAGS]
        if not found:
            return []
        return [
            RuleResult(
                rule_id=self.rule_id,
                rule_description=self.description,
                category=self.category,
                severity=self.severity,
                domain=domain,
                variable=", ".join(found),
                message=(
                    f"Population flag(s) found in DM: {found}. "
                    f"These belong in subject-level analysis "
                    f"datasets, not DM"
                ),
                affected_count=len(found),
                fix_suggestion="Remove population flags from DM; use SUPPDM or analysis datasets",
            )
        ]


# ---------------------------------------------------------------------------
# Rule registry
# ---------------------------------------------------------------------------


def get_fda_business_rules() -> list[ValidationRule]:
    """Return all FDA Business Rule instances for engine registration."""
    return [
        # Original rules
        FDAB057Rule(),
        FDAB055Rule(),
        FDAB015Rule(),
        FDAB039Rule(),
        FDAB009Rule(),
        FDAB030Rule(),
        FDABLC01Rule(),
        # AE domain rules
        FDAB001Rule(),
        FDAB002Rule(),
        FDAB003Rule(),
        FDAB004Rule(),
        FDAB005Rule(),
        # DM domain rule
        FDAB016Rule(),
        # CM/EX domain rules
        FDAB025Rule(),
        FDAB026Rule(),
        # Cross-domain rules
        FDAB020Rule(),
        FDAB021Rule(),
        FDAB022Rule(),
        # LB paired results
        FDAB035Rule(),
        FDAB036Rule(),
        # Population flags
        PopulationFlagRule(),
    ]
