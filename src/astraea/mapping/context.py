"""Mapping context assembly for LLM prompts.

Gathers domain-specific reference data, source dataset profiles, eCRF form
metadata, and controlled terminology into a focused prompt string for the
LLM mapping agent. Filters out EDC system columns and includes only relevant
CT codelists to keep context within token budgets.
"""

from __future__ import annotations

from astraea.models.controlled_terms import Codelist
from astraea.models.ecrf import ECRFForm
from astraea.models.mapping import StudyMetadata
from astraea.models.profiling import DatasetProfile, VariableProfile
from astraea.models.sdtm import CoreDesignation, DomainSpec
from astraea.reference.controlled_terms import CTReference
from astraea.reference.sdtm_ig import SDTMReference


class MappingContextBuilder:
    """Assembles focused LLM context for a single domain mapping call.

    Combines SDTM-IG domain specification, source dataset profiles (with
    EDC columns filtered out), eCRF form metadata, and only the controlled
    terminology codelists referenced by the target domain's variables.

    Usage::

        builder = MappingContextBuilder(sdtm_ref, ct_ref)
        prompt = builder.build_prompt(
            domain="DM",
            source_profiles=[dm_profile],
            ecrf_forms=[demographics_form],
            study_metadata=study_meta,
        )
    """

    def __init__(self, sdtm_ref: SDTMReference, ct_ref: CTReference) -> None:
        self._sdtm_ref = sdtm_ref
        self._ct_ref = ct_ref

    def build_prompt(
        self,
        *,
        domain: str,
        source_profiles: list[DatasetProfile],
        ecrf_forms: list[ECRFForm],
        study_metadata: StudyMetadata,
        cross_domain_profiles: dict[str, DatasetProfile] | None = None,
    ) -> str:
        """Build a structured context string for the LLM mapping call.

        Args:
            domain: Target SDTM domain code (e.g., "DM", "AE").
            source_profiles: Profiled source datasets for this domain.
            ecrf_forms: eCRF forms associated with this domain.
            study_metadata: Study-level identifiers and constants.
            cross_domain_profiles: Optional profiles of datasets from other
                domains that may supply cross-referenced variables.

        Returns:
            Markdown-formatted context string with sections for domain spec,
            source data, eCRF, controlled terminology, cross-domain sources,
            and study metadata.
        """
        domain_spec = self._sdtm_ref.get_domain_spec(domain)
        if domain_spec is None:
            msg = f"Unknown SDTM domain: {domain}"
            raise ValueError(msg)

        relevant_codelists = _get_relevant_codelists(domain_spec, self._ct_ref)

        sections: list[str] = []

        # 1. SDTM Domain section
        sections.append(_format_domain_section(domain_spec))

        # 2. Source Data section
        sections.append(_format_source_data_section(source_profiles))

        # 3. eCRF Forms section
        sections.append(_format_ecrf_section(ecrf_forms))

        # 4. Controlled Terminology section
        sections.append(_format_ct_section(relevant_codelists))

        # 5. Cross-Domain Sources section
        sections.append(
            _format_cross_domain_section(cross_domain_profiles)
        )

        # 6. Study Metadata section
        sections.append(_format_study_metadata_section(study_metadata))

        return "\n\n".join(sections)


def _get_relevant_codelists(
    domain_spec: DomainSpec, ct_ref: CTReference
) -> dict[str, Codelist]:
    """Collect only CT codelists referenced by the domain's variables.

    Args:
        domain_spec: The SDTM-IG domain specification.
        ct_ref: Controlled terminology reference.

    Returns:
        Dict mapping codelist code to Codelist for each referenced codelist.
    """
    codelists: dict[str, Codelist] = {}
    for var_spec in domain_spec.variables:
        code = var_spec.codelist_code
        if code is None:
            continue
        if code in codelists:
            continue
        cl = ct_ref.lookup_codelist(code)
        if cl is not None:
            codelists[code] = cl
    return codelists


def _format_variable_profile(vp: VariableProfile) -> str:
    """Format a single variable profile as a compact one-line summary.

    Args:
        vp: The variable profile to format.

    Returns:
        A single line like: "- AGE (numeric) label='Age' unique=45 missing=2% samples=[25, 30, 40]"
    """
    samples = ", ".join(vp.sample_values[:5])
    parts = [
        f"- {vp.name} ({vp.dtype})",
        f'label="{vp.label}"',
        f"unique={vp.n_unique}",
        f"missing={vp.missing_pct:.0f}%",
    ]
    if samples:
        parts.append(f"samples=[{samples}]")
    if vp.is_date and vp.detected_date_format:
        parts.append(f"date_format={vp.detected_date_format}")
    return " | ".join(parts)


def _format_domain_section(domain_spec: DomainSpec) -> str:
    """Format the SDTM domain specification section."""
    lines: list[str] = []
    lines.append(f"## SDTM Domain: {domain_spec.domain} ({domain_spec.description})")
    lines.append(f"Class: {domain_spec.domain_class.value}")
    lines.append(f"Structure: {domain_spec.structure}")
    if domain_spec.key_variables:
        lines.append(f"Key Variables: {', '.join(domain_spec.key_variables)}")
    lines.append("")

    # Group variables by core designation
    for core_label, core_enum in [
        ("Required", CoreDesignation.REQ),
        ("Expected", CoreDesignation.EXP),
        ("Permissible", CoreDesignation.PERM),
    ]:
        vars_in_group = [v for v in domain_spec.variables if v.core == core_enum]
        if not vars_in_group:
            continue
        lines.append(f"### {core_label} Variables")
        for v in vars_in_group:
            codelist_str = f" codelist={v.codelist_code}" if v.codelist_code else ""
            lines.append(
                f"- {v.name} ({v.data_type}) | {v.label}{codelist_str}"
            )
        lines.append("")

    return "\n".join(lines)


def _format_source_data_section(profiles: list[DatasetProfile]) -> str:
    """Format the source dataset profiles section, excluding EDC columns."""
    lines: list[str] = []
    lines.append("## Source Data")
    if not profiles:
        lines.append("No source profiles provided.")
        return "\n".join(lines)

    for profile in profiles:
        lines.append(f"\n### {profile.filename} ({profile.row_count} rows)")
        clinical_vars = [v for v in profile.variables if not v.is_edc_column]
        if not clinical_vars:
            lines.append("No clinical variables found.")
            continue
        for vp in clinical_vars:
            lines.append(_format_variable_profile(vp))

    return "\n".join(lines)


def _format_ecrf_section(ecrf_forms: list[ECRFForm]) -> str:
    """Format the eCRF forms section."""
    lines: list[str] = []
    lines.append("## eCRF Forms")
    if not ecrf_forms:
        lines.append("No eCRF forms provided.")
        return "\n".join(lines)

    for form in ecrf_forms:
        lines.append(f"\n### {form.form_name}")
        if not form.fields:
            lines.append("No fields extracted.")
            continue
        for field in form.fields:
            coded_str = ""
            if field.coded_values:
                pairs = [f"{k}={v}" for k, v in field.coded_values.items()]
                coded_str = f" coded=[{', '.join(pairs)}]"
            units_str = f" units={field.units}" if field.units else ""
            field_line = (
                f"- {field.field_name} ({field.data_type})"
                f" | {field.sas_label}{units_str}{coded_str}"
            )
            lines.append(field_line)

    return "\n".join(lines)


def _format_ct_section(codelists: dict[str, Codelist]) -> str:
    """Format the controlled terminology section."""
    lines: list[str] = []
    lines.append("## Controlled Terminology")
    if not codelists:
        lines.append("No relevant codelists for this domain.")
        return "\n".join(lines)

    for code, cl in sorted(codelists.items()):
        ext_label = "extensible" if cl.extensible else "non-extensible"
        lines.append(f"\n### {cl.name} ({code}) [{ext_label}]")
        submission_values = sorted(cl.terms.keys())
        if len(submission_values) <= 20:
            lines.append(f"Values: {', '.join(submission_values)}")
        else:
            shown = submission_values[:20]
            lines.append(
                f"Values ({len(submission_values)} total, first 20): {', '.join(shown)}"
            )

    return "\n".join(lines)


def _format_cross_domain_section(
    profiles: dict[str, DatasetProfile] | None,
) -> str:
    """Format the cross-domain sources summary section."""
    lines: list[str] = []
    lines.append("## Cross-Domain Sources Available")
    if not profiles:
        lines.append("None.")
        return "\n".join(lines)

    for label, profile in sorted(profiles.items()):
        clinical_vars = [v for v in profile.variables if not v.is_edc_column]
        var_summary = ", ".join(
            f"{v.name} ({v.label})" for v in clinical_vars[:10]
        )
        extra = ""
        if len(clinical_vars) > 10:
            extra = f" ... and {len(clinical_vars) - 10} more"
        lines.append(f"- {label} [{profile.filename}]: {var_summary}{extra}")

    return "\n".join(lines)


def _format_study_metadata_section(study_metadata: StudyMetadata) -> str:
    """Format the study metadata section."""
    lines: list[str] = []
    lines.append("## Study Metadata")
    lines.append(f"- Study ID: {study_metadata.study_id}")
    lines.append(f"- Site ID Variable: {study_metadata.site_id_variable}")
    lines.append(f"- Subject ID Variable: {study_metadata.subject_id_variable}")
    return "\n".join(lines)
