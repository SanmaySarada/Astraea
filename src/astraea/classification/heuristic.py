"""Deterministic heuristic domain scoring for raw SAS datasets.

Classifies raw datasets to SDTM domains using filename pattern matching
and variable name overlap with SDTM-IG specs. No LLM calls -- purely
rule-based scoring that serves as a sanity check against LLM classification
(prevents hallucination cascading per Pitfall C1).
"""

from __future__ import annotations

from astraea.models.classification import HeuristicScore
from astraea.models.profiling import DatasetProfile
from astraea.reference.sdtm_ig import SDTMReference

# Filename patterns per domain. Keys are domain codes, values are lists of
# filename substrings (lowercased) that indicate the domain.
FILENAME_PATTERNS: dict[str, list[str]] = {
    "AE": ["ae"],
    "CM": ["cm", "conmed"],
    "DM": ["dm", "demo"],
    "DS": ["ds", "disp"],
    "DV": ["dv", "deviat"],
    "EG": ["eg", "ecg"],
    "EX": ["ex", "expos", "dose"],
    "IE": ["ie", "incl", "excl"],
    "LB": ["lb", "lab", "biochem", "hem", "coag", "urin", "chem"],
    "MH": ["mh", "medhist", "haemh"],
    "PE": ["pe", "physex"],
    "VS": ["vs", "vital"],
    "CE": ["ce"],
    "DA": ["da"],
    "SV": ["sv"],
}

# Prefixes used to detect multi-file domains that should be merged.
# Key is the target domain, values are prefixes that indicate membership.
MERGE_PREFIXES: dict[str, list[str]] = {
    "LB": ["lb_", "lab"],
    "EG": ["eg_", "ecg"],
    "DS": ["ds_"],
    "EX": ["ex_"],
    "MH": ["haemh", "mh_"],
}

# Common identifier variables present in most/all domains -- excluded from
# overlap scoring because they don't help distinguish between domains.
_COMMON_IDENTIFIERS: frozenset[str] = frozenset(
    {"STUDYID", "DOMAIN", "USUBJID", "SUBJID", "SITEID"}
)


def _is_segment_match(name: str, pattern: str) -> bool:
    """Check if pattern appears as a delimited segment in name.

    Returns True if pattern appears bounded by underscores, hyphens, or
    string boundaries -- not as a substring of a larger word.
    E.g., "conmed" in "conmed_extra" is True, but "da" in "unknown_data" is False.
    """
    idx = name.find(pattern)
    if idx < 0 or name == pattern:
        return False

    # Check left boundary: start of string or delimiter
    if idx > 0 and name[idx - 1] not in ("_", "-"):
        return False

    # Check right boundary: end of string or delimiter
    end = idx + len(pattern)
    return not (end < len(name) and name[end] not in ("_", "-"))


def score_by_filename(dataset_name: str) -> list[HeuristicScore]:
    """Score domain likelihood from filename patterns.

    Exact matches (filename equals the pattern) score 1.0.
    Prefix/contains matches (filename starts with or contains the pattern)
    score 0.7.

    Args:
        dataset_name: Raw dataset filename (e.g., "ae.sas7bdat").

    Returns:
        List of HeuristicScore sorted by score descending. Empty if no match.
    """
    # Normalize: strip extension, lowercase
    name = dataset_name.lower()
    for ext in (".sas7bdat", ".sas7bcat", ".xpt"):
        if name.endswith(ext):
            name = name[: -len(ext)]
            break

    scores: list[HeuristicScore] = []

    for domain, patterns in FILENAME_PATTERNS.items():
        best_score = 0.0
        best_signal = ""

        for pattern in patterns:
            if name == pattern:
                # Exact match -- highest confidence
                best_score = 1.0
                best_signal = f"filename exact match: {pattern}"
                break
            elif name.startswith(pattern + "_") or _is_segment_match(
                name, pattern
            ):
                if best_score < 0.7:
                    best_score = 0.7
                    best_signal = f"filename contains: {pattern}"

        if best_score > 0.0:
            scores.append(
                HeuristicScore(
                    domain=domain,
                    score=best_score,
                    signals=[best_signal],
                )
            )

    scores.sort(key=lambda s: s.score, reverse=True)
    return scores


def score_by_variables(
    profile: DatasetProfile,
    ref: SDTMReference,
) -> list[HeuristicScore]:
    """Score domain likelihood from variable name overlap with SDTM-IG specs.

    Compares the clinical (non-EDC) variable names in the profile against
    domain-specific variables in the SDTM-IG, excluding common identifiers
    that appear in every domain.

    Args:
        profile: Profiled dataset with variable metadata.
        ref: SDTM-IG reference for domain variable lookups.

    Returns:
        List of HeuristicScore sorted by score descending, only including
        domains with overlap > 0.1.
    """
    # Get clinical variable names (non-EDC), uppercased
    clinical_vars = frozenset(
        vp.name.upper()
        for vp in profile.variables
        if not vp.is_edc_column
    )

    scores: list[HeuristicScore] = []

    for domain in ref.list_domains():
        spec = ref.get_domain_spec(domain)
        if spec is None:
            continue

        # Get domain-specific variables (excluding common identifiers)
        domain_vars = frozenset(
            v.name for v in spec.variables if v.name not in _COMMON_IDENTIFIERS
        )

        if not domain_vars:
            continue

        overlap = clinical_vars & domain_vars
        overlap_ratio = len(overlap) / len(domain_vars)

        if overlap_ratio > 0.1:
            scores.append(
                HeuristicScore(
                    domain=domain,
                    score=round(overlap_ratio, 3),
                    signals=[
                        f"variable overlap: {len(overlap)}/{len(domain_vars)}"
                    ],
                )
            )

    scores.sort(key=lambda s: s.score, reverse=True)
    return scores


def compute_heuristic_scores(
    dataset_name: str,
    profile: DatasetProfile | None = None,
    ref: SDTMReference | None = None,
) -> list[HeuristicScore]:
    """Combine filename and variable heuristic scores.

    When both filename and variable scores are available, takes the maximum
    score per domain. Returns UNCLASSIFIED if no domain scores >= 0.3.

    Args:
        dataset_name: Raw dataset filename.
        profile: Optional dataset profile for variable overlap scoring.
        ref: Optional SDTM-IG reference for variable overlap scoring.

    Returns:
        List of HeuristicScore sorted by score descending. Contains at least
        one entry (UNCLASSIFIED if nothing matched).
    """
    filename_scores = score_by_filename(dataset_name)

    variable_scores: list[HeuristicScore] = []
    if profile is not None and ref is not None:
        variable_scores = score_by_variables(profile, ref)

    # Merge: take max score per domain, combine signals
    domain_map: dict[str, HeuristicScore] = {}

    for hs in filename_scores:
        domain_map[hs.domain] = hs

    for hs in variable_scores:
        if hs.domain in domain_map:
            existing = domain_map[hs.domain]
            # Take the higher score, combine signals
            if hs.score > existing.score:
                domain_map[hs.domain] = HeuristicScore(
                    domain=hs.domain,
                    score=hs.score,
                    signals=existing.signals + hs.signals,
                )
            else:
                domain_map[hs.domain] = HeuristicScore(
                    domain=existing.domain,
                    score=existing.score,
                    signals=existing.signals + hs.signals,
                )
        else:
            domain_map[hs.domain] = hs

    combined = sorted(domain_map.values(), key=lambda s: s.score, reverse=True)

    # If nothing scored >= 0.3, return UNCLASSIFIED
    if not combined or combined[0].score < 0.3:
        return [
            HeuristicScore(
                domain="UNCLASSIFIED",
                score=0.0,
                signals=["no heuristic match"],
            )
        ]

    return combined


def detect_merge_groups(dataset_names: list[str]) -> dict[str, list[str]]:
    """Detect groups of datasets that should merge into the same SDTM domain.

    Uses MERGE_PREFIXES to find datasets sharing a common prefix pattern
    (e.g., lb_biochem, lb_hem, lb_urin all merge into LB).

    Args:
        dataset_names: List of raw dataset filenames.

    Returns:
        Dict of domain code -> list of dataset names, only for groups with
        2 or more datasets.
    """
    # Normalize names: strip extensions, lowercase
    normalized: dict[str, str] = {}  # normalized -> original
    for name in dataset_names:
        norm = name.lower()
        for ext in (".sas7bdat", ".sas7bcat", ".xpt"):
            if norm.endswith(ext):
                norm = norm[: -len(ext)]
                break
        normalized[norm] = name

    groups: dict[str, list[str]] = {}

    for domain, prefixes in MERGE_PREFIXES.items():
        members: list[str] = []
        for norm, original in normalized.items():
            for prefix in prefixes:
                if norm.startswith(prefix) and norm != prefix.rstrip("_"):
                    members.append(original)
                    break
        if len(members) >= 2:
            groups[domain] = sorted(members)

    return groups
