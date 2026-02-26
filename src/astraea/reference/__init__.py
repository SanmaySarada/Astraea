"""SDTM-IG and Controlled Terminology reference lookup.

Re-exports for convenient imports:
    from astraea.reference import SDTMReference, CTReference
    from astraea.reference import load_sdtm_reference, load_ct_reference
"""

from astraea.reference.controlled_terms import CTReference
from astraea.reference.loader import load_ct_reference, load_sdtm_reference
from astraea.reference.sdtm_ig import SDTMReference

__all__ = [
    "CTReference",
    "SDTMReference",
    "load_ct_reference",
    "load_sdtm_reference",
]
