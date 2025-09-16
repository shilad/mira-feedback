"""Unit tests for the grading feedback tool."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from shilads_helpers.tools.grading_feedback.models import (
    RubricCriterion, ComponentFeedback, GradingResult
)
from shilads_helpers.tools.grading_feedback.rubric_parser import RubricParser
from shilads_helpers.tools.grading_feedback.grader import SubmissionGrader


class TestModels:
    """Test Pydantic models."""

    def test_rubric_criterion(self):
        """Test RubricCriterion model."""
        criterion = RubricCriterion(
            name="Code Quality",
            max_points=5.0,
            criteria="Code is clean and well-documented"
        )
        assert criterion.name == "Code Quality"
        assert criterion.max_points == 5.0
        assert criterion.criteria == "Code is clean and well-documented"

    def test_component_feedback(self):
        """Test ComponentFeedback model."""
        feedback = ComponentFeedback(
            score=4.5,
            max_score=5.0,
            feedback="Good code structure, minor issues with comments"
        )
        assert feedback.score == 4.5
        assert feedback.max_score == 5.0
        assert feedback.feedback == "Good code structure, minor issues with comments"

    def test_grading_result(self):
        """Test GradingResult model."""
        result = GradingResult(
            total_score=8.5,
            max_score=10.0,
            components={
                "Code Quality": ComponentFeedback(
                    score=4.5,
                    max_score=5.0,
                    feedback="Good structure"
                ),
                "Testing": ComponentFeedback(
                    score=4.0,
                    max_score=5.0,
                    feedback="Comprehensive tests"
                )
            },
            comment="Overall good work with minor improvements needed"
        )
        assert result.total_score == 8.5
        assert result.max_score == 10.0
        assert len(result.components) == 2
        assert result.components["Code Quality"].score == 4.5

    def test_grading_result_to_yaml_dict(self):
        """Test conversion to YAML-friendly dictionary."""
        result = GradingResult(
            total_score=3.0,
            max_score=4.0,
            components={
                "Submission": ComponentFeedback(score=1, max_score=1, feedback="Present"),
                "Data": ComponentFeedback(score=1, max_score=1, feedback="Loaded"),
                "Viz": ComponentFeedback(score=1, max_score=1, feedback="Created"),
                "AI": ComponentFeedback(score=0, max_score=1, feedback="Missing")
            },
            comment="Good work, missing AI statement"
        )

        yaml_dict = result.to_yaml_dict()
        assert yaml_dict['total_score'] == 3.0
        assert yaml_dict['max_score'] == 4.0
        assert yaml_dict['components']['Submission']['score'] == 1
        assert yaml_dict['components']['AI']['feedback'] == "Missing"
        assert yaml_dict['comment'] == "Good work, missing AI statement"


class TestRubricParser:
    """Test rubric parsing functionality."""

    def test_parse_table_format(self):
        """Test parsing table format rubric."""
        rubric_content = """
# Assignment Rubric

| Component | Points | Criteria |
|-----------|--------|----------|
| Code Quality | 5 | Clean, readable code with proper documentation |
| Testing | 3 | Includes comprehensive unit tests |
| Performance | 2 | Efficient algorithm implementation |
"""
        parser = RubricParser()
        criteria = parser.parse(rubric_content)

        assert len(criteria) == 3
        assert criteria[0].name == "Code Quality"
        assert criteria[0].max_points == 5
        assert "Clean, readable code" in criteria[0].criteria
        assert criteria[1].name == "Testing"
        assert criteria[1].max_points == 3
        assert criteria[2].name == "Performance"
        assert criteria[2].max_points == 2

    def test_parse_list_format(self):
        """Test parsing bullet list format rubric."""
        rubric_content = """
# Grading Criteria

- Code Quality (5 points): Clean, readable code with documentation
- Testing (3 points): Comprehensive unit tests
- Performance (2 points): Efficient implementation
"""
        parser = RubricParser()
        criteria = parser.parse(rubric_content)

        assert len(criteria) == 3
        assert criteria[0].name == "Code Quality"
        assert criteria[0].max_points == 5
        assert criteria[1].name == "Testing"
        assert criteria[1].max_points == 3

    def test_parse_header_format(self):
        """Test parsing header-based format rubric."""
        rubric_content = """
## Code Quality (5 points)
The code should be clean, readable, and well-documented.

## Testing (3 points)
Include comprehensive unit tests covering edge cases.

## Performance (2 points)
Implement an efficient algorithm with good time complexity.
"""
        parser = RubricParser()
        criteria = parser.parse(rubric_content)

        assert len(criteria) == 3
        assert criteria[0].name == "Code Quality"
        assert criteria[0].max_points == 5
        assert "clean, readable" in criteria[0].criteria
        assert criteria[1].name == "Testing"
        assert criteria[1].max_points == 3

    def test_parse_decimal_points(self):
        """Test parsing rubric with decimal points."""
        rubric_content = """
| Component | Points |
|-----------|--------|
| Analysis | 2.5 |
| Presentation | 1.5 |
"""
        parser = RubricParser()
        criteria = parser.parse(rubric_content)

        assert len(criteria) == 2
        assert criteria[0].max_points == 2.5
        assert criteria[1].max_points == 1.5

    def test_parse_skip_total_row(self):
        """Test that parser skips total rows."""
        rubric_content = """
| Component | Points |
|-----------|--------|
| Task 1 | 3 |
| Task 2 | 2 |
| Total | 5 |
"""
        parser = RubricParser()
        criteria = parser.parse(rubric_content)

        assert len(criteria) == 2  # Should skip the Total row
        assert criteria[0].name == "Task 1"
        assert criteria[1].name == "Task 2"

    def test_parse_invalid_format_raises_error(self):
        """Test that invalid format raises error."""
        rubric_content = """
This is not a valid rubric format.
No tables, lists, or headers with points.
"""
        parser = RubricParser()
        with pytest.raises(ValueError, match="Could not parse rubric"):
            parser.parse(rubric_content)


class TestSubmissionGrader:
    """Test the submission grader (mocked, no API calls)."""

    def test_grader_initialization_with_config(self):
        config = {
            "openai": {
                "api_key": "test-key",
                "organization": "test-org",
                "model": "gpt-4"
            }
        }

        grader = SubmissionGrader(configs=config)
        # Model will be set from config or fallback to o1-preview
        assert grader.agent is not None

    def test_grader_initialization_with_params(self):
        """Test grader initialization with explicit configs."""
        test_configs = {
            "openai": {
                "api_key": "test-key",
                "organization": "test-org"
            }
        }
        grader = SubmissionGrader(
            configs=test_configs,
            model="gpt-3.5-turbo"
        )
        assert grader.model_name == "gpt-3.5-turbo"
        assert grader.agent is not None

    def test_build_prompt(self):
        """Test prompt building."""
        test_configs = {"openai": {"api_key": "test", "organization": "test", "model": "gpt-4"}}
        grader = SubmissionGrader(configs=test_configs)
        criteria = [
            RubricCriterion(name="Code", max_points=5, criteria="Clean code"),
            RubricCriterion(name="Tests", max_points=3, criteria="Has tests")
        ]

        prompt = grader._build_prompt("My submission code", criteria)

        assert "Code (5.0 points): Clean code" in prompt
        assert "Tests (3.0 points): Has tests" in prompt
        assert "My submission code" in prompt
        assert '"Code"' in prompt and '"Tests"' in prompt

    def test_create_error_result(self):
        """Test error result creation."""
        test_configs = {"openai": {"api_key": "test", "organization": "test", "model": "gpt-4"}}
        grader = SubmissionGrader(configs=test_configs)
        criteria = [
            RubricCriterion(name="Code", max_points=5, criteria="Clean code"),
            RubricCriterion(name="Tests", max_points=3, criteria="Has tests")
        ]

        result = grader._create_error_result(criteria, "API error")

        assert result.total_score == 0
        assert result.max_score == 8
        assert "Code" in result.components
        assert "Tests" in result.components
        assert result.components["Code"].score == 0
        assert "API error" in result.comment


class TestCLI:
    """Test CLI functionality."""

    def test_find_all_submission_files(self):
        """Test finding submission files."""
        from shilads_helpers.tools.grading_feedback.submission_utils import find_all_submission_files

        # Create a temporary directory with files
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create submission files
            submission1 = tmpdir / "submission.py"
            submission1.write_text("print('hello')")
            submission2 = tmpdir / "TidyTuesday.Rmd"
            submission2.write_text("# R code")

            # Find submission files
            found = find_all_submission_files(tmpdir)

            # Should find both files
            assert len(found) == 2
            file_names = [f[0].name for f in found]
            assert "submission.py" in file_names
            assert "TidyTuesday.Rmd" in file_names

    def test_find_all_submission_files_skips_feedback(self):
        """Test that feedback files are skipped."""
        from shilads_helpers.tools.grading_feedback.submission_utils import find_all_submission_files

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create various files
            submission = tmpdir / "submission.py"
            submission.write_text("print('hello')")
            feedback = tmpdir / "grading_feedback.yaml"
            feedback.write_text("feedback: test")
            rubric = tmpdir / "rubric.md"
            rubric.write_text("# Rubric")

            # Find submission files
            found = find_all_submission_files(tmpdir)

            # Should find submission but not feedback or rubric
            assert len(found) == 1
            assert found[0][0].name == "submission.py"