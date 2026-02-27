"""SDTM domain mapping engine.

Orchestrates LLM-based variable mapping proposals, validates against
SDTM-IG and CT reference data, and produces enriched mapping specifications.
"""

from astraea.mapping.context import MappingContextBuilder
from astraea.mapping.engine import MappingEngine

__all__ = ["MappingContextBuilder", "MappingEngine"]
