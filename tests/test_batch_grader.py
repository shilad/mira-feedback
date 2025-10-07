"""Tests for batch grading functionality."""

import pytest
import asyncio
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock

from mira.tools.grading_feedback.batch_grader import BatchGrader, BatchGradingResult
from mira.tools.grading_feedback.models import (
    GradingResult, ComponentFeedback, RubricCriterion
)


@pytest.fixture
def sample_config():
    """Create sample configuration."""
    return {
        'tools': {
            'max_threads': 2
        },
        'openai': {
            'api_key': 'test-key',
            'model': 'gpt-4'
        }
    }


@pytest.fixture
def sample_rubric():
    """Create sample rubric criteria."""
    return [
        RubricCriterion(name="Code Quality", max_points=30, criteria="Clean, readable code"),
        RubricCriterion(name="Functionality", max_points=50, criteria="Works correctly"),
        RubricCriterion(name="Documentation", max_points=20, criteria="Well documented")
    ]


@pytest.fixture
def sample_grading_result():
    """Create sample grading result."""
    return GradingResult(
        total_score=85,
        max_score=100,
        components={
            "Code Quality": ComponentFeedback(score=25, max_score=30, feedback="Good structure"),
            "Functionality": ComponentFeedback(score=45, max_score=50, feedback="Works well"),
            "Documentation": ComponentFeedback(score=15, max_score=20, feedback="Could be better")
        },
        comment="Overall good work"
    )


def test_batch_grader_initialization(sample_config):
    """Test BatchGrader initialization."""
    grader = BatchGrader(configs=sample_config, max_concurrent=4)
    assert grader.max_concurrent == 4
    assert grader.configs == sample_config


def test_batch_grader_uses_config_threads(sample_config):
    """Test that BatchGrader uses thread count from config."""
    grader = BatchGrader(configs=sample_config)
    assert grader.max_concurrent == 2  # From config


def test_find_submission_directories():
    """Test finding submission directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create submission directories with files
        (tmpdir / "student1").mkdir()
        (tmpdir / "student1" / "main.py").write_text("print('hello')")

        (tmpdir / "student2").mkdir()
        (tmpdir / "student2" / "solution.java").write_text("class Solution {}")

        # Create non-submission directories
        (tmpdir / "__pycache__").mkdir()
        (tmpdir / ".git").mkdir()
        (tmpdir / "empty_dir").mkdir()

        grader = BatchGrader(configs={'tools': {'max_threads': 1}})  # Still uses max_threads from config
        dirs = grader.find_submission_directories(tmpdir)

        assert len(dirs) == 2
        assert tmpdir / "student1" in dirs
        assert tmpdir / "student2" in dirs
        assert tmpdir / "__pycache__" not in dirs
        assert tmpdir / ".git" not in dirs
        assert tmpdir / "empty_dir" not in dirs


def test_batch_grading_result_to_dict():
    """Test BatchGradingResult to_dict conversion."""
    result = BatchGradingResult(
        submission_dir="/path/to/submission",
        student_id="student1",
        total_score=85,
        max_score=100,
        success=True,
        grading_result=GradingResult(
            total_score=85,
            max_score=100,
            components={
                "Test": ComponentFeedback(score=85, max_score=100, feedback="Good")
            },
            comment="Nice work"
        )
    )

    data = result.to_dict()
    assert data['submission_dir'] == "/path/to/submission"
    assert data['student_id'] == "student1"
    assert data['total_score'] == 85
    assert data['max_score'] == 100
    assert data['success'] is True
    assert 'components' in data
    assert 'comment' in data
    assert data['comment'] == "Nice work"


def test_batch_grading_result_with_error():
    """Test BatchGradingResult with error."""
    result = BatchGradingResult(
        submission_dir="/path/to/submission",
        student_id="student1",
        total_score=0,
        max_score=100,
        success=False,
        error_message="Failed to grade"
    )

    data = result.to_dict()
    assert data['success'] is False
    assert data['error_message'] == "Failed to grade"
    assert 'components' not in data


@pytest.mark.asyncio
@patch('mira.tools.grading_feedback.batch_grader.SubmissionGrader')
async def test_grade_single_submission_async(mock_grader_class, sample_config, sample_rubric, sample_grading_result):
    """Test grading a single submission asynchronously."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create submission
        submission_dir = tmpdir / "student1"
        submission_dir.mkdir()
        (submission_dir / "main.py").write_text("def hello(): return 'world'")

        # Setup mocks
        mock_grader = AsyncMock()
        mock_grader.grade_async.return_value = sample_grading_result
        mock_grader_class.return_value = mock_grader

        # Create batch grader
        batch_grader = BatchGrader(configs=sample_config)

        # Grade submission
        result = await batch_grader._grade_single_submission_async(
            submission_dir, sample_rubric, "feedback.yaml"
        )

        # Check result
        assert result.success is True
        assert result.student_id == "student1"
        assert result.total_score == 85
        assert result.max_score == 100

        # Check feedback file was created
        feedback_file = submission_dir / "feedback.yaml"
        assert feedback_file.exists()

        # Check feedback content
        with open(feedback_file) as f:
            feedback_data = yaml.safe_load(f)
        assert feedback_data['total_score'] == 85


@pytest.mark.asyncio
@patch('mira.tools.grading_feedback.batch_grader.SubmissionGrader')
async def test_grade_single_submission_error_async(mock_grader_class, sample_config, sample_rubric):
    """Test handling error in single submission grading."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create submission
        submission_dir = tmpdir / "student1"
        submission_dir.mkdir()
        (submission_dir / "main.py").write_text("def hello(): return 'world'")

        # Setup mock to raise error
        mock_grader = AsyncMock()
        mock_grader.grade_async.side_effect = Exception("API error")
        mock_grader_class.return_value = mock_grader

        # Create batch grader
        batch_grader = BatchGrader(configs=sample_config)

        # Grade submission
        result = await batch_grader._grade_single_submission_async(
            submission_dir, sample_rubric, "feedback.yaml"
        )

        # Check error result
        assert result.success is False
        assert result.student_id == "student1"
        assert "API error" in result.error_message
        assert result.total_score == 0


@patch('mira.tools.grading_feedback.batch_grader.SubmissionGrader')
@patch('mira.tools.grading_feedback.batch_grader.RubricParser')
def test_grade_all_submissions_sync(mock_parser_class, mock_grader_class,
                                   sample_config, sample_rubric, sample_grading_result):
    """Test grading all submissions using the sync wrapper."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create rubric file
        rubric_path = tmpdir / "rubric.md"
        rubric_path.write_text("# Rubric\n| Criterion | Points |\n|---|---|\n| Test | 100 |")

        # Create submissions
        for i in range(3):
            student_dir = tmpdir / f"student{i}"
            student_dir.mkdir()
            (student_dir / "main.py").write_text(f"print({i})")

        # Setup mocks
        mock_parser = Mock()
        mock_parser.parse_file.return_value = sample_rubric
        mock_parser_class.return_value = mock_parser

        mock_grader = AsyncMock()
        mock_grader.grade_async.return_value = sample_grading_result
        mock_grader_class.return_value = mock_grader

        # Create batch grader
        batch_grader = BatchGrader(configs=sample_config, max_concurrent=2)

        # Grade all submissions (using sync wrapper)
        results = batch_grader.grade_all_submissions(
            submissions_dir=tmpdir,
            rubric_path=rubric_path
        )

        # Check results
        assert len(results) == 3
        assert all(r.success for r in results)
        assert all(r.total_score == 85 for r in results)


def test_save_summary():
    """Test saving grading summary to YAML."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create results
        results = [
            BatchGradingResult(
                submission_dir="/path/student1",
                student_id="student1",
                total_score=85,
                max_score=100,
                success=True
            ),
            BatchGradingResult(
                submission_dir="/path/student2",
                student_id="student2",
                total_score=75,
                max_score=100,
                success=True
            ),
            BatchGradingResult(
                submission_dir="/path/student3",
                student_id="student3",
                total_score=0,
                max_score=100,
                success=False,
                error_message="Failed"
            )
        ]

        # Save summary
        grader = BatchGrader(configs={'tools': {'max_threads': 1}})  # Still uses max_threads from config
        summary_path = tmpdir / "summary.yaml"
        grader.save_summary(results, summary_path)

        # Check file exists
        assert summary_path.exists()

        # Load and check content
        with open(summary_path) as f:
            data = yaml.safe_load(f)

        assert data['grading_summary']['total_submissions'] == 3
        assert data['grading_summary']['successful'] == 2
        assert data['grading_summary']['failed'] == 1
        assert data['grading_summary']['average_score'] == 80  # (85+75)/2
        assert len(data['submissions']) == 3