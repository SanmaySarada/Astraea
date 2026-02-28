"""Tests for auto-fix CLI commands and display helpers.

Verifies:
- `astraea auto-fix` command help and error handling
- `astraea validate --auto-fix` flag appears in help
- display_fix_loop_result renders without errors
- display_needs_human renders without errors
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path

from typer.testing import CliRunner

from astraea.cli.app import app

runner = CliRunner()


def test_auto_fix_help() -> None:
    """auto-fix --help shows correct help text."""
    result = runner.invoke(app, ["auto-fix", "--help"])
    assert result.exit_code == 0
    assert "Auto-fix deterministic" in result.output


def test_validate_auto_fix_help() -> None:
    """validate --help includes --auto-fix option."""
    result = runner.invoke(app, ["validate", "--help"])
    assert result.exit_code == 0
    assert "--auto-fix" in result.output


def test_auto_fix_no_directory() -> None:
    """auto-fix with nonexistent path exits with code 1."""
    result = runner.invoke(app, ["auto-fix", "/nonexistent/path/xyz"])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def test_auto_fix_no_xpt_files(tmp_path: Path) -> None:
    """auto-fix with empty directory exits with code 1."""
    result = runner.invoke(app, ["auto-fix", str(tmp_path)])
    assert result.exit_code == 1
    assert "No .xpt files" in result.output


def test_display_fix_loop_result_renders() -> None:
    """display_fix_loop_result renders without exceptions."""
    from rich.console import Console

    from astraea.cli.display import display_fix_loop_result
    from astraea.validation.autofix import FixAction
    from astraea.validation.fix_loop import FixLoopResult, IterationResult
    from astraea.validation.report import ValidationReport

    # Build a minimal FixLoopResult
    report = ValidationReport.from_results("TEST", [], ["DM"])
    fix_action = FixAction(
        rule_id="ASTR-T002",
        domain="DM",
        variable="DOMAIN",
        fix_type="add_missing_column",
        before_value="Column missing",
        after_value="Added with value 'DM'",
        affected_count=10,
        timestamp="2026-02-28T00:00:00+00:00",
    )
    iteration = IterationResult(
        iteration=1,
        issues_found=5,
        auto_fixed=1,
        remaining_auto_fixable=0,
        needs_human=4,
        fix_actions=[fix_action],
    )
    result = FixLoopResult(
        iterations_run=1,
        max_iterations=3,
        converged=True,
        total_fixed=1,
        remaining_issues=[],
        needs_human_issues=[],
        all_fix_actions=[fix_action],
        iteration_details=[iteration],
        final_report=report,
    )

    output = StringIO()
    console = Console(file=output, force_terminal=True)
    display_fix_loop_result(result, console)

    text = output.getvalue()
    assert "Auto-Fix" in text
    assert "1" in text  # iterations
    assert "DM" in text  # domain in fix table


def test_display_needs_human_renders() -> None:
    """display_needs_human renders without exceptions."""
    from rich.console import Console

    from astraea.cli.display import display_needs_human
    from astraea.validation.autofix import (
        FixClassification,
        IssueClassification,
    )
    from astraea.validation.rules.base import RuleCategory, RuleResult, RuleSeverity

    issue = IssueClassification(
        result=RuleResult(
            rule_id="FDAB057",
            rule_description="TS domain must contain STUDYID parameter",
            category=RuleCategory.FDA_BUSINESS,
            severity=RuleSeverity.ERROR,
            passed=False,
            message="Missing required TS parameter STUDYID",
            domain="TS",
            variable=None,
            affected_count=1,
        ),
        classification=FixClassification.NEEDS_HUMAN,
        reason="FDA Business Rules require domain expertise",
        suggested_fix="Add STUDYID parameter to TS domain",
    )

    output = StringIO()
    console = Console(file=output, force_terminal=True)
    display_needs_human([issue], console)

    text = output.getvalue()
    assert "Human Review" in text
    assert "FDAB057" in text


def test_display_needs_human_empty() -> None:
    """display_needs_human with empty list shows no-issues message."""
    from rich.console import Console

    from astraea.cli.display import display_needs_human

    output = StringIO()
    console = Console(file=output, force_terminal=True)
    display_needs_human([], console)

    text = output.getvalue()
    assert "No issues" in text
