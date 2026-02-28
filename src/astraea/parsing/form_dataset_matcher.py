"""Match eCRF forms to raw SAS datasets by variable name overlap.

Associates parsed eCRF forms with profiled datasets to enable downstream
domain classification to use eCRF context. Matching is purely deterministic
based on the overlap between form field names and dataset clinical variables.
"""

from __future__ import annotations

from loguru import logger

from astraea.models.ecrf import ECRFForm
from astraea.models.profiling import DatasetProfile


def match_form_to_datasets(
    form: ECRFForm,
    profiles: list[DatasetProfile],
) -> list[tuple[str, float]]:
    """Score each dataset's variable overlap with a single eCRF form.

    Computes the fraction of form field names that appear in each dataset's
    clinical (non-EDC) variable names.

    Args:
        form: Parsed eCRF form with field definitions.
        profiles: List of profiled raw datasets.

    Returns:
        List of (dataset_filename, overlap_score) tuples sorted by score
        descending, only including datasets with overlap > 0.0.
    """
    form_fields = {f.field_name.upper() for f in form.fields}
    if not form_fields:
        return []

    results: list[tuple[str, float]] = []

    for profile in profiles:
        # Get clinical (non-EDC) variable names, uppercased
        clinical_vars = {vp.name.upper() for vp in profile.variables if not vp.is_edc_column}
        overlap = len(form_fields & clinical_vars)
        score = overlap / len(form_fields)
        if score > 0.0:
            results.append((profile.filename, score))

    results.sort(key=lambda x: x[1], reverse=True)
    return results


def match_all_forms(
    forms: list[ECRFForm],
    profiles: list[DatasetProfile],
    threshold: float = 0.2,
) -> dict[str, list[tuple[str, float]]]:
    """Match all eCRF forms to datasets, filtering by threshold.

    Args:
        forms: List of parsed eCRF forms.
        profiles: List of profiled raw datasets.
        threshold: Minimum overlap score to include a match (default 0.2).

    Returns:
        Dict of form_name -> [(dataset_name, score), ...] with only
        matches above the threshold included.
    """
    result: dict[str, list[tuple[str, float]]] = {}

    for form in forms:
        matches = match_form_to_datasets(form, profiles)
        filtered = [(name, score) for name, score in matches if score >= threshold]
        result[form.form_name] = filtered

        n = len(filtered)
        logger.info(
            "Matched form '{form_name}' to {n} dataset(s)",
            form_name=form.form_name,
            n=n,
        )

    return result


def get_unmatched_datasets(
    form_matches: dict[str, list[tuple[str, float]]],
    all_dataset_names: list[str],
) -> list[str]:
    """Find datasets that appear in no form match.

    Args:
        form_matches: Output of :func:`match_all_forms`.
        all_dataset_names: Complete list of raw dataset filenames.

    Returns:
        Dataset names that have no form association.
    """
    matched_datasets: set[str] = set()
    for matches in form_matches.values():
        for dataset_name, _score in matches:
            matched_datasets.add(dataset_name)

    return sorted(name for name in all_dataset_names if name not in matched_datasets)


def get_unmatched_forms(
    form_matches: dict[str, list[tuple[str, float]]],
) -> list[str]:
    """Find forms with zero dataset matches.

    Args:
        form_matches: Output of :func:`match_all_forms`.

    Returns:
        Form names that matched no datasets.
    """
    return sorted(form_name for form_name, matches in form_matches.items() if len(matches) == 0)
