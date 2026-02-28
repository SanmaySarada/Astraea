"""Tests for derivation rule vocabulary in the LLM mapping prompt."""

from astraea.mapping.prompts import MAPPING_SYSTEM_PROMPT, MAPPING_USER_INSTRUCTIONS


# All 10 derivation rule keywords that the execution engine recognizes
DERIVATION_KEYWORDS = [
    "GENERATE_USUBJID",
    "CONCAT",
    "ISO8601_DATE",
    "ISO8601_DATETIME",
    "ISO8601_PARTIAL_DATE",
    "PARSE_STRING_DATE",
    "MIN_DATE_PER_SUBJECT",
    "MAX_DATE_PER_SUBJECT",
    "RACE_CHECKBOX",
    "NUMERIC_TO_YN",
]


class TestSystemPromptVocabulary:
    """Test that the system prompt contains the derivation rule vocabulary."""

    def test_system_prompt_contains_vocabulary_section(self) -> None:
        """System prompt must contain the Derivation Rule Vocabulary section."""
        assert "## Derivation Rule Vocabulary" in MAPPING_SYSTEM_PROMPT

    def test_system_prompt_contains_all_keywords(self) -> None:
        """System prompt must list all 10 recognized derivation keywords."""
        for keyword in DERIVATION_KEYWORDS:
            assert keyword in MAPPING_SYSTEM_PROMPT, (
                f"Missing keyword '{keyword}' in MAPPING_SYSTEM_PROMPT"
            )

    def test_system_prompt_contains_column_name_instruction(self) -> None:
        """System prompt must instruct LLM to use actual SAS column names."""
        assert "actual SAS column names" in MAPPING_SYSTEM_PROMPT

    def test_system_prompt_contains_reject_warning(self) -> None:
        """System prompt must warn that unrecognized rules will be rejected."""
        assert "reject any rule not in this list" in MAPPING_SYSTEM_PROMPT

    def test_system_prompt_contains_assign_direct_guidance(self) -> None:
        """System prompt must clarify that ASSIGN/DIRECT don't need derivation_rule."""
        assert "For ASSIGN and DIRECT patterns" in MAPPING_SYSTEM_PROMPT

    def test_system_prompt_contains_lookup_recode_guidance(self) -> None:
        """System prompt must clarify that LOOKUP_RECODE uses codelist_code."""
        assert "For LOOKUP_RECODE" in MAPPING_SYSTEM_PROMPT


class TestUserInstructionsVocabulary:
    """Test that user instructions reference the vocabulary."""

    def test_user_instructions_reference_vocabulary(self) -> None:
        """User instructions must reference the Derivation Rule Vocabulary."""
        assert "Derivation Rule Vocabulary" in MAPPING_USER_INSTRUCTIONS

    def test_user_instructions_no_vague_dsl_reference(self) -> None:
        """User instructions must not use the old vague 'pseudo-code DSL' phrasing."""
        assert "pseudo-code DSL" not in MAPPING_USER_INSTRUCTIONS
