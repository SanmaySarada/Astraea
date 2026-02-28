"""Tests for NCI Controlled Terminology reference data lookup."""

import pytest

from astraea.models.controlled_terms import Codelist
from astraea.reference import CTReference, load_ct_reference


@pytest.fixture
def ct() -> CTReference:
    """Load CT reference from default bundled data."""
    return load_ct_reference()


class TestCTReference:
    """Tests for CTReference lookup class."""

    def test_version(self, ct: CTReference) -> None:
        assert ct.version == "2025-09-26"

    def test_ig_version(self, ct: CTReference) -> None:
        assert ct.ig_version == "3.4"

    def test_list_codelists_at_least_10(self, ct: CTReference) -> None:
        codes = ct.list_codelists()
        assert len(codes) >= 10

    def test_lookup_codelist_sex(self, ct: CTReference) -> None:
        cl = ct.lookup_codelist("C66731")
        assert cl is not None
        assert isinstance(cl, Codelist)
        assert cl.name == "Sex"
        assert "M" in cl.terms
        assert "F" in cl.terms
        assert "U" in cl.terms
        assert "UNDIFFERENTIATED" in cl.terms

    def test_lookup_codelist_nonexistent(self, ct: CTReference) -> None:
        assert ct.lookup_codelist("C99999") is None

    def test_validate_term_sex_valid(self, ct: CTReference) -> None:
        assert ct.validate_term("C66731", "M") is True
        assert ct.validate_term("C66731", "F") is True

    def test_validate_term_sex_invalid(self, ct: CTReference) -> None:
        assert ct.validate_term("C66731", "INVALID") is False
        assert ct.validate_term("C66731", "Male") is False  # must be submission value
        assert ct.validate_term("C66731", "m") is False  # case-sensitive

    def test_validate_term_nonexistent_codelist(self, ct: CTReference) -> None:
        assert ct.validate_term("C99999", "M") is False

    def test_is_extensible_sex_false(self, ct: CTReference) -> None:
        assert ct.is_extensible("C66731") is False

    def test_is_extensible_race_true(self, ct: CTReference) -> None:
        assert ct.is_extensible("C74457") is True

    def test_is_extensible_ethnicity_false(self, ct: CTReference) -> None:
        assert ct.is_extensible("C66790") is False

    def test_is_extensible_severity_false(self, ct: CTReference) -> None:
        assert ct.is_extensible("C66769") is False

    def test_is_extensible_route_true(self, ct: CTReference) -> None:
        assert ct.is_extensible("C66729") is True

    def test_is_extensible_unit_true(self, ct: CTReference) -> None:
        assert ct.is_extensible("C71620") is True

    def test_is_extensible_frequency_true(self, ct: CTReference) -> None:
        assert ct.is_extensible("C71113") is True

    def test_is_extensible_country_true(self, ct: CTReference) -> None:
        assert ct.is_extensible("ISO3166") is True

    def test_is_extensible_nonexistent_returns_false(self, ct: CTReference) -> None:
        assert ct.is_extensible("C99999") is False

    def test_validate_term_extensible_always_true(self, ct: CTReference) -> None:
        """Extensible codelists accept any value."""
        assert ct.validate_term("C66729", "ORAL") is True
        assert ct.validate_term("C66729", "CUSTOM_ROUTE") is True

    def test_get_codelist_for_variable_sex(self, ct: CTReference) -> None:
        cl = ct.get_codelist_for_variable("SEX")
        assert cl is not None
        assert cl.code == "C66731"

    def test_get_codelist_for_variable_case_insensitive(self, ct: CTReference) -> None:
        cl = ct.get_codelist_for_variable("sex")
        assert cl is not None
        assert cl.code == "C66731"

    def test_get_codelist_for_variable_race(self, ct: CTReference) -> None:
        cl = ct.get_codelist_for_variable("RACE")
        assert cl is not None
        assert cl.code == "C74457"

    def test_get_codelist_for_variable_ageu(self, ct: CTReference) -> None:
        cl = ct.get_codelist_for_variable("AGEU")
        assert cl is not None
        assert cl.code == "C66781"

    def test_get_codelist_for_variable_no_codelist(self, ct: CTReference) -> None:
        assert ct.get_codelist_for_variable("AETERM") is None

    def test_race_codelist_terms(self, ct: CTReference) -> None:
        cl = ct.lookup_codelist("C74457")
        assert cl is not None
        assert "WHITE" in cl.terms
        assert "ASIAN" in cl.terms
        assert "BLACK OR AFRICAN AMERICAN" in cl.terms

    def test_ethnicity_codelist_terms(self, ct: CTReference) -> None:
        cl = ct.lookup_codelist("C66790")
        assert cl is not None
        assert "HISPANIC OR LATINO" in cl.terms
        assert "NOT HISPANIC OR LATINO" in cl.terms

    def test_no_yes_response_terms(self, ct: CTReference) -> None:
        cl = ct.lookup_codelist("C66742")
        assert cl is not None
        assert "Y" in cl.terms
        assert "N" in cl.terms
        assert cl.extensible is False


class TestCodelistCCodesVerified:
    """Verify every codelist has the correct NCI C-code after the fix."""

    def test_race_code_is_c74457(self, ct: CTReference) -> None:
        cl = ct.lookup_codelist("C74457")
        assert cl is not None
        assert cl.name == "Race"
        assert cl.extensible is True

    def test_ethnicity_code_is_c66790(self, ct: CTReference) -> None:
        cl = ct.lookup_codelist("C66790")
        assert cl is not None
        assert cl.name == "Ethnicity"

    def test_ny_code_is_c66742(self, ct: CTReference) -> None:
        cl = ct.lookup_codelist("C66742")
        assert cl is not None
        assert cl.name == "No Yes Response"
        assert "Y" in cl.terms
        assert "N" in cl.terms

    def test_country_code_is_iso3166(self, ct: CTReference) -> None:
        cl = ct.lookup_codelist("ISO3166")
        assert cl is not None
        assert cl.name == "Country"

    def test_age_unit_code_is_c66781(self, ct: CTReference) -> None:
        cl = ct.lookup_codelist("C66781")
        assert cl is not None
        assert cl.name == "Age Unit"

    def test_route_code_is_c66729(self, ct: CTReference) -> None:
        cl = ct.lookup_codelist("C66729")
        assert cl is not None
        assert cl.name == "Route of Administration"

    def test_severity_code_is_c66769(self, ct: CTReference) -> None:
        cl = ct.lookup_codelist("C66769")
        assert cl is not None
        assert cl.name == "Severity/Intensity Scale for Adverse Events"

    def test_unit_code_is_c71620(self, ct: CTReference) -> None:
        cl = ct.lookup_codelist("C71620")
        assert cl is not None
        assert cl.name == "Unit"

    def test_frequency_code_is_c71113(self, ct: CTReference) -> None:
        cl = ct.lookup_codelist("C71113")
        assert cl is not None
        assert cl.name == "Frequency"

    def test_sex_code_unchanged_c66731(self, ct: CTReference) -> None:
        cl = ct.lookup_codelist("C66731")
        assert cl is not None
        assert cl.name == "Sex"

    def test_outcome_code_unchanged_c66768(self, ct: CTReference) -> None:
        cl = ct.lookup_codelist("C66768")
        assert cl is not None
        assert cl.name == "Outcome of Event"

    def test_old_wrong_codes_do_not_exist(self, ct: CTReference) -> None:
        """Verify that the OLD wrong codes no longer exist as codelist keys.

        Note: C66767, C66728, C66726, C66734 are now VALID codelists
        (added in Phase 3.1-01). Only C66770 was a truly wrong code.
        """
        assert ct.lookup_codelist("C66770") is None  # was Frequency (wrong)


class TestC66742Fix:
    """C66742 (No Yes Response) must have exactly N and Y -- no U term."""

    def test_c66742_has_no_u_term(self, ct: CTReference) -> None:
        cl = ct.lookup_codelist("C66742")
        assert cl is not None
        assert "U" not in cl.terms

    def test_c66742_has_exactly_n_and_y(self, ct: CTReference) -> None:
        cl = ct.lookup_codelist("C66742")
        assert cl is not None
        assert set(cl.terms.keys()) == {"N", "Y"}

    def test_c66742_is_non_extensible(self, ct: CTReference) -> None:
        cl = ct.lookup_codelist("C66742")
        assert cl is not None
        assert cl.extensible is False

    def test_c66742_validates_n_and_y(self, ct: CTReference) -> None:
        assert ct.validate_term("C66742", "N") is True
        assert ct.validate_term("C66742", "Y") is True

    def test_c66742_rejects_u(self, ct: CTReference) -> None:
        assert ct.validate_term("C66742", "U") is False


class TestNonExtensibleCodelists:
    """Non-extensible codelists must have COMPLETE term sets."""

    def test_c66767_action_taken(self, ct: CTReference) -> None:
        cl = ct.lookup_codelist("C66767")
        assert cl is not None
        assert cl.name == "Action Taken with Study Treatment"
        assert cl.extensible is False
        expected = {
            "DOSE NOT CHANGED",
            "DOSE REDUCED",
            "DOSE INCREASED",
            "DRUG INTERRUPTED",
            "DRUG WITHDRAWN",
            "NOT APPLICABLE",
            "UNKNOWN",
        }
        assert set(cl.terms.keys()) == expected

    def test_c66734_domain_abbreviation(self, ct: CTReference) -> None:
        cl = ct.lookup_codelist("C66734")
        assert cl is not None
        assert cl.name == "Domain Abbreviation"
        assert cl.extensible is False
        expected = {
            "AE",
            "CE",
            "CM",
            "CO",
            "DA",
            "DM",
            "DS",
            "DV",
            "EG",
            "EX",
            "FA",
            "IE",
            "LB",
            "MH",
            "PE",
            "QS",
            "SC",
            "SE",
            "SV",
            "TA",
            "TE",
            "TI",
            "TS",
            "TV",
            "VS",
        }
        assert set(cl.terms.keys()) == expected

    def test_c78736_reference_range_indicator(self, ct: CTReference) -> None:
        cl = ct.lookup_codelist("C78736")
        assert cl is not None
        assert cl.name == "Reference Range Indicator"
        assert cl.extensible is False
        expected = {"NORMAL", "HIGH", "LOW", "ABNORMAL", "HIGH HIGH", "LOW LOW"}
        assert set(cl.terms.keys()) == expected

    def test_c71148_position(self, ct: CTReference) -> None:
        cl = ct.lookup_codelist("C71148")
        assert cl is not None
        assert cl.name == "Position"
        assert cl.extensible is False
        expected = {"SITTING", "STANDING", "SUPINE"}
        assert set(cl.terms.keys()) == expected

    def test_c66728_relation_to_reference_period(self, ct: CTReference) -> None:
        cl = ct.lookup_codelist("C66728")
        assert cl is not None
        assert cl.name == "Relation to Reference Period"
        assert cl.extensible is False
        expected = {"BEFORE", "DURING", "DURING/AFTER", "AFTER", "ONGOING"}
        assert set(cl.terms.keys()) == expected


class TestExtensibleCodelists:
    """Extensible codelists must load and have minimum term counts."""

    @pytest.mark.parametrize(
        ("code", "name", "min_terms"),
        [
            ("C66727", "Disposition Event", 5),
            ("C65047", "Laboratory Test Code", 30),
            ("C67154", "Laboratory Test Name", 30),
            ("C66741", "Vital Signs Test Code", 5),
            ("C67153", "Vital Signs Test Name", 5),
            ("C71153", "ECG Test Code", 5),
            ("C71152", "ECG Test Name", 5),
            ("C66726", "Pharmaceutical Dosage Form", 5),
            ("C78734", "Specimen Type", 5),
            ("C99079", "Epoch", 5),
            ("C74456", "Anatomical Location", 5),
        ],
    )
    def test_extensible_codelist_loads(
        self, ct: CTReference, code: str, name: str, min_terms: int
    ) -> None:
        cl = ct.lookup_codelist(code)
        assert cl is not None, f"Codelist {code} ({name}) not found"
        assert cl.name == name
        assert cl.extensible is True
        assert len(cl.terms) >= min_terms, (
            f"Codelist {code} ({name}) has {len(cl.terms)} terms, expected >= {min_terms}"
        )


class TestAllSixteenCodelists:
    """Verify all 16 new codelists are loadable via CTReference."""

    ALL_NEW_CODES = [
        "C66767",
        "C66727",
        "C65047",
        "C67154",
        "C66741",
        "C67153",
        "C71153",
        "C71152",
        "C66726",
        "C66734",
        "C78736",
        "C78734",
        "C71148",
        "C66728",
        "C99079",
        "C74456",
    ]

    def test_none_missing(self, ct: CTReference) -> None:
        missing = [c for c in self.ALL_NEW_CODES if ct.lookup_codelist(c) is None]
        assert missing == [], f"Missing codelists: {missing}"

    def test_total_codelist_count(self, ct: CTReference) -> None:
        """30 total: 11 original + 16 new + 2 FDA compliance (C66785, C66789) + C66738."""
        assert len(ct.list_codelists()) == 30
