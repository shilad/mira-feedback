"""OpenAI-based grader using pydantic-ai for structured output."""

import asyncio
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

from shilads_helpers.libs.config_loader import ConfigType
from shilads_helpers.libs.llm import create_agent
from .models import RubricCriterion, ComponentFeedback, GradingResult
from .rubric_parser import RubricParser

LOG = logging.getLogger(__name__)


def create_grading_agent(configs: ConfigType,
                         model: Optional[str] = None,
                         settings_dict: Optional[Dict[str, Any]] = None) -> Any:
    """
    Create a pydantic-ai Agent configured for grading with OpenAI models.

    This is a wrapper around the general create_agent function with a grading-specific prompt.

    Args:
        configs: Configuration dictionary (required)
        model: Model to use (overrides config value)
        settings_dict: Pydantic AI settings dict (overrides config values)

    Returns:
        Configured Agent for grading
    """
    system_prompt = (
        "You are a helpful grading assistant. Evaluate student submissions "
        "against the provided rubric criteria. Be fair, constructive, and specific "
        "in your feedback. Award partial credit where appropriate."
    )

    return create_agent(
        configs=configs,
        model=model,
        settings_dict=settings_dict,
        system_prompt=system_prompt
    )


class SubmissionGrader:
    """Grade submissions using OpenAI with structured output."""

    def __init__(self, configs: ConfigType,
                 model: Optional[str] = None, settings: Optional[Dict[str, Any]] = None):
        """
        Initialize the grader.

        Args:
            configs: Configuration dictionary (required)
            model: Model to use (overrides config value)
            settings: Pydantic AI settings dict (overrides config values)
        """
        self.configs = configs

        # Store model and settings for later use
        self.model_name = model
        self.settings = settings

        # Create the main grading agent using the factory function
        self.agent = create_grading_agent(
            configs=self.configs,
            model=model,
            settings_dict=settings
        )

    async def grade_async(self, submission_content: str, rubric_criteria: List[RubricCriterion]) -> GradingResult:
        """
        Grade a submission asynchronously.

        Args:
            submission_content: The student's submission text
            rubric_criteria: List of rubric criteria to evaluate against

        Returns:
            GradingResult with scores and feedback
        """
        # Build the grading prompt
        prompt = self._build_prompt(submission_content, rubric_criteria)

        try:
            # Run the agent to get response
            # Settings are already configured in the agent creation
            result = await self.agent.run(prompt)

            # Parse the response to create GradingResult
            # Extract the actual output from the AgentRunResult
            if hasattr(result, 'output'):
                response_text = str(result.output)
            elif hasattr(result, 'data'):
                response_text = str(result.data)
            else:
                response_text = str(result)

            # Try to extract structured data from the response
            import json
            import re

            # Look for JSON in the response
            json_match = re.search(r'{.*}', response_text, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())

                    # Convert to GradingResult
                    components = {}
                    for name, info in data.get('components', {}).items():
                        components[name] = ComponentFeedback(
                            score=info.get('score', 0),
                            max_score=info.get('max_score', 0),
                            feedback=info.get('feedback', '')
                        )

                    return GradingResult(
                        total_score=data.get('total_score', 0),
                        max_score=data.get('max_score', sum(c.max_points for c in rubric_criteria)),
                        components=components,
                        comment=data.get('comment', '')
                    )
                except json.JSONDecodeError:
                    pass

            # If we can't parse JSON, create a basic result
            LOG.warning("Could not parse structured response, creating basic result")
            return self._create_basic_result(rubric_criteria, response_text)

        except Exception as e:
            import traceback
            LOG.error(f"Error during grading: {e}: " + traceback.format_exc())
            # Return a default result on error
            return self._create_error_result(rubric_criteria, str(e))

    def grade(self, submission_content: str, rubric_criteria: List[RubricCriterion]) -> GradingResult:
        """
        Grade a submission synchronously.

        Args:
            submission_content: The student's submission text
            rubric_criteria: List of rubric criteria to evaluate against

        Returns:
            GradingResult with scores and feedback
        """
        return asyncio.run(self.grade_async(submission_content, rubric_criteria))

    async def select_files_for_review_async(self, summary: str, rubric_criteria: List[RubricCriterion]) -> List[str]:
        """
        Ask LLM to select which files to review based on submission summary and rubric.

        Args:
            summary: Summary of submission structure with file sizes
            rubric_criteria: List of rubric criteria

        Returns:
            List of file paths to review
        """
        criteria_text = "\n".join([
            f"- {c.name} ({c.max_points} points): {c.criteria}"
            for c in rubric_criteria
        ])

        prompt = f"""You are reviewing a student submission directory structure to decide which files to grade.

RUBRIC CRITERIA:
{criteria_text}

SUBMISSION STRUCTURE:
{summary}

Based on the rubric criteria and the submission structure above, select which files should be reviewed for grading.
Focus on files that are most relevant to the rubric criteria.

Return ONLY a JSON list of filenames that should be reviewed. For example:
["main.py", "test.py", "README.md"]

Include only the files most relevant to grading. Prioritize:
1. Main implementation files
2. Test files (if testing is in the rubric)
3. Documentation (if documentation is in the rubric)
4. Configuration/data files only if necessary

Return ONLY the JSON list, no other text."""

        try:
            # Create a separate agent for file selection that returns plain text
            import json

            # Use the factory function to create a properly configured agent
            file_selection_agent = create_grading_agent(
                configs=self.configs,
                model=self.model_name,
                settings_dict=self.settings
            )

            result = await file_selection_agent.run(prompt)

            # Parse the JSON response from the text
            # Extract the actual output from the AgentRunResult
            if hasattr(result, 'output'):
                response_text = str(result.output)
            elif hasattr(result, 'data'):
                response_text = str(result.data)
            else:
                response_text = str(result)

            # Extract JSON from the response
            import re
            json_match = re.search(r'\[.*?\]', response_text, re.DOTALL)
            if json_match:
                file_list = json.loads(json_match.group())
                if isinstance(file_list, list):
                    return file_list

            LOG.warning("Could not parse file selection response, using all files")
            return []
        except Exception as e:
            LOG.error(f"Error selecting files: {e}")
            return []

    def select_files_for_review(self, summary: str, rubric_criteria: List[RubricCriterion]) -> List[str]:
        """
        Synchronous wrapper for file selection.

        Args:
            summary: Summary of submission structure with file sizes
            rubric_criteria: List of rubric criteria

        Returns:
            List of file paths to review
        """
        return asyncio.run(self.select_files_for_review_async(summary, rubric_criteria))

    def grade_submission_file(self, submission_path: Path, rubric_path: Path) -> GradingResult:
        """
        Grade a submission file against a rubric file.

        Args:
            submission_path: Path to the submission file
            rubric_path: Path to the rubric markdown file

        Returns:
            GradingResult with scores and feedback
        """
        # Parse rubric
        parser = RubricParser()
        rubric_criteria = parser.parse_file(rubric_path)

        # Read submission
        try:
            submission_content = submission_path.read_text(encoding='utf-8', errors='ignore')
        except Exception as e:
            LOG.error(f"Error reading submission file: {e}")
            return self._create_error_result(rubric_criteria, f"Could not read submission: {e}")

        # Grade the submission
        return self.grade(submission_content, rubric_criteria)

    def _build_prompt(self, submission: str, criteria: List[RubricCriterion]) -> str:
        """Build the grading prompt with rubric criteria."""
        criteria_text = "\n".join([
            f"- {c.name} ({c.max_points} points): {c.criteria}"
            for c in criteria
        ])

        return f"""Grade this student submission according to the following rubric:

RUBRIC CRITERIA:
{criteria_text}

INSTRUCTIONS:
1. Evaluate the submission against each criterion
2. Assign a score from 0 to the maximum points for each criterion
3. Provide specific, constructive feedback when a criterion is not fully met
4. Write an overall comment summarizing the student's performance
5. All comments should be very brief.

Return your evaluation as a JSON object with this structure:
{{
    "total_score": <sum of all component scores>,
    "max_score": {sum(c.max_points for c in criteria)},
    "components": {{
        {', '.join([f'"{c.name}": {{"score": <0-{c.max_points}>, "max_score": {c.max_points}, "feedback": "<specific feedback>"}}'
                   for c in criteria])}
    }},
    "comment": "<overall feedback comment for the student>"
}}

STUDENT SUBMISSION:
{submission}"""

    def _create_basic_result(self, criteria: List[RubricCriterion], response_text: str) -> GradingResult:
        """Create a basic result when structured parsing fails."""
        components = {}
        # Give partial credit when we can't parse the response
        for criterion in criteria:
            components[criterion.name] = ComponentFeedback(
                score=criterion.max_points * 0.5,  # Default to 50% credit
                max_score=criterion.max_points,
                feedback="Automated evaluation - please review manually"
            )

        return GradingResult(
            total_score=sum(c.max_points * 0.5 for c in criteria),
            max_score=sum(c.max_points for c in criteria),
            components=components,
            comment=f"Automated grading completed. Response: {response_text[:200]}..."
        )

    def _create_error_result(self, criteria: List[RubricCriterion], error_msg: str) -> GradingResult:
        """Create an error result when grading fails."""
        components = {}
        for criterion in criteria:
            components[criterion.name] = ComponentFeedback(
                score=0,
                max_score=criterion.max_points,
                feedback=f"Could not evaluate: {error_msg}"
            )

        return GradingResult(
            total_score=0,
            max_score=sum(c.max_points for c in criteria),
            components=components,
            comment=f"Grading error occurred: {error_msg}"
        )

    def grade_submission_directory(self, submission_dir: Path, rubric_criteria: List[RubricCriterion]) -> GradingResult:
        """
        Grade all files in a submission directory.

        This method handles the complete workflow of:
        1. Finding submission files
        2. Selecting relevant files if submission is large
        3. Building submission content
        4. Grading the submission

        Args:
            submission_dir: Path to the submission directory
            rubric_criteria: List of rubric criteria to evaluate against

        Returns:
            GradingResult with scores and feedback
        """
        from .submission_utils import (
            find_all_submission_files,
            create_submission_summary,
            build_submission_content,
            select_files_to_grade,
            SIZE_THRESHOLD
        )

        # Find all submission files
        submission_files = find_all_submission_files(submission_dir)
        if not submission_files:
            LOG.warning(f"No submission files found in {submission_dir}")
            return self._create_error_result(rubric_criteria, "No submission files found")

        total_size = sum(size for _, size in submission_files)
        LOG.info(f"Found {len(submission_files)} files (total size: {total_size:,} bytes)")

        # Determine which files to grade
        if total_size > SIZE_THRESHOLD:
            LOG.info(f"Large submission detected ({total_size:,} bytes > {SIZE_THRESHOLD:,} bytes)")
            LOG.info("Using two-pass approach to select relevant files...")

            # Create submission summary and ask LLM which files to review
            summary = create_submission_summary(submission_dir, submission_files)

            try:
                selected_filenames = self.select_files_for_review(summary, rubric_criteria)
                files_to_grade = select_files_to_grade(submission_files, selected_filenames)
                LOG.info(f"LLM selected {len(files_to_grade)} files for review")
            except Exception as e:
                LOG.warning(f"File selection failed, using all files: {e}")
                files_to_grade = submission_files
        else:
            # Use all files for small submissions
            files_to_grade = submission_files

        # Build submission content from selected files
        submission_content = build_submission_content(submission_dir, files_to_grade)
        LOG.info(f"Combined submission content: {len(submission_content)} characters")

        # Grade the submission
        return self.grade(submission_content, rubric_criteria)