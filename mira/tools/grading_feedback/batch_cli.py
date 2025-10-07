#!/usr/bin/env python3
"""Command-line interface for batch grading multiple submissions."""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime

from mira.libs.config_loader import load_all_configs
from .batch_grader import BatchGrader

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
LOG = logging.getLogger(__name__)


def main():
    """Main entry point for grade-batch command."""
    parser = argparse.ArgumentParser(
        description='Grade multiple student submissions in parallel using OpenAI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Grade all submissions in a directory
  grade-batch --submissions-dir hw/submissions/ --rubric rubric.md

  # Override thread count for faster processing
  grade-batch --submissions-dir hw/submissions/ --rubric rubric.md --max-threads 8

  # Use specific model
  grade-batch --submissions-dir hw/submissions/ --rubric rubric.md --model gpt-4

  # Save summary to specific location
  grade-batch --submissions-dir hw/submissions/ --rubric rubric.md --summary grading_results.yaml

  # Custom feedback filename in each submission directory
  grade-batch --submissions-dir hw/submissions/ --rubric rubric.md --feedback-file feedback.yaml
        """
    )

    # Required arguments
    parser.add_argument(
        '--submissions-dir', '-s',
        type=Path,
        required=True,
        help='Directory containing all student submission directories'
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
        help='Feedback filename to create in each submission directory (default: moodle_feedback.yaml)'
    )
    parser.add_argument(
        '--summary', '-o',
        type=Path,
        default=None,
        help='Path to save summary YAML file (default: grading_summary_TIMESTAMP.yaml in submissions dir)'
    )
    parser.add_argument(
        '--model', '-m',
        type=str,
        default=None,
        help='OpenAI model to use (overrides config value)'
    )
    parser.add_argument(
        '--max-threads', '-t',
        type=int,
        default=None,
        help='Maximum number of concurrent grading tasks (overrides config value)'
    )
    parser.add_argument(
        '--continue-on-error',
        action='store_true',
        help='Continue grading even if some submissions fail'
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
    if not args.submissions_dir.is_dir():
        LOG.error(f"Submissions directory does not exist: {args.submissions_dir}")
        sys.exit(1)

    if not args.rubric.is_file():
        LOG.error(f"Rubric file does not exist: {args.rubric}")
        sys.exit(1)

    # Load configuration
    try:
        config = load_all_configs()
    except Exception as e:
        LOG.error(f"Failed to load configuration: {e}")
        sys.exit(1)

    # Initialize batch grader
    try:
        batch_grader = BatchGrader(
            configs=config,
            model=args.model,
            max_concurrent=args.max_threads  # Using max_threads arg for backward compatibility
        )
    except Exception as e:
        LOG.error(f"Failed to initialize batch grader: {e}")
        sys.exit(1)

    # Grade all submissions
    LOG.info(f"Starting batch grading of submissions in {args.submissions_dir}")
    LOG.info(f"Using rubric: {args.rubric}")
    if args.model:
        LOG.info(f"Using model: {args.model}")

    try:
        results = batch_grader.grade_all_submissions(
            submissions_dir=args.submissions_dir,
            rubric_path=args.rubric,
            feedback_filename=args.feedback_file,
            continue_on_error=args.continue_on_error
        )
    except Exception as e:
        LOG.error(f"Batch grading failed: {e}")
        sys.exit(1)

    if not results:
        LOG.error("No submissions were graded")
        sys.exit(1)

    # Generate summary output path if not specified
    if args.summary is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        summary_path = args.submissions_dir / f"grading_summary_{timestamp}.yaml"
    else:
        summary_path = args.summary

    # Save summary
    try:
        batch_grader.save_summary(results, summary_path)
        LOG.info(f"Summary saved to: {summary_path}")
    except Exception as e:
        LOG.error(f"Failed to save summary: {e}")

    # Print results summary
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]

    print(f"\n{'='*60}")
    print(f"Batch Grading Complete")
    print(f"{'='*60}")
    print(f"Total submissions: {len(results)}")
    print(f"Successfully graded: {len(successful)}")
    print(f"Failed: {len(failed)}")

    if successful:
        avg_score = sum(r.total_score for r in successful) / len(successful)
        max_score = successful[0].max_score if successful else 0
        print(f"Average score: {avg_score:.1f}/{max_score:.0f} ({avg_score/max_score*100:.1f}%)")

        # Show score distribution
        print(f"\nScore Distribution:")
        for result in successful:
            pct = result.total_score / result.max_score * 100
            print(f"  {result.student_id}: {result.total_score:.1f}/{result.max_score:.0f} ({pct:.1f}%)")

    if failed:
        print(f"\nFailed submissions:")
        for result in failed:
            print(f"  {result.student_id}: {result.error_message}")

    print(f"\nFeedback files saved in each submission directory as: {args.feedback_file}")
    print(f"Summary saved to: {summary_path}")

    # Exit with error if any submissions failed and not continuing on error
    if failed and not args.continue_on_error:
        sys.exit(1)


if __name__ == "__main__":
    main()