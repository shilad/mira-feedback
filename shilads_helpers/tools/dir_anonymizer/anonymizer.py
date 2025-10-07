"""Directory anonymizer using local LLM."""

import os
import sys
import json
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from fnmatch import fnmatch
from tqdm import tqdm

from shilads_helpers.libs.config_loader import ConfigType, get_config
from shilads_helpers.libs.local_anonymizer import LocalAnonymizer

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)


class DirectoryAnonymizer:
    """Anonymize directory contents and optionally filenames."""
    
    def __init__(self, config: ConfigType, anonymize_filenames: Optional[bool] = None):
        """Initialize the anonymizer with configuration.

        Args:
            config: Configuration dict (required).
            anonymize_filenames: Override for filename anonymization. If None, uses config value.
        """
        self.config = config
        self.anon_config = get_config('anonymizer', self.config)
        self.anonymize_filenames = (
            anonymize_filenames if anonymize_filenames is not None
            else get_config('options.anonymize_filenames', self.anon_config, True)
        )

        # Initialize local LLM-based anonymizer from config
        self.anonymizer = LocalAnonymizer.create_from_config(self.anon_config)
        LOG.info("Using local LLM anonymizer")

        # Initialize Moodle grades handler lazily to avoid circular import
        self.moodle_grades_handler = None

        # Cache for anonymized paths to ensure consistency
        # Maps original relative path -> anonymized relative path
        self.path_cache = {}

        # Track all mappings - unified for both paths and content
        self.all_mappings = {
            'mappings': {},  # Unified mappings: redacted_token -> original_text
            'statistics': {
                'total_files': 0,
                'processed_files': 0,
                'skipped_files': 0,
                'errors': []
            }
        }
        
    def should_process_file(self, file_path: Path) -> bool:
        """Check if a file should be processed based on config.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if file should be processed
        """
        # Special case: Always process moodle_grades.csv
        if file_path.name == 'moodle_grades.csv':
            return True

        # Check if file extension is in allowed types
        file_types = self.anon_config.get('file_types', [])
        if not any(file_path.suffix.lower() == ft.lower() for ft in file_types):
            LOG.warning(f"Skipping file (not in allowed types): {file_path}")
            return False
            
        # Check against exclude patterns
        exclude_patterns = self.anon_config.get('exclude_patterns', [])
        for pattern in exclude_patterns:
            if fnmatch(str(file_path), pattern) or fnmatch(file_path.name, pattern):
                LOG.warning(f"Skipping file (matches exclude pattern '{pattern}'): {file_path}")
                return False
                
        return True
        
    def should_exclude_dir(self, dir_path: Path) -> bool:
        """Check if a directory should be excluded.
        
        Args:
            dir_path: Path to the directory
            
        Returns:
            True if directory should be excluded
        """
        exclude_patterns = self.anon_config.get('exclude_patterns', [])
        for pattern in exclude_patterns:
            if fnmatch(dir_path.name, pattern):
                return True
        return False
        
    def is_moodle_submission(self, filename: str) -> bool:
        """Check if a filename matches the Moodle submission pattern.
        
        Moodle submission directories follow the pattern: "Name_ID_assignsubmission_file"
        
        Args:
            filename: The filename to check
            
        Returns:
            True if this matches a Moodle submission pattern
        """
        import re
        moodle_pattern = r'^(.+?)_(\d+)_(assignsubmission_\w+)$'
        return bool(re.match(moodle_pattern, filename))
    
    def anonymize_moodle_submission(self, filename: str) -> Tuple[str, Dict[str, str]]:
        """Anonymize a Moodle submission directory name.

        Handles the special case of Moodle submission directories which contain
        student names that must be anonymized. Pattern: "Name_ID_assignsubmission_file"

        Args:
            filename: The Moodle submission directory name

        Returns:
            Tuple of (anonymized directory name, mappings dict)
        """
        import re
        moodle_pattern = r'^(.+?)_(\d+)_(assignsubmission_\w+)$'
        match = re.match(moodle_pattern, filename)

        if not match:
            # Shouldn't happen if is_moodle_submission was called first
            return filename, {}

        name_part = match.group(1)
        id_part = match.group(2)
        suffix_part = match.group(3)

        # Try to anonymize using LLM first, which will use entity memory
        anonymized_name, mappings = self.anonymizer.anonymize_data(name_part)

        # If LLM didn't detect it as a name, force anonymization
        # since we know this position contains a student name in Moodle format
        if anonymized_name == name_part:
            # Name wasn't detected by LLM, force anonymization
            # Check if we've seen this name before
            if name_part not in self.anonymizer.entity_memory:
                # Generate a new tag for this person
                self.anonymizer.entity_counters['PERSON'] += 1
                tag = f"REDACTED_PERSON{self.anonymizer.entity_counters['PERSON']}"
                self.anonymizer.entity_memory[name_part] = tag
            else:
                tag = self.anonymizer.entity_memory[name_part]
            anonymized_name = tag
            # Create the mapping for this forced anonymization
            mappings = {tag: name_part}

        # Clean up any extra whitespace or newlines
        anonymized_name = anonymized_name.strip()

        # Reconstruct the filename
        return f"{anonymized_name}_{id_part}_{suffix_part}", mappings
    
    def anonymize_filename(self, filename: str, is_directory: bool = False) -> Tuple[str, Dict[str, str]]:
        """Anonymize a filename using LLM to detect and redact PII.
        
        Uses the LLM to intelligently detect PII in filenames and redact only
        the sensitive parts while preserving structure and extensions.
        
        Args:
            filename: Original filename
            is_directory: Whether this is a directory name (unused but kept for compatibility)

        Returns:
            Tuple of (anonymized filename, mappings dict)
        """
        # Special case: Never redact moodle_grades.csv
        if filename == 'moodle_grades.csv':
            return filename, {}

        # Special handling for Moodle submission directories
        if self.is_moodle_submission(filename):
            return self.anonymize_moodle_submission(filename)
        
        # Separate the extension from the base name for files
        path = Path(filename)
        if not is_directory and path.suffix:
            # Get all extensions (handles cases like .tar.gz)
            ext = ''.join(path.suffixes)
            base_name = str(path).replace(ext, '')
        else:
            ext = ''
            base_name = filename
        
        # Use the LLM to anonymize the base name
        # The LLM will detect names, emails, phones, etc. and replace with standard tokens
        anonymized_base, mappings = self.anonymizer.anonymize_data(base_name)
        anonymized_filename = anonymized_base.strip()
        if ext:
            anonymized_filename += ext

        # mappings is now a flat dict: token -> original
        return anonymized_filename, mappings
        
    def anonymize_file_content(self, file_path: Path) -> Tuple[str, Dict[str, str]]:
        """Anonymize the content of a single file.

        Args:
            file_path: Path to the file

        Returns:
            Tuple of (anonymized content, flat mappings dict)
        """
        try:
            # Special handling for moodle_grades.csv
            if file_path.name == 'moodle_grades.csv':
                # Lazy import to avoid circular dependency
                if self.moodle_grades_handler is None:
                    from shilads_helpers.tools.moodle_prep.moodle_grades_handler import MoodleGradesHandler
                    self.moodle_grades_handler = MoodleGradesHandler()
                LOG.info(f"Using specialized handler for {file_path.name}")
                return self.moodle_grades_handler.anonymize_moodle_grades(file_path)

            # Default LLM-based anonymization for other files
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Returns flat dict: token -> original
            anonymized_content, mappings = self.anonymizer.anonymize_data(content)
            return anonymized_content, mappings

        except Exception as e:
            LOG.warning(f"Could not process file {file_path}: {e}")
            raise
            
    def process_directory(self,
                         input_dir: str,
                         output_dir: Optional[str] = None) -> Dict[str, Any]:
        """Process an entire directory tree.

        Args:
            input_dir: Input directory path
            output_dir: Output directory path (from config if not specified)

        Returns:
            Dictionary with all mappings and statistics
        """
        input_path = Path(input_dir).resolve()
        if not input_path.exists():
            raise ValueError(f"Input directory does not exist: {input_path}")
            
        # Determine output directory
        if output_dir is None:
            output_dir = self.anon_config['output']['output_dir']
        output_path = Path(output_dir).resolve()

        # Collect all files to process
        files_to_process = self.gather_files_to_process(input_path)
        self.all_mappings['statistics']['total_files'] = len(files_to_process)

        # Process files with progress bar
        with tqdm(total=len(files_to_process), desc="Anonymizing files") as pbar:
            for file_path in files_to_process:
                try:
                    self.anonymize_one_file(file_path, input_path, output_path)
                except Exception as e:
                    LOG.error(f"Error processing {file_path}: {e}")
                    self.all_mappings['statistics']['errors'].append({
                        'file': str(file_path),
                        'error': str(e)
                    })
                    self.all_mappings['statistics']['skipped_files'] += 1
                    
                pbar.update(1)
                
        # Save mapping file to output directory
        mapping_filename = Path(self.anon_config['output']['mapping_file']).name
        mapping_file = output_path / mapping_filename
        with open(mapping_file, 'w') as f:
            json.dump(self.all_mappings, f, indent=2)
        LOG.info(f"Anonymization complete. Mapping saved to {mapping_file}")
        
        # Create report if requested
        if self.anon_config['options']['create_report']:
            self.create_report(output_path)
            
        return self.all_mappings

    def anonymize_one_file(self, file_path, input_path, output_path):
        # Determine output file path and create it
        rel_path = file_path.relative_to(input_path)
        if self.anonymize_filenames:
            out_rel_path = self.anonymize_file_path(file_path, rel_path)
        else:
            out_rel_path = rel_path
        out_file_path = output_path / out_rel_path
        out_file_path.parent.mkdir(parents=True, exist_ok=True)

        # Anonymize content
        anon_content, content_mappings = self.anonymize_file_content(file_path)
        with open(out_file_path, 'w', encoding='utf-8') as f:
            f.write(anon_content)

        # Add content mappings to unified mappings
        # content_mappings is now a flat dict: token -> original
        self.all_mappings['mappings'].update(content_mappings)
        self.all_mappings['statistics']['processed_files'] += 1

    def gather_files_to_process(self, input_path):
        files_to_process = []
        moodle_csv_path = None

        for root, dirs, files in os.walk(input_path):
            root_path = Path(root)

            # Filter out excluded directories
            excluded_dirs = []
            for d in dirs:
                if self.should_exclude_dir(root_path / d):
                    LOG.warning(f"Skipping directory (matches exclude pattern): {root_path / d}")
                    excluded_dirs.append(d)
            dirs[:] = [d for d in dirs if d not in excluded_dirs]

            for file in files:
                file_path = root_path / file
                if self.should_process_file(file_path):
                    # Check if this is moodle_grades.csv
                    if file == 'moodle_grades.csv' and root_path == input_path:
                        moodle_csv_path = file_path
                    else:
                        files_to_process.append(file_path)

        # Sort files by path length (shorter paths first)
        # This ensures parent directories are processed before their children
        files_to_process.sort(key=lambda p: (len(p.parts), str(p)))

        # Process moodle_grades.csv first if it exists
        if moodle_csv_path:
            files_to_process.insert(0, moodle_csv_path)
            LOG.info("Processing moodle_grades.csv first to establish canonical name mappings")

        return files_to_process

    def anonymize_file_path(self, file_path, rel_path):
        # Build the anonymized path by looking up parent and anonymizing the last part
        parent_path = rel_path.parent
        # Look up or build the anonymized parent path
        if parent_path == Path('.'):
            # Top-level file/directory
            anonymized_parent = Path('.')
        else:
            # Build parent path from cached components
            # Since we process shortest paths first, all parent components should be cached
            anonymized_parts = []
            current_path = ""

            for part in parent_path.parts:
                # Build the key for this path component
                current_path = str(Path(current_path) / part) if current_path else part

                if current_path in self.path_cache:
                    # Use the cached anonymized version
                    anonymized_parts = list(self.path_cache[current_path].parts)
                else:
                    # This directory component hasn't been seen yet (first file in this directory)
                    # Anonymize this directory component
                    anon_part, part_mappings = self.anonymize_filename(part, is_directory=True)
                    self.all_mappings['mappings'].update(part_mappings)
                    anonymized_parts.append(anon_part)
                    # Cache the anonymized path
                    self.path_cache[current_path] = Path(*anonymized_parts)

            anonymized_parent = Path(*anonymized_parts) if anonymized_parts else Path('.')

        # Anonymize the last component (the actual file or final directory)
        last_part = rel_path.name
        is_file = file_path.is_file()
        anonymized_last, last_mappings = self.anonymize_filename(last_part, is_directory=not is_file)
        self.all_mappings['mappings'].update(last_mappings)

        # Build the complete anonymized path
        if anonymized_parent == Path('.'):
            out_rel_path = Path(anonymized_last)
        else:
            out_rel_path = anonymized_parent / anonymized_last

        # Cache this complete path
        self.path_cache[str(rel_path)] = out_rel_path

        return out_rel_path

    def create_report(self, output_path: Path):
        """Create a summary report of the anonymization.

        Args:
            output_path: Path where output was written
        """
        report_path = output_path / 'anonymization_report.txt'

        with open(report_path, 'w') as f:
            f.write("Anonymization Report\n")
            f.write("=" * 50 + "\n\n")

            stats = self.all_mappings['statistics']
            f.write(f"Total files found: {stats['total_files']}\n")
            f.write(f"Files processed: {stats['processed_files']}\n")
            f.write(f"Files skipped: {stats['skipped_files']}\n")

            if stats['errors']:
                f.write(f"\nErrors encountered: {len(stats['errors'])}\n")
                for error in stats['errors'][:10]:  # Show first 10 errors
                    f.write(f"  - {error['file']}: {error['error']}\n")

            f.write("\n" + "=" * 50 + "\n")
            f.write("Anonymization summary:\n")

            # Count anonymization replacements by type (PERSON, EMAIL, etc.)
            type_counts = {}
            for token, original in self.all_mappings['mappings'].items():
                # Extract type from token (e.g., REDACTED_PERSON1 -> PERSON)
                if token.startswith('REDACTED_'):
                    # Extract the type part (everything between REDACTED_ and the number)
                    import re
                    match = re.match(r'REDACTED_([A-Z]+)\d*', token)
                    if match:
                        pii_type = match.group(1)
                        type_counts[pii_type] = type_counts.get(pii_type, 0) + 1

            for pii_type, count in sorted(type_counts.items()):
                f.write(f"  - {pii_type}: {count} unique replacements\n")

        LOG.info(f"Report saved to {report_path}")