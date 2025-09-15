#!/usr/bin/env python3
"""Command-line interface for grading submissions with OpenAI."""

import argparse
import logging
import sys
import yaml
from pathlib import Path
from typing import Optional, List, Dict, Tuple

from shilads_helpers.libs.config_loader import load_all_configs
from .grader import SubmissionGrader
from .rubric_parser import RubricParser

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
LOG = logging.getLogger(__name__)

# Size threshold for two-pass approach (10KB)
SIZE_THRESHOLD = 10 * 1024  # 10KB in bytes


def find_all_submission_files(submission_dir: Path) -> List[Tuple[Path, int]]:
    """
    Find all submission files in a directory with their sizes.

    Returns:
        List of (file_path, size_in_bytes) tuples
    """
    all_extensions = [
        '*.py', '*.ipynb',
        '*.R', '*.r', '*.Rmd', '*.qmd',
        '*.java', '*.cpp', '*.c', '*.h',
        '*.js', '*.ts', '*.jsx', '*.tsx',
        '*.md', '*.txt', '*.html',
        '*.sql', '*.sh', '*.yml', '*.yaml', '*.json',
        '*.csv', '*.pdf'
    ]

    submission_files = []

    for ext in all_extensions:
        files = list(submission_dir.glob(ext))
        for file in files:
            # Skip feedback, rubric, and hidden files
            if any(skip in file.name.lower() for skip in ['feedback', 'grading', 'rubric', '.git']):
                continue
            if file.name.startswith('.'):
                continue

            try:
                size = file.stat().st_size
                submission_files.append((file, size))
            except Exception as e:
                LOG.warning(f"Could not stat file {file}: {e}")

    # Also check subdirectories (one level deep)
    for subdir in submission_dir.iterdir():
        if subdir.is_dir() and not subdir.name.startswith('.'):
            for ext in all_extensions:
                files = list(subdir.glob(ext))
                for file in files:
                    if any(skip in file.name.lower() for skip in ['feedback', 'grading', 'rubric']):
                        continue
                    if file.name.startswith('.'):
                        continue

                    try:
                        size = file.stat().st_size
                        submission_files.append((file, size))
                    except Exception as e:
                        LOG.warning(f"Could not stat file {file}: {e}")

    # Sort by size (largest first) for better visibility
    submission_files.sort(key=lambda x: x[1], reverse=True)

    return submission_files


def create_submission_summary(submission_dir: Path, files: List[Tuple[Path, int]]) -> str:
    """
    Create a summary of submission contents for LLM to decide which files to review.

    Args:
        submission_dir: The submission directory
        files: List of (file_path, size) tuples

    Returns:
        Summary string describing the submission structure
    """
    summary = f"SUBMISSION DIRECTORY: {submission_dir.name}\n"
    summary += f"Total files: {len(files)}\n"
    summary += f"Total size: {sum(f[1] for f in files):,} bytes\n\n"
    summary += "FILE STRUCTURE:\n"

    for file_path, size in files:
        # Get relative path from submission directory
        try:
            rel_path = file_path.relative_to(submission_dir)
        except ValueError:
            rel_path = file_path.name

        # Format size nicely
        if size < 1024:
            size_str = f"{size} bytes"
        elif size < 1024 * 1024:
            size_str = f"{size / 1024:.1f} KB"
        else:
            size_str = f"{size / (1024 * 1024):.1f} MB"

        summary += f"  - {rel_path}: {size_str}\n"

        # Add file type hint
        suffix = file_path.suffix.lower()
        if suffix in ['.py', '.java', '.cpp', '.c', '.js', '.ts']:
            summary += f"    (source code)\n"
        elif suffix in ['.md', '.txt', '.pdf']:
            summary += f"    (documentation)\n"
        elif suffix in ['.ipynb', '.Rmd', '.qmd']:
            summary += f"    (notebook)\n"
        elif suffix in ['.csv', '.json', '.yml', '.yaml']:
            summary += f"    (data/config)\n"

    return summary


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

    # Find all submission files
    submission_files = find_all_submission_files(args.submission_dir)
    if not submission_files:
        LOG.error(f"No submission files found in {args.submission_dir}")
        sys.exit(1)

    total_size = sum(size for _, size in submission_files)
    LOG.info(f"Found {len(submission_files)} files (total size: {total_size:,} bytes)")

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

    # Determine if we need two-pass approach
    if total_size > SIZE_THRESHOLD:
        LOG.info(f"Large submission detected ({total_size:,} bytes > {SIZE_THRESHOLD:,} bytes)")
        LOG.info("Using two-pass approach to select relevant files...")

        # Create submission summary
        summary = create_submission_summary(args.submission_dir, submission_files)

        # Ask LLM which files to review
        try:
            selected_files = grader.select_files_for_review(summary, rubric_criteria)
            LOG.info(f"LLM selected {len(selected_files)} files for review")
        except Exception as e:
            LOG.warning(f"File selection failed, using all files: {e}")
            selected_files = [str(f[0]) for f in submission_files]

        # Filter to selected files
        files_to_grade = []
        for file_path, size in submission_files:
            if str(file_path) in selected_files or str(file_path.name) in selected_files:
                files_to_grade.append((file_path, size))
                LOG.info(f"  - Selected: {file_path.name}")
    else:
        # Use all files for small submissions
        files_to_grade = submission_files

    # Read submission content from selected files
    submission_content = ""
    for file_path, size in files_to_grade:
        try:
            rel_path = file_path.relative_to(args.submission_dir)
        except ValueError:
            rel_path = file_path.name

        submission_content += f"\n{'='*60}\n"
        submission_content += f"FILE: {rel_path}\n"
        submission_content += f"{'='*60}\n"

        try:
            if file_path.suffix.lower() == '.pdf':
                submission_content += "[PDF file - content not extracted]\n"
            else:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                # Truncate very large files
                if len(content) > 50000:
                    content = content[:50000] + "\n... [truncated] ..."
                submission_content += content
        except Exception as e:
            submission_content += f"[Error reading file: {e}]\n"

    LOG.info(f"Combined submission content: {len(submission_content)} characters")

    # Grade submission
    try:
        LOG.info(f"Grading submission with {args.model}...")
        result = grader.grade(submission_content, rubric_criteria)
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
    print(f"Files graded: {len(files_to_grade)}")
    print(f"Score: {result.total_score}/{result.max_score} ({result.total_score/result.max_score*100:.1f}%)")
    print(f"Feedback saved to: {output_path}")
    print(f"\nComponent Scores:")
    for name, feedback in result.components.items():
        print(f"  - {name}: {feedback.score}/{feedback.max_score}")
    print(f"\nOverall Comment: {result.comment}")


if __name__ == "__main__":
    main()