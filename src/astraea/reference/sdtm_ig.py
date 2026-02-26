"""SDTM Implementation Guide reference data lookup.

Provides structured access to bundled SDTM-IG v3.4 domain specifications.
All data is loaded from JSON files at initialization -- no network calls.
"""

from __future__ import annotations

import json
from pathlib import Path

from astraea.models.sdtm import (
    CoreDesignation,
    DomainClass,
    DomainSpec,
    SDTMIGPackage,
    VariableSpec,
)

_DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "sdtm_ig"


class SDTMReference:
    """Queryable interface over bundled SDTM-IG domain specifications.

    Loads domains.json once at init and exposes lookup methods that
    return Pydantic models. Used by mapping agents and validators
    to access SDTM structural requirements.
    """

    def __init__(self, data_path: str | Path | None = None) -> None:
        data_dir = Path(data_path) if data_path else _DEFAULT_DATA_DIR
        domains_file = data_dir / "domains.json"
        version_file = data_dir / "version.json"

        if not domains_file.exists():
            msg = f"SDTM-IG domains.json not found at {domains_file}"
            raise FileNotFoundError(msg)

        with open(domains_file) as f:
            raw_domains = json.load(f)

        with open(version_file) as f:
            version_info = json.load(f)

        # Build Pydantic models from raw JSON
        domains: dict[str, DomainSpec] = {}
        for code, data in raw_domains.items():
            variables = [VariableSpec(**v) for v in data["variables"]]
            domains[code] = DomainSpec(
                domain=data["domain"],
                description=data["description"],
                domain_class=DomainClass(data["domain_class"]),
                structure=data["structure"],
                variables=variables,
            )

        self._package = SDTMIGPackage(
            version=version_info["version"],
            domains=domains,
        )

    @property
    def version(self) -> str:
        """Return the SDTM-IG version string."""
        return self._package.version

    def get_domain_spec(self, domain: str) -> DomainSpec | None:
        """Return the full domain specification, or None if not found."""
        return self._package.domains.get(domain.upper())

    def get_required_variables(self, domain: str) -> list[str]:
        """Return names of Required (Req) variables for a domain."""
        spec = self.get_domain_spec(domain)
        if spec is None:
            return []
        return [v.name for v in spec.variables if v.core == CoreDesignation.REQ]

    def get_expected_variables(self, domain: str) -> list[str]:
        """Return names of Expected (Exp) variables for a domain."""
        spec = self.get_domain_spec(domain)
        if spec is None:
            return []
        return [v.name for v in spec.variables if v.core == CoreDesignation.EXP]

    def get_variable_spec(self, domain: str, variable: str) -> VariableSpec | None:
        """Return a single variable specification, or None if not found."""
        spec = self.get_domain_spec(domain)
        if spec is None:
            return None
        for v in spec.variables:
            if v.name == variable.upper():
                return v
        return None

    def list_domains(self) -> list[str]:
        """Return all available domain codes."""
        return sorted(self._package.domains.keys())

    def get_domain_class(self, domain: str) -> DomainClass | None:
        """Return the classification of a domain (Events, Findings, etc.)."""
        spec = self.get_domain_spec(domain)
        if spec is None:
            return None
        return spec.domain_class
