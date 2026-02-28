"""eCTD directory structure assembly for FDA submission.

Creates the m5/datasets/tabulations/sdtm/ directory tree required by
eCTD format and copies XPT datasets, define.xml, and cSDRG into the
correct locations with validated file naming.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from loguru import logger


def validate_xpt_filename(name: str) -> tuple[bool, str]:
    """Check FDA naming conventions for an XPT file.

    Valid names are lowercase, alphanumeric (with underscores allowed),
    and end with the .xpt extension.

    Args:
        name: The filename to validate (e.g., "dm.xpt").

    Returns:
        Tuple of (is_valid, corrected_name).  If the name is already
        valid, corrected_name equals name.  Otherwise corrected_name
        is the auto-corrected version (lowercased, invalid chars removed).
    """
    corrected = name.lower()

    # Split stem and suffix
    stem = Path(corrected).stem
    suffix = Path(corrected).suffix

    # Ensure .xpt extension
    if suffix != ".xpt":
        corrected = stem + ".xpt"

    # Remove invalid characters from stem (keep alphanumeric + underscore)
    clean_stem = re.sub(r"[^a-z0-9_]", "", Path(corrected).stem)
    if not clean_stem:
        clean_stem = "unnamed"
    corrected = clean_stem + ".xpt"

    is_valid = corrected == name
    return is_valid, corrected


def assemble_ectd_package(
    source_dir: Path,
    output_dir: Path,
    study_id: str,
    *,
    define_xml_path: Path | None = None,
    csdrg_path: Path | None = None,
) -> Path:
    """Assemble the eCTD directory structure for FDA submission.

    Creates the standard eCTD module 5 directory tree and copies
    submission artifacts into the correct locations:

    - XPT datasets go into ``m5/datasets/tabulations/sdtm/``
    - define.xml goes into the same sdtm/ directory
    - cSDRG goes at the ``tabulations/`` level per FDA guidance

    File names are validated and auto-corrected to lowercase.

    Args:
        source_dir: Directory containing source .xpt files.
        output_dir: Root directory where the eCTD tree will be created.
        study_id: Study identifier (used for logging context).
        define_xml_path: Optional path to define.xml file.
        csdrg_path: Optional path to cSDRG document.

    Returns:
        Path to the sdtm/ directory within the eCTD tree.

    Raises:
        FileNotFoundError: If source_dir does not exist.
    """
    if not source_dir.exists():
        msg = f"Source directory does not exist: {source_dir}"
        raise FileNotFoundError(msg)

    # Create the eCTD directory structure
    sdtm_dir = output_dir / "m5" / "datasets" / "tabulations" / "sdtm"
    sdtm_dir.mkdir(parents=True, exist_ok=True)
    logger.info(
        "Created eCTD directory structure: {}",
        sdtm_dir.relative_to(output_dir),
    )

    # Copy and validate XPT files
    xpt_files = sorted(source_dir.glob("*.xpt"))
    if not xpt_files:
        logger.warning("No .xpt files found in source directory: {}", source_dir)

    for xpt in xpt_files:
        is_valid, corrected_name = validate_xpt_filename(xpt.name)
        dest = sdtm_dir / corrected_name

        if not is_valid:
            logger.info(
                "Renamed {} -> {} (FDA naming convention)",
                xpt.name,
                corrected_name,
            )

        shutil.copy2(xpt, dest)
        logger.debug("Copied {} to {}", xpt.name, dest)

    # Copy define.xml if provided
    if define_xml_path is not None:
        if define_xml_path.exists():
            dest = sdtm_dir / "define.xml"
            shutil.copy2(define_xml_path, dest)
            logger.info("Copied define.xml to {}", dest)
        else:
            logger.warning("define.xml path does not exist: {}", define_xml_path)

    # Copy cSDRG if provided -- placed at tabulations/ level per FDA guidance
    if csdrg_path is not None:
        tabulations_dir = sdtm_dir.parent  # m5/datasets/tabulations/
        if csdrg_path.exists():
            dest = tabulations_dir / csdrg_path.name
            shutil.copy2(csdrg_path, dest)
            logger.info("Copied cSDRG to {}", dest)
        else:
            logger.warning("cSDRG path does not exist: {}", csdrg_path)

    logger.info(
        "eCTD package assembled for study {} ({} XPT files)",
        study_id,
        len(xpt_files),
    )

    return sdtm_dir
