"""Tests for the classify CLI command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from astraea.cli.app import app
from astraea.models.classification import (
    ClassificationResult,
    DomainClassification,
    DomainPlan,
    HeuristicScore,
)

runner = CliRunner()


def _make_classification_result() -> ClassificationResult:
    """Create a sample classification result for testing."""
    return ClassificationResult(
        classifications=[
            DomainClassification(
                raw_dataset="ae.sas7bdat",
                primary_domain="AE",
                secondary_domains=["SUPPAE"],
                confidence=0.95,
                reasoning="Filename and variables strongly match Adverse Events domain",
                heuristic_scores=[
                    HeuristicScore(
                        domain="AE", score=0.92, signals=["filename exact match"]
                    )
                ],
            ),
            DomainClassification(
                raw_dataset="dm.sas7bdat",
                primary_domain="DM",
                secondary_domains=[],
                confidence=0.90,
                reasoning="Demographics domain based on variable names",
                heuristic_scores=[
                    HeuristicScore(
                        domain="DM", score=0.88, signals=["filename exact match"]
                    )
                ],
            ),
            DomainClassification(
                raw_dataset="irt.sas7bdat",
                primary_domain="UNCLASSIFIED",
                secondary_domains=[],
                confidence=0.2,
                reasoning="No matching SDTM domain found",
                heuristic_scores=[],
            ),
        ],
        domain_plans=[
            DomainPlan(
                domain="AE",
                source_datasets=["ae.sas7bdat"],
                mapping_pattern="direct",
                notes="",
            ),
            DomainPlan(
                domain="DM",
                source_datasets=["dm.sas7bdat"],
                mapping_pattern="direct",
                notes="",
            ),
            DomainPlan(
                domain="LB",
                source_datasets=[
                    "lb_biochem.sas7bdat",
                    "lb_hem.sas7bdat",
                    "lb_urin.sas7bdat",
                ],
                mapping_pattern="mixed",
                notes="",
            ),
        ],
        unclassified_datasets=["irt.sas7bdat"],
    )


class TestClassifyCommand:
    def test_help_shows_description(self) -> None:
        result = runner.invoke(app, ["classify", "--help"])
        assert result.exit_code == 0
        assert "classify" in result.output.lower() or "SDTM" in result.output

    def test_missing_dir_exits_nonzero(self) -> None:
        result = runner.invoke(app, ["classify", "/nonexistent/path/"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "Error" in result.output

    def test_empty_dir_exits_nonzero(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["classify", str(tmp_path)])
        assert result.exit_code != 0
        assert "No .sas7bdat" in result.output

    def test_no_api_key_exits_nonzero(self) -> None:
        import os

        env = os.environ.copy()
        env.pop("ANTHROPIC_API_KEY", None)
        with patch.dict("os.environ", env, clear=True):
            result = runner.invoke(app, ["classify", "Fakedata/"])
            assert result.exit_code != 0
            assert "ANTHROPIC_API_KEY" in result.output

    @patch("astraea.classification.classifier.classify_all")
    @patch("astraea.profiling.profiler.profile_dataset")
    @patch("astraea.io.sas_reader.read_all_sas_files")
    def test_successful_classify_shows_table(
        self,
        mock_read: MagicMock,
        mock_profile: MagicMock,
        mock_classify: MagicMock,
        tmp_path: Path,
    ) -> None:
        sas_file = tmp_path / "ae.sas7bdat"
        sas_file.write_bytes(b"fake")

        mock_read.return_value = {"ae.sas7bdat": (MagicMock(), MagicMock())}
        mock_profile.return_value = MagicMock(filename="ae.sas7bdat")
        mock_classify.return_value = _make_classification_result()

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}):
            result = runner.invoke(app, ["classify", str(tmp_path)])

        assert result.exit_code == 0
        assert "AE" in result.output
        assert "DM" in result.output
        assert "UNCLASSIFIED" in result.output

    @patch("astraea.classification.classifier.classify_all")
    @patch("astraea.profiling.profiler.profile_dataset")
    @patch("astraea.io.sas_reader.read_all_sas_files")
    def test_classify_shows_merge_groups(
        self,
        mock_read: MagicMock,
        mock_profile: MagicMock,
        mock_classify: MagicMock,
        tmp_path: Path,
    ) -> None:
        sas_file = tmp_path / "ae.sas7bdat"
        sas_file.write_bytes(b"fake")

        mock_read.return_value = {"ae.sas7bdat": (MagicMock(), MagicMock())}
        mock_profile.return_value = MagicMock(filename="ae.sas7bdat")
        mock_classify.return_value = _make_classification_result()

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}):
            result = runner.invoke(app, ["classify", str(tmp_path)])

        assert result.exit_code == 0
        assert "Merge Groups" in result.output
        assert "LB" in result.output

    @patch("astraea.classification.classifier.classify_all")
    @patch("astraea.profiling.profiler.profile_dataset")
    @patch("astraea.io.sas_reader.read_all_sas_files")
    def test_output_flag_writes_json(
        self,
        mock_read: MagicMock,
        mock_profile: MagicMock,
        mock_classify: MagicMock,
        tmp_path: Path,
    ) -> None:
        sas_file = tmp_path / "ae.sas7bdat"
        sas_file.write_bytes(b"fake")
        output_file = tmp_path / "result.json"

        mock_read.return_value = {"ae.sas7bdat": (MagicMock(), MagicMock())}
        mock_profile.return_value = MagicMock(filename="ae.sas7bdat")
        mock_classify.return_value = _make_classification_result()

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}):
            result = runner.invoke(
                app, ["classify", str(tmp_path), "--output", str(output_file)]
            )

        assert result.exit_code == 0
        assert output_file.exists()
        assert "AE" in output_file.read_text()

    def test_cache_dir_loads_cached(self, tmp_path: Path) -> None:
        sas_file = tmp_path / "ae.sas7bdat"
        sas_file.write_bytes(b"fake")

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        cache_file = cache_dir / "classification.json"
        classification = _make_classification_result()
        cache_file.write_text(classification.model_dump_json(indent=2))

        result = runner.invoke(
            app, ["classify", str(tmp_path), "--cache-dir", str(cache_dir)]
        )

        assert result.exit_code == 0
        assert "cached" in result.output.lower() or "Loading" in result.output
        assert "AE" in result.output
