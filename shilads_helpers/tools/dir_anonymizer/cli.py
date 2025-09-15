#!/usr/bin/env python3
"""Command-line interface for directory anonymizer."""

import sys
import argparse
import logging
from pathlib import Path

from shilads_helpers.libs.config_loader import load_all_configs
from shilads_helpers.tools.dir_anonymizer.anonymizer import DirectoryAnonymizer
from shilads_helpers.tools.dir_anonymizer.deanonymizer import DirectoryDeanonymizer
from shilads_helpers.tools.dir_anonymizer.accuracy import AccuracyTester

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
LOG = logging.getLogger(__name__)


def anonymize_command(args):
    """Handle the anonymize command."""
    try:
        # Load configuration
        config = load_all_configs()

        # Determine whether to anonymize filenames (default is True)
        anonymize_filenames = not args.keep_original_filenames
        anonymizer = DirectoryAnonymizer(config=config, anonymize_filenames=anonymize_filenames)
        
        LOG.info(f"Anonymizing directory: {args.input_dir}")
        if args.output_dir:
            LOG.info(f"Output directory: {args.output_dir}")
            
        if args.dry_run:
            LOG.info("Running in DRY RUN mode - no files will be written")
            
        if args.keep_original_filenames:
            LOG.info("Keeping original filenames (not anonymizing)")
        else:
            LOG.info("Anonymizing filenames")
            
        results = anonymizer.process_directory(
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            dry_run=args.dry_run
        )
        
        stats = results['statistics']
        LOG.info(f"Processed {stats['processed_files']} of {stats['total_files']} files")
        
        if stats['errors']:
            LOG.warning(f"Encountered {len(stats['errors'])} errors")
            
    except Exception as e:
        LOG.error(f"Anonymization failed: {e}")
        sys.exit(1)


def deanonymize_command(args):
    """Handle the deanonymize/restore command."""
    try:
        if not Path(args.mapping_file).exists():
            LOG.error(f"Mapping file not found: {args.mapping_file}")
            sys.exit(1)
            
        deanonymizer = DirectoryDeanonymizer(args.mapping_file)
        
        LOG.info(f"Restoring directory: {args.input_dir}")
        LOG.info(f"Output directory: {args.output_dir}")
        LOG.info(f"Using mapping file: {args.mapping_file}")
        
        stats = deanonymizer.restore_directory(
            anonymized_dir=args.input_dir,
            output_dir=args.output_dir,
            restore_filenames=not args.keep_anonymized_names
        )
        
        LOG.info(f"Restored {stats['restored_files']} of {stats['total_files']} files")
        
        if stats['errors']:
            LOG.warning(f"Encountered {len(stats['errors'])} errors")
            
    except Exception as e:
        LOG.error(f"Restoration failed: {e}")
        sys.exit(1)


def accuracy_command(args):
    """Handle the accuracy test command."""
    try:
        # Load configuration
        config = load_all_configs()

        test_dir = Path(args.test_dir) if args.test_dir else None
        tester = AccuracyTester(config=config, test_dir=test_dir, backend=args.backend)
        tester.run(verbose=args.verbose)
    except Exception as e:
        LOG.error(f"Accuracy testing failed: {e}")
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Anonymize or restore directory contents using anonLLM'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Anonymize command
    anon_parser = subparsers.add_parser(
        'anonymize',
        help='Anonymize a directory'
    )
    anon_parser.add_argument(
        'input_dir',
        help='Directory to anonymize'
    )
    anon_parser.add_argument(
        'output_dir',
        help='Output directory for anonymized files'
    )
    anon_parser.add_argument(
        '-d', '--dry-run',
        action='store_true',
        help='Show what would be done without actually doing it'
    )
    anon_parser.add_argument(
        '--keep-original-filenames',
        action='store_true',
        help='Keep original filenames instead of anonymizing them (default: anonymize filenames)'
    )
    
    # Deanonymize/restore command
    deanon_parser = subparsers.add_parser(
        'restore',
        help='Restore an anonymized directory using mappings'
    )
    deanon_parser.add_argument(
        'input_dir',
        help='Anonymized directory to restore'
    )
    deanon_parser.add_argument(
        'output_dir',
        help='Where to write restored files'
    )
    deanon_parser.add_argument(
        '-m', '--mapping-file',
        default='anonymization_mapping.json',
        help='Path to mapping file (default: anonymization_mapping.json)'
    )
    deanon_parser.add_argument(
        '-k', '--keep-anonymized-names',
        action='store_true',
        help='Keep anonymized filenames instead of restoring originals'
    )
    
    # Accuracy test command
    accuracy_parser = subparsers.add_parser(
        'accuracy',
        help='Run accuracy tests for PII detection'
    )
    accuracy_parser.add_argument(
        '-t', '--test-dir',
        help='Directory containing test YAML files (default: tests/test_accuracy/test_cases)'
    )
    accuracy_parser.add_argument(
        '-b', '--backend',
        choices=['local', 'anonllm'],
        default='local',
        help='Anonymizer backend to use (default: local)'
    )
    accuracy_parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show detailed failure information'
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
        
    # Execute command
    if args.command == 'anonymize':
        anonymize_command(args)
    elif args.command == 'restore':
        deanonymize_command(args)
    elif args.command == 'accuracy':
        accuracy_command(args)
        

if __name__ == '__main__':
    main()