"""cSDRG (Clinical Study Data Reviewer's Guide) template generator.

Generates a Markdown document following the PHUSE cSDRG structure,
populated with domain mapping rationale, validation summary, and
known false-positive documentation.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Template

from astraea.models.mapping import DomainMappingSpec
from astraea.validation.report import ValidationReport
from astraea.validation.rules.base import RuleSeverity

_CSDRG_TEMPLATE = """\
# Clinical Study Data Reviewer's Guide

## 1. Introduction

**Study ID:** {{ study_id }}

**Purpose:** This document provides a guide for reviewers of the SDTM datasets
submitted for study {{ study_id }}. It describes the data standards, domain
mapping rationale, and any known data issues or deviations.

**Generated:** {{ generated_at }}

**SDTM Implementation Guide Version:** {{ sdtm_ig_version }}

---

## 2. Study Description

[Placeholder: Add study description, trial design, objectives, endpoints]

---

## 3. Data Standards and Dictionary Inventory

| Item | Value |
|------|-------|
| Data Standard | SDTM |
| SDTM-IG Version | {{ sdtm_ig_version }} |
| Controlled Terminology Version | {{ ct_version }} |
| MedDRA Version | [Placeholder: Add MedDRA version] |

---

## 4. Dataset Overview

| Domain | Label | Class | Variables | Structure | Source Datasets |
|--------|-------|-------|-----------|-----------|-----------------|
{% for row in overview_rows -%}
| {{ row.dom }} | {{ row.lbl }} | {{ row.cls }} | {{ row.nv }} | {{ row.strc }} | {{ row.src }} |
{% endfor %}

---

## 5. Domain-Specific Information

{% for spec in specs %}
### 5.{{ loop.index }}. {{ spec.domain }} -- {{ spec.domain_label }}

**Source Data:** {{ spec.source_datasets | join(', ') }}

**Mapping Approach:**

| Pattern | Count |
|---------|-------|
{% for pattern, count in pattern_counts[spec.domain].items() -%}
| {{ pattern }} | {{ count }} |
{% endfor %}

{% if non_standard_vars[spec.domain] -%}
**Non-Standard Variables:**

{% for var in non_standard_vars[spec.domain] -%}
- {{ var }}
{% endfor %}
{% endif -%}

{% if spec.suppqual_candidates -%}
**SUPPQUAL Candidates:**

{% for var in spec.suppqual_candidates -%}
- {{ var }}
{% endfor %}
{% endif -%}

{% if spec.missing_required_variables -%}
**Missing Required Variables:**

{% for var in spec.missing_required_variables -%}
- {{ var }}
{% endfor %}
{% endif %}
{% endfor %}

---

## 6. Data Issues and Handling

### Date Imputation

Partial dates are represented using ISO 8601 truncation per SDTM-IG convention:
- Missing day: YYYY-MM
- Missing day and month: YYYY
- No date imputation is performed; partial dates are truncated, not filled.

### Missing Data Conventions

Missing data is represented as blank (character variables) or null (numeric variables)
per SDTM conventions.

### Known Data Issues

[Placeholder: Document any known data quality issues, protocol deviations
affecting data, or other concerns for the reviewer.]

---

## 7. Validation Results Summary

| Metric | Count |
|--------|-------|
| Total Findings | {{ validation_report.total_rules_run }} |
| Errors | {{ effective_errors }} |
| Warnings | {{ effective_warnings }} |
| Notices | {{ validation_report.notice_count }} |
| Submission Ready | {{ "Yes" if validation_report.submission_ready else "No" }} |

{% if top_issues -%}
**Top Issues:**

| # | Severity | Rule | Domain | Message |
|---|----------|------|--------|---------|
{% for issue in top_issue_rows -%}
| {{ loop.index }} | {{ issue.sev }} | {{ issue.rid }} | {{ issue.dom }} | {{ issue.msg }} |
{% endfor %}
{% endif %}

{% if known_fps -%}
### Known False Positives

The following validation findings are known false positives and have been excluded
from the effective error and warning counts.

| Rule ID | Domain | Variable | Reason |
|---------|--------|----------|--------|
{% for fp in fp_rows -%}
| {{ fp.rid }} | {{ fp.dom }} | {{ fp.var }} | {{ fp.reason }} |
{% endfor %}
{% endif %}

---

## 8. Non-Standard Variables

{% if all_suppqual_candidates -%}
The following source variables are recommended for SUPPQUAL domains:

| Domain | Variable | Notes |
|--------|----------|-------|
{% for item in all_suppqual_candidates -%}
| {{ item.domain }} | {{ item.variable }} | {{ item.notes }} |
{% endfor %}
{% else -%}
No non-standard variables requiring SUPPQUAL placement were identified.
{% endif %}
"""


def generate_csdrg(
    specs: list[DomainMappingSpec],
    validation_report: ValidationReport,
    study_id: str,
    output_path: Path,
    *,
    sdtm_ig_version: str = "3.4",
    ct_version: str | None = None,
) -> Path:
    """Generate a cSDRG (Clinical Study Data Reviewer's Guide) Markdown document.

    Uses Jinja2 to render a PHUSE-structured cSDRG template populated with
    domain mapping rationale, validation summary, and known false-positive
    documentation.

    Args:
        specs: List of DomainMappingSpec for all mapped domains.
        validation_report: The study validation report.
        study_id: Study identifier.
        output_path: Path to write the generated Markdown file.
        sdtm_ig_version: SDTM-IG version string (default "3.4").
        ct_version: Controlled Terminology version string.

    Returns:
        The output_path where the cSDRG was written.
    """
    # Build pattern counts per domain
    pattern_counts: dict[str, dict[str, int]] = {}
    for spec in specs:
        counter: Counter[str] = Counter()
        for vm in spec.variable_mappings:
            counter[vm.mapping_pattern.value] += 1
        pattern_counts[spec.domain] = dict(counter)

    # Build non-standard variables per domain (variables not in SDTM-IG)
    # We approximate this as any variable with notes mentioning "non-standard"
    # or any SUPPQUAL candidate
    non_standard_vars: dict[str, list[str]] = {}
    for spec in specs:
        ns_vars: list[str] = []
        for vm in spec.variable_mappings:
            notes_lower = vm.notes.lower()
            if "non-standard" in notes_lower or "non standard" in notes_lower:
                ns_vars.append(vm.sdtm_variable)
        non_standard_vars[spec.domain] = ns_vars

    # Build SUPPQUAL candidates across all domains
    all_suppqual_candidates: list[dict[str, str]] = []
    for spec in specs:
        for var in spec.suppqual_candidates:
            all_suppqual_candidates.append(
                {
                    "domain": spec.domain,
                    "variable": var,
                    "notes": f"Source variable from {', '.join(spec.source_datasets)}",
                }
            )

    # Build overview rows for the dataset table
    overview_rows = [
        {
            "dom": s.domain,
            "lbl": s.domain_label,
            "cls": s.domain_class,
            "nv": s.total_variables,
            "strc": s.structure,
            "src": ", ".join(s.source_datasets),
        }
        for s in specs
    ]

    # Get top issues (non-false-positive, sorted by severity)
    sorted_results = sorted(
        validation_report.results,
        key=lambda r: (
            0
            if r.severity == RuleSeverity.ERROR
            else (1 if r.severity == RuleSeverity.WARNING else 2),
            -r.affected_count,
        ),
    )
    top_issues = [r for r in sorted_results if not r.known_false_positive][:5]
    top_issue_rows = [
        {
            "sev": r.severity.display_name,
            "rid": r.rule_id,
            "dom": r.domain or "-",
            "msg": r.message[:80] + ("..." if len(r.message) > 80 else ""),
        }
        for r in top_issues
    ]

    # Get known false positives
    known_fps = validation_report.known_false_positive_results
    fp_rows = [
        {
            "rid": r.rule_id,
            "dom": r.domain or "-",
            "var": r.variable or "-",
            "reason": r.known_false_positive_reason or "-",
        }
        for r in known_fps
    ]

    # Render template
    template = Template(_CSDRG_TEMPLATE)
    rendered = template.render(
        study_id=study_id,
        generated_at=datetime.now(tz=UTC).isoformat(),
        sdtm_ig_version=sdtm_ig_version,
        ct_version=ct_version or "[Not specified]",
        specs=specs,
        overview_rows=overview_rows,
        pattern_counts=pattern_counts,
        non_standard_vars=non_standard_vars,
        validation_report=validation_report,
        effective_errors=validation_report.effective_error_count,
        effective_warnings=validation_report.effective_warning_count,
        top_issue_rows=top_issue_rows,
        known_fps=known_fps,
        fp_rows=fp_rows,
        all_suppqual_candidates=all_suppqual_candidates,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered)

    return output_path
