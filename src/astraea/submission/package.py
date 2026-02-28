"""Submission package assembly and size validation.

Provides utilities for checking submission size against the FDA 5GB limit,
validating file naming conventions, and assembling a package manifest.
"""

from __future__ import annotations

from pathlib import Path

from astraea.models.mapping import DomainMappingSpec
from astraea.validation.rules.base import RuleCategory, RuleResult, RuleSeverity

# Domain-specific guidance for splitting oversized XPT files
SPLIT_GUIDANCE: dict[str, str] = {
    "lb": (
        "Split LB by LBCAT into separate XPT files "
        "(e.g., lb_chem.xpt, lb_hem.xpt, lb_ua.xpt)"
    ),
    "ae": (
        "Split AE by AESEV or AESER into separate XPT files if needed"
    ),
    "cm": (
        "Split CM by CMCAT into separate XPT files "
        "(e.g., cm_prior.xpt, cm_concom.xpt)"
    ),
    "eg": (
        "Split EG by EGTESTCD into separate XPT files "
        "(e.g., eg_rhythm.xpt, eg_interval.xpt)"
    ),
    "vs": (
        "Split VS by VSTESTCD grouping into separate XPT files"
    ),
    "fa": (
        "Split FA by FATESTCD or parent domain into separate XPT files"
    ),
}

_ONE_GB = 1024**3


def check_submission_size(
    output_dir: Path,
    *,
    limit_gb: float = 5.0,
) -> list[RuleResult]:
    """Check total submission size against FDA limit.

    Walks the output directory summing all .xpt file sizes. Returns:
    - ERROR if total exceeds limit_gb (default 5GB)
    - WARNING for any single file > 1GB with domain-specific split guidance
    - NOTICE always with total size and per-file breakdown

    Args:
        output_dir: Path to the output directory containing .xpt files.
        limit_gb: Maximum total size in GB (default 5.0).

    Returns:
        List of RuleResult findings.
    """
    results: list[RuleResult] = []

    if not output_dir.exists():
        return [
            RuleResult(
                rule_id="PKG-SIZE-001",
                rule_description="Submission size check",
                category=RuleCategory.FDA_TRC,
                severity=RuleSeverity.ERROR,
                message=f"Output directory does not exist: {output_dir}",
                fix_suggestion="Generate datasets before checking submission size",
            )
        ]

    xpt_files = sorted(output_dir.glob("*.xpt"))
    file_sizes: list[dict[str, str | int]] = []
    total_size = 0

    for xpt in xpt_files:
        size = xpt.stat().st_size
        total_size += size
        file_sizes.append({"name": xpt.name, "size": size})

    limit_bytes = int(limit_gb * _ONE_GB)

    # ERROR if total exceeds limit
    if total_size > limit_bytes:
        results.append(
            RuleResult(
                rule_id="PKG-SIZE-002",
                rule_description="Total submission size exceeds FDA limit",
                category=RuleCategory.FDA_TRC,
                severity=RuleSeverity.ERROR,
                message=(
                    f"Total XPT size {_format_size(total_size)} "
                    f"exceeds {limit_gb}GB FDA limit"
                ),
                fix_suggestion=(
                    "Reduce dataset sizes by splitting large domains "
                    "or removing unnecessary variables"
                ),
            )
        )

    # WARNING for individual files > 1GB with split guidance
    for info in file_sizes:
        name = str(info["name"])
        size = int(info["size"])
        if size > _ONE_GB:
            domain_code = name.replace(".xpt", "").lower()
            # Strip any suffix after underscore for lookup
            base_domain = domain_code.split("_")[0]
            guidance = SPLIT_GUIDANCE.get(
                base_domain,
                f"Consider splitting {name} by a categorical variable "
                f"to reduce file size below 1GB.",
            )
            results.append(
                RuleResult(
                    rule_id="PKG-SIZE-003",
                    rule_description="Individual XPT file exceeds 1GB",
                    category=RuleCategory.FDA_TRC,
                    severity=RuleSeverity.WARNING,
                    message=(
                        f"{name} is {_format_size(size)} (exceeds 1GB)"
                    ),
                    fix_suggestion=guidance,
                )
            )

    # NOTICE with size breakdown always
    breakdown = ", ".join(
        f"{info['name']}: {_format_size(int(info['size']))}"
        for info in file_sizes
    )
    results.append(
        RuleResult(
            rule_id="PKG-SIZE-004",
            rule_description="Submission size summary",
            category=RuleCategory.FDA_TRC,
            severity=RuleSeverity.NOTICE,
            message=(
                f"Total: {_format_size(total_size)}, "
                f"{len(xpt_files)} file(s). {breakdown}"
            ),
        )
    )

    return results


def validate_file_naming(
    output_dir: Path,
    expected_domains: list[str],
) -> list[RuleResult]:
    """Validate file naming conventions for submission.

    Checks that expected domain .xpt files exist with lowercase names,
    flags unexpected files, and verifies define.xml is present.

    Args:
        output_dir: Path to the output directory.
        expected_domains: List of domain codes expected in submission.

    Returns:
        List of RuleResult findings.
    """
    results: list[RuleResult] = []

    if not output_dir.exists():
        return [
            RuleResult(
                rule_id="PKG-NAME-001",
                rule_description="Output directory check",
                category=RuleCategory.FDA_TRC,
                severity=RuleSeverity.ERROR,
                message=f"Output directory does not exist: {output_dir}",
            )
        ]

    # Check expected domain files
    existing_xpts = {
        f.name for f in output_dir.iterdir() if f.suffix == ".xpt"
    }

    for domain in expected_domains:
        expected_name = f"{domain.lower()}.xpt"
        if expected_name not in existing_xpts:
            results.append(
                RuleResult(
                    rule_id="PKG-NAME-002",
                    rule_description="Expected domain file missing",
                    category=RuleCategory.FDA_TRC,
                    severity=RuleSeverity.ERROR,
                    domain=domain,
                    message=f"Expected file {expected_name} not found",
                    fix_suggestion=f"Generate the {domain} domain dataset",
                )
            )

    # Check for unexpected files
    expected_names = {d.lower() + ".xpt" for d in expected_domains}
    unexpected = existing_xpts - expected_names
    for name in sorted(unexpected):
        results.append(
            RuleResult(
                rule_id="PKG-NAME-003",
                rule_description="Unexpected XPT file found",
                category=RuleCategory.FDA_TRC,
                severity=RuleSeverity.WARNING,
                message=f"Unexpected file: {name}",
            )
        )

    # Check define.xml
    define_path = output_dir / "define.xml"
    if not define_path.exists():
        results.append(
            RuleResult(
                rule_id="PKG-NAME-004",
                rule_description="define.xml missing",
                category=RuleCategory.FDA_TRC,
                severity=RuleSeverity.ERROR,
                message="define.xml not found in output directory",
                fix_suggestion="Generate define.xml before submission",
            )
        )

    return results


def assemble_package_manifest(
    output_dir: Path,
    specs: list[DomainMappingSpec],
) -> dict:
    """Assemble an informational manifest of the submission package.

    Args:
        output_dir: Path to the output directory.
        specs: List of DomainMappingSpec for context.

    Returns:
        Dict with file inventory, total_size, domain_count,
        has_define_xml, and has_csdrg.
    """
    files: list[dict[str, str | int]] = []
    total_size = 0

    if output_dir.exists():
        for f in sorted(output_dir.iterdir()):
            if f.is_file():
                size = f.stat().st_size
                total_size += size
                domain = ""
                if f.suffix == ".xpt":
                    domain = f.stem.upper()
                files.append({
                    "path": str(f),
                    "name": f.name,
                    "size": size,
                    "domain": domain,
                })

    has_define = (output_dir / "define.xml").exists() if output_dir.exists() else False
    has_csdrg = any(
        f.name.endswith(".md") and "csdrg" in f.name.lower()
        for f in (output_dir.iterdir() if output_dir.exists() else [])
    )

    return {
        "files": files,
        "total_size": total_size,
        "domain_count": len(specs),
        "has_define_xml": has_define,
        "has_csdrg": has_csdrg,
    }


def _format_size(size_bytes: int) -> str:
    """Format a byte count as a human-readable size string."""
    if size_bytes >= _ONE_GB:
        return f"{size_bytes / _ONE_GB:.2f} GB"
    mb = size_bytes / (1024**2)
    if mb >= 1:
        return f"{mb:.1f} MB"
    kb = size_bytes / 1024
    return f"{kb:.1f} KB"
