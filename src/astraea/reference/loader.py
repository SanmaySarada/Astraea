"""Convenience loaders for bundled SDTM-IG and CT reference data.

Usage:
    from astraea.reference import load_sdtm_reference, load_ct_reference

    ref = load_sdtm_reference()
    ct = load_ct_reference()
"""

from __future__ import annotations

from astraea.reference.controlled_terms import CTReference
from astraea.reference.sdtm_ig import SDTMReference


def load_sdtm_reference() -> SDTMReference:
    """Load SDTM-IG reference data from the default bundled location."""
    return SDTMReference()


def load_ct_reference() -> CTReference:
    """Load Controlled Terminology reference data from the default bundled location."""
    return CTReference()
