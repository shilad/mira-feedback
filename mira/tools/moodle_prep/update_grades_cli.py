#!/usr/bin/env python3
"""Command-line interface for updating moodle_grades.csv with feedback scores."""

import argparse
import logging
import sys
from pathlib import Path

from mira.tools.moodle_prep.utils import update_grades_csv_from_feedback

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
LOG = logging.getLogger(__name__)


def main():
    """Main entry point for update-moodle-grades command."""
    parser = argparse.ArgumentParser(
        description='Update moodle_grades.csv with scores from feedback.yaml files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  update-moodle-grades --restored-dir hw/3_restored/

  This will:
    1. Read feedback.yaml from each submission directory in hw/3_restored/
    2. Extract total_score and comment from each feedback.yaml
    3. Update hw/3_restored/moodle_grades_final.csv with the grades

  If moodle_grades_final.csv doesn't exist, it will be copied from hw/1_prep/moodle_grades.csv
        """
    )

    # Required arguments
    parser.add_argument(
        '--restored-dir', '-d',
        type=Path,
        required=True,
        help='Path to restored directory containing submission folders with feedback.yaml files'
    )

    # Optional arguments
    parser.add_argument(
        '--csv-path', '-c',
        type=Path,
        help='Path to moodle_grades.csv file (default: <restored-dir>/moodle_grades_final.csv)'
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

    # Validate input directory
    if not args.restored_dir.exists():
        LOG.error(f"Restored directory not found: {args.restored_dir}")
        sys.exit(1)

    if not args.restored_dir.is_dir():
        LOG.error(f"Path is not a directory: {args.restored_dir}")
        sys.exit(1)

    # Update grades
    try:
        LOG.info(f"Updating grades from feedback files in {args.restored_dir}")

        stats = update_grades_csv_from_feedback(
            restored_dir=args.restored_dir,
            csv_path=args.csv_path
        )

        # Print summary
        print("\n" + "=" * 50)
        print("Grade Update Complete!")
        print("=" * 50)

        print(f"\nStatistics:")
        print(f"  Total students: {stats['total_students']}")
        print(f"  Updated with grades: {stats['updated']}")
        print(f"  Missing feedback: {stats['missing_feedback']}")

        if stats['errors']:
            print(f"\nErrors encountered: {len(stats['errors'])}")
            for error in stats['errors'][:5]:  # Show first 5 errors
                print(f"  - {error['student']}: {error['error']}")
            if len(stats['errors']) > 5:
                print(f"  ... and {len(stats['errors']) - 5} more")

        csv_path = args.csv_path or args.restored_dir / 'moodle_grades_final.csv'
        print(f"\nUpdated CSV: {csv_path}")

    except Exception as e:
        LOG.error(f"Update failed: {e}", exc_info=args.verbose)
        sys.exit(1)


if __name__ == '__main__':
    main()