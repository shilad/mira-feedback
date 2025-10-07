"""Batch grader for processing multiple submissions in parallel using async/await."""

import asyncio
import logging
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from tqdm.asyncio import tqdm

from shilads_helpers.libs.config_loader import ConfigType, get_config
from .grader import SubmissionGrader
from .rubric_parser import RubricParser
from .models import GradingResult, RubricCriterion

LOG = logging.getLogger(__name__)


@dataclass
class BatchGradingResult:
    """Result from batch grading operation."""
    submission_dir: str
    student_id: str
    total_score: float
    max_score: float
    success: bool
    error_message: Optional[str] = None
    grading_result: Optional[GradingResult] = None
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        data = {
            'submission_dir': self.submission_dir,
            'student_id': self.student_id,
            'total_score': self.total_score,
            'max_score': self.max_score,
            'success': self.success,
            'timestamp': self.timestamp
        }
        if self.error_message:
            data['error_message'] = self.error_message
        if self.grading_result:
            components_dict = {}
            for name, feedback in self.grading_result.components.items():
                component_data = {
                    'score': feedback.score,
                    'max_score': feedback.max_score,
                    'feedback': feedback.feedback
                }
                # Convert adjustments to plain dicts if present
                if feedback.adjustments:
                    component_data['adjustments'] = [
                        {
                            'name': adj.name,
                            'description': adj.description,
                            'score_impact': adj.score_impact
                        }
                        for adj in feedback.adjustments
                    ]
                else:
                    component_data['adjustments'] = None
                components_dict[name] = component_data

            data['components'] = components_dict
            data['comment'] = self.grading_result.comment
        return data


class BatchGrader:
    """Grade multiple submissions in parallel using async/await."""

    def __init__(self, configs: ConfigType, model: Optional[str] = None,
                 settings: Optional[Dict[str, Any]] = None, max_concurrent: Optional[int] = None):
        """
        Initialize the batch grader.

        Args:
            configs: Configuration dictionary
            model: Optional model override
            settings: Optional settings override
            max_concurrent: Maximum number of concurrent grading tasks (overrides config)
        """
        self.configs = configs
        self.model = model
        self.settings = settings

        # Get max concurrent tasks from parameter or config
        if max_concurrent is not None:
            self.max_concurrent = max_concurrent
        else:
            self.max_concurrent = get_config("tools.max_threads", configs, default=4)

        LOG.info(f"BatchGrader initialized with max_concurrent={self.max_concurrent}")

    def find_submission_directories(self, submissions_dir: Path) -> List[Path]:
        """
        Find all submission directories.

        Args:
            submissions_dir: Parent directory containing submissions

        Returns:
            List of submission directory paths
        """
        submission_dirs = []

        # Look for directories that likely contain submissions
        for item in submissions_dir.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                # Skip common non-submission directories
                if item.name.lower() in ['__pycache__', 'node_modules', '.git', 'venv']:
                    continue

                # Check if it looks like a submission directory
                # (contains at least one code/text file)
                has_submission_files = any(
                    f.suffix in ['.py', '.java', '.cpp', '.c', '.js', '.ts', '.r', '.R',
                                 '.md', '.txt', '.ipynb', '.Rmd', '.qmd', '.sql']
                    for f in item.rglob('*') if f.is_file()
                )

                if has_submission_files:
                    submission_dirs.append(item)
                    LOG.debug(f"Found submission directory: {item.name}")

        submission_dirs.sort()  # Sort for consistent ordering
        return submission_dirs

    async def _grade_single_submission_async(self, submission_dir: Path, rubric_criteria: List[RubricCriterion],
                                            feedback_filename: str = "moodle_feedback.yaml") -> BatchGradingResult:
        """
        Grade a single submission directory asynchronously.

        Args:
            submission_dir: Path to submission directory
            rubric_criteria: Parsed rubric criteria
            feedback_filename: Name of feedback file to create

        Returns:
            BatchGradingResult with grading outcome
        """
        # Extract student ID from directory name
        # Handle pattern like: REDACTED_PERSON10_325229_assignsubmission_file
        dir_name = submission_dir.name
        if dir_name.startswith("REDACTED_PERSON"):
            # Extract just the REDACTED_PERSON{id} part
            parts = dir_name.split("_")
            if len(parts) >= 2:
                student_id = f"{parts[0]}_{parts[1]}"  # e.g., REDACTED_PERSON10
            else:
                student_id = dir_name
        else:
            student_id = dir_name

        LOG.debug(f"Grading submission: {student_id} (dir: {dir_name})")

        try:
            # Create a new grader instance for this submission
            grader = SubmissionGrader(
                configs=self.configs,
                model=self.model,
                settings=self.settings
            )

            # Grade the submission directory
            # Since grade_submission_directory calls grade() which uses asyncio.run(),
            # we need to call the async version directly to avoid nested event loops
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
                grading_result = grader._create_error_result(rubric_criteria, "No submission files found")
            else:
                total_size = sum(size for _, size in submission_files)

                # Determine which files to grade
                if total_size > SIZE_THRESHOLD:
                    summary = create_submission_summary(submission_dir, submission_files)
                    # Use async version to avoid nested event loops
                    selected_filenames = await grader.select_files_for_review_async(summary, rubric_criteria)
                    files_to_grade = select_files_to_grade(submission_files, selected_filenames)
                else:
                    files_to_grade = submission_files

                # Build submission content from selected files
                submission_content = build_submission_content(submission_dir, files_to_grade)

                # Grade using the async method directly
                grading_result = await grader.grade_async(submission_content, rubric_criteria)

            # Save feedback file in submission directory
            feedback_path = submission_dir / feedback_filename
            with open(feedback_path, 'w') as f:
                yaml.dump(grading_result.to_yaml_dict(), f, default_flow_style=False, sort_keys=False)

            LOG.debug(f"Graded {student_id}: {grading_result.total_score}/{grading_result.max_score}")

            return BatchGradingResult(
                submission_dir=dir_name,  # Keep original directory name for reference
                student_id=student_id,      # Use extracted student ID for grouping
                total_score=grading_result.total_score,
                max_score=grading_result.max_score,
                success=True,
                grading_result=grading_result
            )

        except Exception as e:
            LOG.error(f"Error grading {student_id}: {e}")
            return BatchGradingResult(
                submission_dir=dir_name,  # Keep original directory name for reference
                student_id=student_id,      # Use extracted student ID for grouping
                total_score=0,
                max_score=sum(c.max_points for c in rubric_criteria),
                success=False,
                error_message=str(e)
            )

    async def grade_all_submissions_async(self, submissions_dir: Path, rubric_path: Path,
                                         feedback_filename: str = "moodle_feedback.yaml",
                                         continue_on_error: bool = True) -> List[BatchGradingResult]:
        """
        Grade all submissions asynchronously with concurrency control.

        Args:
            submissions_dir: Parent directory containing all submissions
            rubric_path: Path to rubric file
            feedback_filename: Name of feedback file to create in each directory
            continue_on_error: Whether to continue if a submission fails

        Returns:
            List of BatchGradingResult objects
        """
        # Parse rubric
        parser = RubricParser()
        rubric_criteria = parser.parse_file(rubric_path)
        LOG.info(f"Parsed rubric with {len(rubric_criteria)} criteria")

        # Find all submission directories
        submission_dirs = self.find_submission_directories(submissions_dir)
        if not submission_dirs:
            LOG.error(f"No submission directories found in {submissions_dir}")
            return []

        LOG.info(f"Found {len(submission_dirs)} submission directories")

        # Create a semaphore to limit concurrent tasks
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def grade_with_semaphore(submission_dir: Path) -> BatchGradingResult:
            """Grade a submission with semaphore-controlled concurrency."""
            async with semaphore:
                return await self._grade_single_submission_async(
                    submission_dir, rubric_criteria, feedback_filename
                )

        # Create all grading tasks
        tasks = [
            grade_with_semaphore(submission_dir)
            for submission_dir in submission_dirs
        ]

        # Execute tasks with progress bar
        results = []

        # Use tqdm to show progress
        for coro in tqdm.as_completed(tasks, total=len(tasks), desc="Grading submissions"):
            try:
                grading_result = await coro
                results.append(grading_result)

                # Log progress
                if grading_result.success:
                    LOG.debug(f"Completed: {grading_result.student_id} - {grading_result.total_score}/{grading_result.max_score}")
                else:
                    LOG.warning(f"Failed: {grading_result.student_id} - {grading_result.error_message}")

            except Exception as e:
                import traceback
                LOG.error(f"Unexpected error during grading: {e} " + traceback.format_exc())
                if not continue_on_error:
                    # Cancel remaining tasks
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    raise

        # Sort results by student ID for consistent output
        results.sort(key=lambda r: r.student_id)

        return results

    def grade_all_submissions(self, submissions_dir: Path, rubric_path: Path,
                             feedback_filename: str = "moodle_feedback.yaml",
                             continue_on_error: bool = True) -> List[BatchGradingResult]:
        """
        Synchronous wrapper for grade_all_submissions_async.

        Args:
            submissions_dir: Parent directory containing all submissions
            rubric_path: Path to rubric file
            feedback_filename: Name of feedback file to create in each directory
            continue_on_error: Whether to continue if a submission fails

        Returns:
            List of BatchGradingResult objects
        """
        return asyncio.run(self.grade_all_submissions_async(
            submissions_dir, rubric_path, feedback_filename, continue_on_error
        ))

    def save_summary(self, results: List[BatchGradingResult], output_path: Path):
        """
        Save grading summary to YAML file.

        Args:
            results: List of grading results
            output_path: Path to save summary file
        """
        # Calculate statistics
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        summary = {
            'grading_summary': {
                'timestamp': datetime.now().isoformat(),
                'total_submissions': len(results),
                'successful': len(successful),
                'failed': len(failed),
                'average_score': sum(r.total_score for r in successful) / len(successful) if successful else 0,
                'max_possible_score': results[0].max_score if results else 0,
            },
            'submissions': [r.to_dict() for r in results]
        }

        with open(output_path, 'w') as f:
            yaml.dump(summary, f, default_flow_style=False, sort_keys=False)

        LOG.info(f"Summary saved to {output_path}")