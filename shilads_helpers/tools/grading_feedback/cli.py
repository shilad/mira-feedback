#!/usr/bin/env python3
"""Command-line interface for grading submissions with OpenAI."""

import argparse
import logging
import sys
import yaml
from pathlib import Path

from shilads_helpers.libs.config_loader import load_all_configs
from .grader import SubmissionGrader
from .rubric_parser import RubricParser

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
LOG = logging.getLogger(__name__)


def main():
    """Main entry point for grade-submission command."""
    parser = argparse.ArgumentParser(
        description='Grade student submissions using OpenAI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Grade with defaults from config (or o1-preview as fallback)
  grade-submission --submission-dir hw/student1/ --rubric rubric.md

  # Specify custom feedback filename
  grade-submission --submission-dir hw/student1/ --rubric rubric.md --feedback-file results.yaml

  # Override model from config (e.g., for faster/cheaper grading)
  grade-submission --submission-dir hw/student1/ --rubric rubric.md --model gpt-4

  # Use o1 with high reasoning effort for complex assignments
  grade-submission --submission-dir hw/student1/ --rubric rubric.md --model o1-preview --reasoning-effort high

  # Use o1-mini for faster grading with reasoning
  grade-submission --submission-dir hw/student1/ --rubric rubric.md --model o1-mini
        """
    )

    # Required arguments
    parser.add_argument(
        '--submission-dir', '-s',
        type=Path,
        required=True,
        help='Directory containing the student submission'
    )
    parser.add_argument(
        '--rubric', '-r',
        type=Path,
        required=True,
        help='Path to the rubric markdown file'
    )

    # Optional arguments
    parser.add_argument(
        '--feedback-file', '-f',
        type=str,
        default='moodle_feedback.yaml',
        help='Feedback filename (default: moodle_feedback.yaml in submission directory)'
    )
    parser.add_argument(
        '--model', '-m',
        type=str,
        default=None,
        help='OpenAI model to use (overrides config value)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate inputs
    if not args.submission_dir.is_dir():
        LOG.error(f"Submission directory does not exist: {args.submission_dir}")
        sys.exit(1)

    if not args.rubric.is_file():
        LOG.error(f"Rubric file does not exist: {args.rubric}")
        sys.exit(1)

    # Parse rubric
    try:
        parser = RubricParser()
        rubric_criteria = parser.parse_file(args.rubric)
        LOG.info(f"Parsed rubric with {len(rubric_criteria)} criteria")
        for criterion in rubric_criteria:
            LOG.debug(f"  - {criterion.name}: {criterion.max_points} points")
    except Exception as e:
        LOG.error(f"Failed to parse rubric: {e}")
        sys.exit(1)

    # Initialize grader
    try:
        # Load configuration
        config = load_all_configs()

        grader = SubmissionGrader(
            configs=config,
            model=args.model
        )
    except Exception as e:
        LOG.error(f"Failed to initialize grader: {e}")
        sys.exit(1)

    # Grade the submission directory
    try:
        LOG.info(f"Grading submission in {args.submission_dir}...")
        result = grader.grade_submission_directory(args.submission_dir, rubric_criteria)
        LOG.info(f"Grading complete: {result.total_score}/{result.max_score}")
    except Exception as e:
        LOG.error(f"Grading failed: {e}")
        sys.exit(1)

    # Determine output path
    if Path(args.feedback_file).is_absolute():
        output_path = Path(args.feedback_file)
    else:
        output_path = args.submission_dir / args.feedback_file

    # Save results
    try:
        with open(output_path, 'w') as f:
            yaml.dump(result.to_yaml_dict(), f, default_flow_style=False, sort_keys=False)
        LOG.info(f"Feedback saved to: {output_path}")
    except Exception as e:
        LOG.error(f"Failed to save feedback: {e}")
        sys.exit(1)

    # Print summary
    print(f"\n{'='*50}")
    print(f"Grading Complete")
    print(f"{'='*50}")
    print(f"Submission: {args.submission_dir.name}")
    print(f"Score: {result.total_score}/{result.max_score} ({result.total_score/result.max_score*100:.1f}%)")
    print(f"Feedback saved to: {output_path}")
    print(f"\nComponent Scores:")
    for name, feedback in result.components.items():
        print(f"  - {name}: {feedback.score}/{feedback.max_score}")
    print(f"\nOverall Comment: {result.comment}")


if __name__ == "__main__":
    main()