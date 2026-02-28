"""NCI Controlled Terminology reference data lookup.

Provides structured access to bundled CDISC CT codelists.
All data is loaded from JSON files at initialization -- no network calls.
"""

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger

from astraea.models.controlled_terms import Codelist, CodelistTerm, CTPackage

_DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "ct"


class CTReference:
    """Queryable interface over bundled NCI CDISC Controlled Terminology.

    Loads codelists.json once at init and exposes lookup methods that
    return Pydantic models. Used by mapping agents for CT validation
    and by validators for conformance checking.
    """

    def __init__(self, data_path: str | Path | None = None) -> None:
        data_dir = Path(data_path) if data_path else _DEFAULT_DATA_DIR
        codelists_file = data_dir / "codelists.json"

        if not codelists_file.exists():
            msg = f"CT codelists.json not found at {codelists_file}"
            raise FileNotFoundError(msg)

        with open(codelists_file) as f:
            raw = json.load(f)

        # Build Pydantic models from raw JSON
        codelists: dict[str, Codelist] = {}
        for code, data in raw["codelists"].items():
            terms: dict[str, CodelistTerm] = {}
            for sv, tdata in data["terms"].items():
                terms[sv] = CodelistTerm(**tdata)
            codelists[code] = Codelist(
                code=data["code"],
                name=data["name"],
                extensible=data["extensible"],
                variable_mappings=data.get("variable_mappings", []),
                terms=terms,
            )

        self._package = CTPackage(
            version=raw["version"],
            ig_version=raw["ig_version"],
            codelists=codelists,
        )

        # Build reverse lookup: variable name -> list of codelist codes
        self._variable_to_codelist: dict[str, list[str]] = {}
        for code, cl in codelists.items():
            for var_name in cl.variable_mappings:
                key = var_name.upper()
                if key not in self._variable_to_codelist:
                    self._variable_to_codelist[key] = []
                self._variable_to_codelist[key].append(code)

    @property
    def version(self) -> str:
        """Return the CT package version string."""
        return self._package.version

    @property
    def ig_version(self) -> str:
        """Return the associated SDTM-IG version."""
        return self._package.ig_version

    def lookup_codelist(self, codelist_code: str) -> Codelist | None:
        """Return the full codelist, or None if not found."""
        return self._package.codelists.get(codelist_code)

    def is_extensible(self, codelist_code: str) -> bool:
        """Check whether a codelist allows study-specific values.

        Returns False if codelist not found (conservative default).
        """
        cl = self.lookup_codelist(codelist_code)
        if cl is None:
            return False
        return cl.extensible

    def validate_term(self, codelist_code: str, value: str) -> bool:
        """Check if a submission value is valid for a codelist.

        For non-extensible codelists, returns True only if the value
        is an exact match to a defined submission value.
        For extensible codelists, always returns True (any value allowed).

        Returns False if the codelist is not found.
        """
        cl = self.lookup_codelist(codelist_code)
        if cl is None:
            return False
        if cl.extensible:
            return True
        return value in cl.terms

    def get_codelist_for_variable(self, variable_name: str) -> Codelist | None:
        """Reverse lookup: given an SDTM variable name, find its codelist.

        Returns the first matching codelist. If multiple codelists map to
        this variable, logs a warning. Use ``get_codelists_for_variable``
        to retrieve all matches.
        """
        codes = self._variable_to_codelist.get(variable_name.upper())
        if codes is None or len(codes) == 0:
            return None
        if len(codes) > 1:
            logger.warning(
                "Variable {} maps to multiple codelists: {}. Returning first.",
                variable_name,
                codes,
            )
        return self.lookup_codelist(codes[0])

    def get_codelists_for_variable(self, variable_name: str) -> list[Codelist]:
        """Reverse lookup: given an SDTM variable name, find all matching codelists.

        Returns a list of Codelist objects (may be empty if no match).
        """
        codes = self._variable_to_codelist.get(variable_name.upper(), [])
        result: list[Codelist] = []
        for code in codes:
            cl = self.lookup_codelist(code)
            if cl is not None:
                result.append(cl)
        return result

    def list_codelists(self) -> list[str]:
        """Return all available codelist codes."""
        return sorted(self._package.codelists.keys())
