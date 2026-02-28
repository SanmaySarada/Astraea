"""RELREC (Related Records) domain models.

Provides Pydantic models for the RELREC domain which captures
relationships between records across different SDTM domains.

NOTE: Full RELREC implementation is deferred to Phase 7+.
See PITFALLS.md m2: "RELREC is complex, no raw data drives it
in Fakedata, and it is rarely needed for initial submissions."
Only a minimal model and stub generator are provided here.

Exports:
    RelRecRecord -- single RELREC row model
    RelRecRelationship -- relationship definition between domains
    RelRecConfig -- configuration for RELREC generation
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class RelRecRecord(BaseModel):
    """A single RELREC (Related Records) row.

    Represents one half of a relationship link between records in
    two different SDTM domains. Relationships are paired via RELID.

    Attributes:
        studyid: Study identifier.
        rdomain: Related domain code (e.g., "AE", "CM").
        usubjid: Unique subject identifier.
        idvar: Identifier variable name in the related domain (e.g., "AESEQ").
        idvarval: Value of the identifier variable.
        reltype: Relationship type -- "ONE" or "MANY".
        relid: Relationship identifier linking paired records.
    """

    studyid: str = Field(..., min_length=1, description="Study identifier")
    rdomain: str = Field(
        ..., min_length=1, max_length=4, description="Related domain code"
    )
    usubjid: str = Field(..., min_length=1, description="Unique subject identifier")
    idvar: str = Field(
        ..., min_length=1, max_length=8, description="Identifier variable name"
    )
    idvarval: str = Field(
        ..., min_length=1, description="Identifier variable value"
    )
    reltype: str = Field(
        ..., description="Relationship type (ONE or MANY)"
    )
    relid: str = Field(
        ..., min_length=1, description="Relationship identifier"
    )

    @field_validator("rdomain")
    @classmethod
    def _uppercase_rdomain(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("reltype")
    @classmethod
    def _validate_reltype(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in ("ONE", "MANY"):
            msg = f"reltype must be 'ONE' or 'MANY', got '{v}'"
            raise ValueError(msg)
        return v


class RelRecRelationship(BaseModel):
    """Definition of a relationship between two SDTM domains.

    Specifies which domains are related and how -- used by RELREC
    generators to create properly linked records.

    Attributes:
        domain_1: First domain code (e.g., "AE").
        idvar_1: Identifier variable in domain_1 (e.g., "AESEQ").
        reltype_1: Relationship type for domain_1 side.
        domain_2: Second domain code (e.g., "CM").
        idvar_2: Identifier variable in domain_2 (e.g., "CMSEQ").
        reltype_2: Relationship type for domain_2 side.
        description: Human-readable description of the relationship.
    """

    domain_1: str = Field(..., min_length=1, max_length=4)
    idvar_1: str = Field(..., min_length=1, max_length=8)
    reltype_1: str = Field(default="ONE")
    domain_2: str = Field(..., min_length=1, max_length=4)
    idvar_2: str = Field(..., min_length=1, max_length=8)
    reltype_2: str = Field(default="ONE")
    description: str = Field(default="")


class RelRecConfig(BaseModel):
    """Configuration for RELREC domain generation.

    RELREC full implementation deferred. See PITFALLS.md m2: RELREC is
    complex, no raw data drives it in Fakedata, and it is rarely needed
    for initial submissions. This config exists to define the relationship
    schema for future implementation.

    Attributes:
        relationships: List of domain relationship definitions.
    """

    relationships: list[RelRecRelationship] = Field(
        default_factory=list,
        description="Definitions of cross-domain relationships",
    )
