"""Integration tests for grading feedback tool with actual OpenAI API."""

import pytest
import asyncio
from pathlib import Path
import tempfile
import yaml

from shilads_helpers.libs.config_loader import load_all_configs
from shilads_helpers.tools.grading_feedback.grader import SubmissionGrader
from shilads_helpers.tools.grading_feedback.rubric_parser import RubricParser
from shilads_helpers.tools.grading_feedback.models import RubricCriterion


# Mark all tests in this file as integration tests
pytestmark = [pytest.mark.integration_test, pytest.mark.slow_integration_test]


class TestOpenAIIntegration:
    """Integration tests that call the actual OpenAI API."""

    def test_grade_simple_submission(self):
        """Test grading a simple submission with OpenAI."""
        # Create a simple rubric
        rubric_criteria = [
            RubricCriterion(
                name="Code Quality",
                max_points=2,
                criteria="Code is clean and follows best practices"
            ),
            RubricCriterion(
                name="Documentation",
                max_points=1,
                criteria="Code includes helpful comments"
            ),
            RubricCriterion(
                name="Functionality",
                max_points=2,
                criteria="Code works correctly and handles edge cases"
            )
        ]

        # Simple Python submission
        submission = """
def fibonacci(n):
    # Calculate the nth Fibonacci number
    if n <= 0:
        return 0
    elif n == 1:
        return 1
    else:
        return fibonacci(n-1) + fibonacci(n-2)

# Test the function
print(fibonacci(5))  # Output: 5
print(fibonacci(10)) # Output: 55
"""

        # Grade the submission
        config = load_all_configs()
        config = load_all_configs()
        grader = SubmissionGrader(configs=config, model="gpt-5-mini")  # Use cheaper model for tests
        result = grader.grade(submission, rubric_criteria)

        # Verify result structure
        assert result.total_score >= 0
        assert result.total_score <= 5
        assert result.max_score == 5

        # Check all components are present
        assert "Code Quality" in result.components
        assert "Documentation" in result.components
        assert "Functionality" in result.components

        # Check component scores are within bounds
        for name, feedback in result.components.items():
            assert feedback.score >= 0
            assert feedback.score <= feedback.max_score
            assert len(feedback.feedback) > 0  # Has feedback text

        # Check overall comment exists
        assert len(result.comment) > 0

    def test_grade_state_fair_submission(self):
        """Test grading a Tidy Tuesday State Fair submission."""
        # State Fair rubric
        rubric_content = """
| Component | Points | Criteria |
|-----------|--------|----------|
| Submission Present | 1 | Valid file submitted |
| Data Loading | 1 | Loads the Ferris wheel dataset |
| Visualization | 1 | Creates at least one plot |
| AI Statement | 1 | Includes AI usage statement describing if (and how) you used AI for your submission |
"""

        # Parse rubric
        parser = RubricParser()
        rubric_criteria = parser.parse(rubric_content)

        # Sample R submission
        submission = """
---
title: "Ferris Wheels Analysis"
---

# AI Statement
I did not use AI for any part of this assignment.

```r
library(tidyverse)
library(ggplot2)

# Load the data
wheels <- read_csv('https://raw.githubusercontent.com/rfordatascience/tidytuesday/main/data/2022/2022-08-09/wheels.csv')

# Create visualization
ggplot(wheels, aes(x = height, y = diameter)) +
  geom_point() +
  labs(title = "Ferris Wheel Heights vs Diameters")
```
"""

        # Grade the submission
        config = load_all_configs()
        config = load_all_configs()
        grader = SubmissionGrader(configs=config, model="gpt-5-mini")
        result = grader.grade(submission, rubric_criteria)
        print(result)

        # Should get high scores for this complete submission
        assert result.total_score >= 3  # Should get most points
        assert result.max_score == 4
        assert "Submission Present" in result.components
        assert "Data Loading" in result.components
        assert "Visualization" in result.components
        assert "AI Statement" in result.components

        # This submission should score well on all components
        assert result.components["Submission Present"].score > 0
        assert result.components["Data Loading"].score > 0
        assert result.components["Visualization"].score > 0
        assert result.components["AI Statement"].score > 0

    @pytest.mark.asyncio
    async def test_async_grading(self):
        """Test async grading functionality."""
        rubric_criteria = [
            RubricCriterion(
                name="Completeness",
                max_points=3,
                criteria="Assignment is complete"
            )
        ]

        submission = "This is a complete assignment with all required components."

        config = load_all_configs()
        config = load_all_configs()
        grader = SubmissionGrader(configs=config, model="gpt-5-mini")
        result = await grader.grade_async(submission, rubric_criteria)

        assert result.total_score >= 0
        assert result.max_score == 3
        assert "Completeness" in result.components

    def test_full_workflow_with_files(self):
        """Test the complete workflow with actual files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create rubric file
            rubric_file = tmpdir / "rubric.md"
            rubric_file.write_text("""
# Simple Rubric

| Component | Points | Description |
|-----------|--------|-------------|
| Implementation | 3 | Code correctly implements the feature |
| Style | 2 | Code follows style guidelines |
""")

            # Create submission file
            submission_file = tmpdir / "submission.py"
            submission_file.write_text("""
def hello_world():
    '''Print hello world message.'''
    print("Hello, World!")

if __name__ == "__main__":
    hello_world()
""")

            # Grade using file methods
            config = load_all_configs()
            grader = SubmissionGrader(configs=config, model="gpt-5-mini")
            result = grader.grade_submission_file(submission_file, rubric_file)

            # Verify results
            assert result.total_score >= 0
            assert result.max_score == 5
            assert "Implementation" in result.components
            assert "Style" in result.components

            # Save to YAML
            output_file = tmpdir / "feedback.yaml"
            with open(output_file, 'w') as f:
                yaml.dump(result.to_yaml_dict(), f)

            # Verify YAML was created
            assert output_file.exists()

            # Load and verify YAML structure
            with open(output_file) as f:
                loaded = yaml.safe_load(f)

            assert 'total_score' in loaded
            assert 'max_score' in loaded
            assert 'components' in loaded
            assert 'comment' in loaded

    def test_handles_api_errors_gracefully(self):
        """Test that API errors are handled gracefully."""
        # Use invalid API key to trigger error
        invalid_configs = {
            "openai": {
                "api_key": "invalid-key",
                "organization": "invalid-org"
            }
        }
        grader = SubmissionGrader(
            configs=invalid_configs,
            model="gpt-4"
        )

        rubric_criteria = [
            RubricCriterion(name="Test", max_points=1, criteria="Test criterion")
        ]

        # Should return error result, not crash
        result = grader.grade("Test submission", rubric_criteria)

        assert result.total_score == 0
        assert "error" in result.comment.lower() or "could not" in result.comment.lower()


# Helper to run integration tests only when explicitly requested
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test (requires API keys)"
    )