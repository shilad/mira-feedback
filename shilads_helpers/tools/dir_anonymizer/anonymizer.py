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

from shilads_helpers.libs.config_loader import load_all_configs, get_config
from shilads_helpers.libs.local_anonymizer import LocalAnonymizer

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)


class DirectoryAnonymizer:
    """Anonymize directory contents and optionally filenames."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, anonymize_filenames: Optional[bool] = None):
        """Initialize the anonymizer with configuration.
        
        Args:
            config: Configuration dict. If None, loads from config files.
            anonymize_filenames: Override for filename anonymization. If None, uses config value.
        """
        self.config = config or load_all_configs()
        self.anon_config = get_config('anonymizer', self.config)
        
        # Override anonymize_filenames if provided
        if anonymize_filenames is not None:
            if 'options' not in self.anon_config:
                self.anon_config['options'] = {}
            self.anon_config['options']['anonymize_filenames'] = anonymize_filenames
        
        # Initialize local LLM-based anonymizer from config
        self.anonymizer = LocalAnonymizer.create_from_config(self.anon_config)
        LOG.info("Using local LLM anonymizer")
        
        # Initialize Moodle grades handler lazily to avoid circular import
        self.moodle_grades_handler = None
        
        # Track all mappings
        self.all_mappings = {
            'files': {},
            'content_mappings': {},
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
    
    def anonymize_moodle_submission(self, filename: str) -> str:
        """Anonymize a Moodle submission directory name.
        
        Handles the special case of Moodle submission directories which contain
        student names that must be anonymized. Pattern: "Name_ID_assignsubmission_file"
        
        Args:
            filename: The Moodle submission directory name
            
        Returns:
            Anonymized directory name with student name replaced
        """
        import re
        moodle_pattern = r'^(.+?)_(\d+)_(assignsubmission_\w+)$'
        match = re.match(moodle_pattern, filename)
        
        if not match:
            # Shouldn't happen if is_moodle_submission was called first
            return filename
        
        name_part = match.group(1)
        id_part = match.group(2)
        suffix_part = match.group(3)
        
        # Try to anonymize using LLM first
        anonymized_name, _ = self.anonymizer.anonymize_data(name_part)
        
        # If LLM didn't detect it as a name, force anonymization
        # since we know this position contains a student name in Moodle format
        if anonymized_name == name_part:
            # Name wasn't detected by LLM, force anonymization
            # Check if we've seen this name before
            if name_part not in self.anonymizer.entity_memory:
                # Generate a new tag for this person
                self.anonymizer.entity_counters['persons'] += 1
                tag = f"REDACTED_PERSON{self.anonymizer.entity_counters['persons']}"
                self.anonymizer.entity_memory[name_part] = tag
            else:
                tag = self.anonymizer.entity_memory[name_part]
            anonymized_name = tag
        
        # Clean up any extra whitespace or newlines
        anonymized_name = anonymized_name.strip()
        
        # Reconstruct the filename
        return f"{anonymized_name}_{id_part}_{suffix_part}"
    
    def anonymize_filename(self, filename: str, is_directory: bool = False) -> str:
        """Anonymize a filename using LLM to detect and redact PII.
        
        Uses the LLM to intelligently detect PII in filenames and redact only
        the sensitive parts while preserving structure and extensions.
        
        Args:
            filename: Original filename
            is_directory: Whether this is a directory name (unused but kept for compatibility)
            
        Returns:
            Anonymized filename with PII replaced by standard redaction tokens
        """
        # Special case: Never redact moodle_grades.csv
        if filename == 'moodle_grades.csv':
            return filename
        
        # Special handling for Moodle submission directories
        if self.is_moodle_submission(filename):
            return self.anonymize_moodle_submission(filename)
        
        # For all other files, use LLM to detect and redact PII
        path = Path(filename)
        
        # Separate the extension from the base name for files
        if not is_directory and path.suffix:
            # Get all extensions (handles cases like .tar.gz)
            ext = ''.join(path.suffixes)
            base_name = str(path).replace(ext, '')
        else:
            ext = ''
            base_name = filename
        
        # Use the LLM to anonymize the base name
        # The LLM will detect names, emails, phones, etc. and replace with standard tokens
        anonymized_base, _ = self.anonymizer.anonymize_data(base_name)
        
        # Clean up any extra whitespace or newlines from LLM output
        anonymized_base = anonymized_base.strip()
        
        # Reconstruct the filename with the preserved extension
        if ext:
            return f"{anonymized_base}{ext}"
        else:
            return anonymized_base
        
    def anonymize_file_content(self, file_path: Path) -> Tuple[str, Dict[str, Any]]:
        """Anonymize the content of a single file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Tuple of (anonymized content, mappings)
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
                
            anonymized_content, mappings = self.anonymizer.anonymize_data(content)
            return anonymized_content, mappings
            
        except Exception as e:
            LOG.warning(f"Could not process file {file_path}: {e}")
            raise
            
    def process_directory(self, 
                         input_dir: str,
                         output_dir: Optional[str] = None,
                         dry_run: bool = False) -> Dict[str, Any]:
        """Process an entire directory tree.
        
        Args:
            input_dir: Input directory path
            output_dir: Output directory path (from config if not specified)
            dry_run: If True, don't write files, just return what would be done
            
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
        
        # Get options
        anonymize_filenames = self.anon_config['options']['anonymize_filenames']
        preserve_structure = self.anon_config['options']['preserve_structure']
        
        # Collect all files to process
        files_to_process = []
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
                    files_to_process.append(file_path)
                    
        self.all_mappings['statistics']['total_files'] = len(files_to_process)
        
        if dry_run:
            LOG.info(f"DRY RUN: Would process {len(files_to_process)} files")
            return self.all_mappings
            
        # Process files with progress bar
        with tqdm(total=len(files_to_process), desc="Anonymizing files") as pbar:
            for file_path in files_to_process:
                try:
                    # Determine output file path
                    rel_path = file_path.relative_to(input_path)
                    
                    if anonymize_filenames:
                        # Anonymize each part of the path
                        parts = list(rel_path.parts)
                        anonymized_parts = []
                        for i, part in enumerate(parts):
                            # Check if this is a file or directory
                            is_last = (i == len(parts) - 1)
                            is_dir = not is_last  # All parts except last are directories
                            
                            # For directories, first check if it matches Moodle pattern
                            # The Moodle check is done inside anonymize_filename
                            anon_part = self.anonymize_filename(part, is_directory=is_dir)
                            anonymized_parts.append(anon_part)
                            # Store mapping
                            self.all_mappings['files'][part] = anon_part
                        out_rel_path = Path(*anonymized_parts)
                    else:
                        out_rel_path = rel_path
                        
                    out_file_path = output_path / out_rel_path
                    
                    # Create output directory
                    out_file_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Anonymize content
                    anon_content, content_mappings = self.anonymize_file_content(file_path)
                    
                    # Write anonymized content
                    with open(out_file_path, 'w', encoding='utf-8') as f:
                        f.write(anon_content)
                        
                    # Store mappings
                    file_key = str(rel_path)
                    self.all_mappings['content_mappings'][file_key] = content_mappings
                    self.all_mappings['files'][file_key] = str(out_rel_path)
                    
                    self.all_mappings['statistics']['processed_files'] += 1
                    
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
            f.write("Anonymization types applied:\n")
            
            # Count anonymization types
            type_counts = {}
            for mappings in self.all_mappings['content_mappings'].values():
                for pattern_type in mappings.keys():
                    type_counts[pattern_type] = type_counts.get(pattern_type, 0) + len(mappings[pattern_type])
                    
            for pattern_type, count in type_counts.items():
                f.write(f"  - {pattern_type}: {count} replacements\n")
                
        LOG.info(f"Report saved to {report_path}")