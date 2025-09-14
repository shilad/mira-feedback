#!/usr/bin/env python3
"""Command-line interface for Moodle submission preparation."""

import argparse
import logging
import sys
from pathlib import Path

from shilads_helpers.tools.moodle_prep.processor import MoodleProcessor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
LOG = logging.getLogger(__name__)


def main():
    """Main entry point for prep-moodle command."""
    parser = argparse.ArgumentParser(
        description='Prepare Moodle homework submissions for anonymized feedback',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Stages:
  0_submitted  - Extracted file submissions only (online text removed)
  1_prep       - Generated moodle_grades.csv + HTML converted to Markdown
  2_redacted   - PII redacted content (clean output)
  
Example:
  prep-moodle --zip submissions.zip --workdir ./output/
  
  This will create:
    ./output/0_submitted/  - File submissions only (no online text)
    ./output/1_prep/       - moodle_grades.csv + HTML converted to Markdown
    ./output/2_redacted/   - Clean anonymized output with PII redacted
        """
    )
    
    # Required arguments
    parser.add_argument(
        '--zip', '-z',
        type=Path,
        required=True,
        help='Path to Moodle submissions zip file'
    )
    parser.add_argument(
        '--workdir', '-w',
        type=Path,
        required=True,
        help='Working directory for processing stages'
    )
    
    # Optional arguments
    parser.add_argument(
        '--skip-stage',
        action='append',
        choices=['0_submitted', '1_prep', '2_redacted'],
        help='Skip specified stage(s). Can be used multiple times.'
    )
    parser.add_argument(
        '--keep-html',
        action='store_true',
        help='Keep original HTML files alongside converted Markdown'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    parser.add_argument(
        '--info',
        action='store_true',
        help='Show information about existing stage directories and exit'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Validate input files
    if not args.info:
        if not args.zip.exists():
            LOG.error(f"Zip file not found: {args.zip}")
            sys.exit(1)
    
    # Create processor
    processor = MoodleProcessor(
        working_dir=args.workdir,
        keep_html=args.keep_html,
        dry_run=args.dry_run
    )
    
    # Show info and exit if requested
    if args.info:
        info = processor.get_stage_info()
        print("\nStage Directory Information:")
        print("-" * 40)
        for stage_name, stage_info in info.items():
            print(f"\n{stage_name}:")
            print(f"  Path: {stage_info['path']}")
            print(f"  Exists: {stage_info['exists']}")
            if stage_info['exists']:
                print(f"  Files: {stage_info['file_count']}")
                print(f"  Directories: {stage_info['dir_count']}")
        sys.exit(0)
    
    # Process submissions
    try:
        skip_stages = set(args.skip_stage) if args.skip_stage else set()
        
        if args.dry_run:
            LOG.info("=== DRY RUN MODE - No files will be modified ===")
        
        LOG.info(f"Processing Moodle submissions...")
        LOG.info(f"  Zip: {args.zip}")
        LOG.info(f"  Working dir: {args.workdir}")
        
        if skip_stages:
            LOG.info(f"  Skipping stages: {', '.join(skip_stages)}")
        
        # Run processing
        results = processor.process(
            zip_path=args.zip,
            skip_stages=skip_stages
        )
        
        # Print summary
        print("\n" + "=" * 50)
        print("Processing Complete!")
        print("=" * 50)
        
        stats = results['stats']
        print(f"\nStatistics:")
        print(f"  Files extracted: {stats['files_extracted']}")
        print(f"  HTML files converted: {stats['files_converted']}")
        print(f"  Files redacted: {stats['files_redacted']}")
        
        if stats['errors']:
            print(f"\nErrors encountered: {len(stats['errors'])}")
            for error in stats['errors'][:5]:  # Show first 5 errors
                print(f"  - {error}")
            if len(stats['errors']) > 5:
                print(f"  ... and {len(stats['errors']) - 5} more")
        
        print(f"\nOutput directories:")
        for stage_name, stage_path in results['stage_dirs'].items():
            print(f"  {stage_name}: {stage_path}")
        
        print(f"\nClean anonymized output ready in: {results['stage_dirs']['2_redacted']}")
        
    except Exception as e:
        LOG.error(f"Processing failed: {e}", exc_info=args.verbose)
        sys.exit(1)


if __name__ == '__main__':
    main()