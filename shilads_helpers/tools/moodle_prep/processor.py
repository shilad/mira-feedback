"""Core processor for Moodle submission preparation."""

import json
import logging
import shutil
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Set

from shilads_helpers.tools.dir_anonymizer.anonymizer import DirectoryAnonymizer
from shilads_helpers.tools.moodle_prep.utils import (
    anonymize_csv,
    anonymize_directory_names,
    process_html_files
)

LOG = logging.getLogger(__name__)


class MoodleProcessor:
    """Process Moodle homework submissions through three stages."""
    
    def __init__(self, working_dir: Path, keep_html: bool = False, dry_run: bool = False):
        """Initialize the processor.
        
        Args:
            working_dir: Base directory for all processing stages
            keep_html: If True, keep HTML files alongside Markdown
            dry_run: If True, don't write any files
        """
        self.working_dir = Path(working_dir)
        self.keep_html = keep_html
        self.dry_run = dry_run
        
        # Define stage directories
        self.stage_dirs = {
            '0_submitted': self.working_dir / '0_submitted',
            '1_prep': self.working_dir / '1_prep',
            '2_redacted': self.working_dir / '2_redacted'
        }
        
        # Tracking for processing
        self.name_mapping = {}
        self.dir_mapping = {}
        self.stats = {
            'files_extracted': 0,
            'files_converted': 0,
            'students_anonymized': 0,
            'files_redacted': 0,
            'errors': []
        }
    
    def process(self, zip_path: Path, grades_path: Path, 
                skip_stages: Optional[Set[str]] = None) -> Dict:
        """Process Moodle submissions through all stages.
        
        Args:
            zip_path: Path to submissions zip file
            grades_path: Path to grading CSV file
            skip_stages: Set of stage names to skip
            
        Returns:
            Dictionary with processing statistics and results
        """
        skip_stages = skip_stages or set()
        
        # Create working directory if needed
        if not self.dry_run:
            self.working_dir.mkdir(parents=True, exist_ok=True)
        
        # Stage 1: Extract and organize
        if '0_submitted' not in skip_stages:
            LOG.info("Stage 1: Extracting submissions...")
            self._stage1_extract(zip_path, grades_path)
        else:
            LOG.info("Skipping Stage 1: 0_submitted")
        
        # Stage 2: Prepare and anonymize structure
        if '1_prep' not in skip_stages:
            LOG.info("Stage 2: Preparing and anonymizing structure...")
            self._stage2_prepare()
        else:
            LOG.info("Skipping Stage 2: 1_prep")
        
        # Stage 3: Redact PII content
        if '2_redacted' not in skip_stages:
            LOG.info("Stage 3: Redacting PII content...")
            self._stage3_redact()
        else:
            LOG.info("Skipping Stage 3: 2_redacted")
        
        return {
            'stats': self.stats,
            'name_mapping': self.name_mapping,
            'dir_mapping': self.dir_mapping,
            'stage_dirs': {k: str(v) for k, v in self.stage_dirs.items()}
        }
    
    def _stage1_extract(self, zip_path: Path, grades_path: Path):
        """Stage 1: Extract zip and copy grades."""
        stage_dir = self.stage_dirs['0_submitted']
        
        if not self.dry_run:
            stage_dir.mkdir(parents=True, exist_ok=True)
            
            # Extract zip file
            LOG.info(f"Extracting {zip_path}...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(stage_dir)
                self.stats['files_extracted'] = len(zip_ref.namelist())
            
            # Copy grades CSV
            grades_dest = stage_dir / 'grades.csv'
            shutil.copy2(grades_path, grades_dest)
            LOG.info(f"Copied grades to {grades_dest}")
        else:
            LOG.info("[DRY RUN] Would extract zip and copy grades")
            # Count files in zip for stats
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                self.stats['files_extracted'] = len(zip_ref.namelist())
    
    def _stage2_prepare(self):
        """Stage 2: Anonymize names and convert HTML."""
        source_dir = self.stage_dirs['0_submitted']
        stage_dir = self.stage_dirs['1_prep']
        
        if not source_dir.exists():
            LOG.error(f"Source directory {source_dir} does not exist. Run stage 1 first.")
            return
        
        if not self.dry_run:
            # Copy entire directory structure
            if stage_dir.exists():
                shutil.rmtree(stage_dir)
            shutil.copytree(source_dir, stage_dir)
            
            # Anonymize grades CSV
            grades_src = stage_dir / 'grades.csv'
            grades_dest = stage_dir / 'grades_anonymized.csv'
            
            if grades_src.exists():
                self.name_mapping = anonymize_csv(grades_src, grades_dest)
                self.stats['students_anonymized'] = len(self.name_mapping)
                
                # Save name mapping
                mapping_file = stage_dir / 'name_mapping.json'
                with open(mapping_file, 'w') as f:
                    json.dump(self.name_mapping, f, indent=2)
                LOG.info(f"Saved name mapping to {mapping_file}")
                
                # Remove original grades file
                grades_src.unlink()
            
            # Get directory mapping
            self.dir_mapping = anonymize_directory_names(stage_dir, self.name_mapping)
            
            # Rename directories
            for old_name, new_name in self.dir_mapping.items():
                old_path = stage_dir / old_name
                new_path = stage_dir / new_name
                if old_path.exists() and old_name != new_name:
                    old_path.rename(new_path)
                    LOG.debug(f"Renamed {old_name} to {new_name}")
            
            # Convert HTML files to Markdown
            self.stats['files_converted'] = process_html_files(stage_dir, self.keep_html)
            
        else:
            LOG.info("[DRY RUN] Would anonymize names and convert HTML files")
            # Simulate anonymization for dry run
            grades_src = source_dir / 'grades.csv'
            if grades_src.exists():
                # Count students in CSV
                import csv
                with open(grades_src, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    names = set()
                    for row in reader:
                        if row.get("Full name"):
                            names.add(row["Full name"])
                    self.stats['students_anonymized'] = len(names)
    
    def _stage3_redact(self):
        """Stage 3: Redact PII content using DirectoryAnonymizer."""
        source_dir = self.stage_dirs['1_prep']
        stage_dir = self.stage_dirs['2_redacted']
        
        if not source_dir.exists():
            LOG.error(f"Source directory {source_dir} does not exist. Run stage 2 first.")
            return
        
        if not self.dry_run:
            # Use DirectoryAnonymizer to redact PII
            LOG.info("Running PII redaction...")
            anonymizer = DirectoryAnonymizer(anonymize_filenames=False)  # Names already anonymized
            
            # Run anonymization
            results = anonymizer.process_directory(
                input_dir=source_dir,
                output_dir=stage_dir,
                dry_run=False
            )
            
            # Save anonymization map to prep directory (not redacted)
            if 'anonymization_map' in results:
                map_file = self.stage_dirs['1_prep'] / 'anonymization_map.json'
                with open(map_file, 'w') as f:
                    json.dump(results['anonymization_map'], f, indent=2)
                LOG.info(f"Saved anonymization map to {map_file}")
            
            # Update stats
            if 'statistics' in results:
                self.stats['files_redacted'] = results['statistics'].get('processed_files', 0)
                if results['statistics'].get('errors'):
                    self.stats['errors'].extend(results['statistics']['errors'])
            
        else:
            LOG.info("[DRY RUN] Would run PII redaction")
            # Count files for dry run
            file_count = sum(1 for _ in source_dir.rglob("*") if _.is_file())
            self.stats['files_redacted'] = file_count
    
    def get_stage_info(self) -> Dict[str, Dict]:
        """Get information about each stage directory.
        
        Returns:
            Dictionary with stage information
        """
        info = {}
        for stage_name, stage_dir in self.stage_dirs.items():
            if stage_dir.exists():
                file_count = sum(1 for _ in stage_dir.rglob("*") if _.is_file())
                dir_count = sum(1 for _ in stage_dir.iterdir() if _.is_dir())
                info[stage_name] = {
                    'path': str(stage_dir),
                    'exists': True,
                    'file_count': file_count,
                    'dir_count': dir_count
                }
            else:
                info[stage_name] = {
                    'path': str(stage_dir),
                    'exists': False,
                    'file_count': 0,
                    'dir_count': 0
                }
        return info