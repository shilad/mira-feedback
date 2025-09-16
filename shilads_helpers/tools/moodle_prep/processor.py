"""Core processor for Moodle submission preparation."""

import logging
import shutil
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Set

from shilads_helpers.libs.config_loader import ConfigType
from shilads_helpers.tools.dir_anonymizer.anonymizer import DirectoryAnonymizer
from shilads_helpers.tools.moodle_prep.utils import (
    process_html_files,
    generate_grades_csv_from_data,
    parse_moodle_dirname,
    convert_html_to_markdown
)

LOG = logging.getLogger(__name__)


class MoodleProcessor:
    """Process Moodle homework submissions through three stages."""

    def __init__(self, config: ConfigType, working_dir: Path, keep_html: bool = False, dry_run: bool = False):
        """Initialize the processor.

        Args:
            config: Configuration dictionary
            working_dir: Base directory for all processing stages
            keep_html: If True, keep HTML files alongside Markdown
            dry_run: If True, don't write any files
        """
        self.config = config
        self.working_dir = Path(working_dir)
        self.keep_html = keep_html
        self.dry_run = dry_run
        
        # Define stage directories
        self.stage_dirs = {
            '0_submitted': self.working_dir / '0_submitted',
            '1_prep': self.working_dir / '1_prep',
            '2_redacted': self.working_dir / '2_redacted'
        }
        
        # Store submission data for moodle_grades.csv generation
        self.all_submissions_data = []
        
        # Tracking for processing
        self.stats = {
            'files_extracted': 0,
            'files_converted': 0,
            'files_redacted': 0,
            'errors': []
        }
    
    def process(self, zip_path: Path, 
                skip_stages: Optional[Set[str]] = None) -> Dict:
        """Process Moodle submissions through all stages.
        
        Args:
            zip_path: Path to submissions zip file
            skip_stages: Set of stage names to skip
            
        Returns:
            Dictionary with processing statistics and results
        """
        skip_stages = skip_stages or set()
        
        # Clear existing working directory if it exists and we're running stage 1
        if not self.dry_run:
            if '0_submitted' not in skip_stages and self.working_dir.exists():
                LOG.info(f"Clearing existing working directory: {self.working_dir}")
                shutil.rmtree(self.working_dir)
            self.working_dir.mkdir(parents=True, exist_ok=True)
        
        # Stage 1: Extract and organize
        if '0_submitted' not in skip_stages:
            LOG.info("Stage 1: Extracting submissions...")
            self._stage1_extract(zip_path)
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
            'stage_dirs': {k: str(v) for k, v in self.stage_dirs.items()}
        }
    
    def _stage1_extract(self, zip_path: Path):
        """Stage 1: Extract zip to stage 0.
        
        Online text submissions are NOT copied to stage 0 but their data is preserved.
        """
        stage_dir = self.stage_dirs['0_submitted']
        
        if not self.dry_run:
            stage_dir.mkdir(parents=True, exist_ok=True)
            
            LOG.info(f"Extracting {zip_path}...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Extract everything to stage 0 first
                zip_ref.extractall(stage_dir)
                self.stats['files_extracted'] = len(zip_ref.namelist())
            
            # Collect submission data and remove onlinetext directories
            self.all_submissions_data = []
            removed_count = 0
            
            for item in list(stage_dir.iterdir()):
                if item.is_dir():
                    student_name, student_id, submission_type = parse_moodle_dirname(item.name)
                    
                    if student_name and student_id:
                        # Create submission record
                        submission_record = {
                            "name": student_name,
                            "id": student_id,
                            "type": submission_type,
                            "online_text": "",
                            "online_text_full": ""  # Store full content for file creation
                        }

                        # If online text, capture content before removing
                        if submission_type == "onlinetext":
                            # Look for onlinetext files
                            for ext in ['.html', '.md', '.txt']:
                                text_file = item / f"onlinetext{ext}"
                                if text_file.exists():
                                    try:
                                        content = text_file.read_text(encoding='utf-8', errors='ignore')
                                        # Convert HTML to Markdown if it's an HTML file
                                        if ext == '.html':
                                            content = convert_html_to_markdown(content)
                                        # Store full content for file creation
                                        submission_record["online_text_full"] = content
                                        # Store up to 1000 characters for CSV
                                        submission_record["online_text"] = content[:1000] if len(content) > 1000 else content
                                        break
                                    except Exception as e:
                                        LOG.warning(f"Could not read online text from {text_file}: {e}")
                            
                            # Remove the directory
                            shutil.rmtree(item)
                            removed_count += 1
                            LOG.debug(f"Removed onlinetext submission: {item.name}")
                        
                        self.all_submissions_data.append(submission_record)
            
            LOG.info(f"Kept {len(list(stage_dir.iterdir()))} file submissions in stage 0")
            LOG.info(f"Collected data for {len(self.all_submissions_data)} total submissions")
            if removed_count > 0:
                LOG.info(f"Removed {removed_count} online text directories (content preserved for moodle_grades.csv)")
            
        else:
            LOG.info("[DRY RUN] Would extract zip to stage 0")
            # Count files in zip for stats
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                self.stats['files_extracted'] = len(zip_ref.namelist())
    
    def _stage2_prepare(self):
        """Stage 2: Generate moodle_grades.csv, convert HTML to Markdown, and create moodle_comments.txt files."""
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

            # Generate moodle_grades.csv from collected submission data
            grades_dest = stage_dir / 'moodle_grades.csv'
            grades_stats = generate_grades_csv_from_data(self.all_submissions_data, grades_dest)
            LOG.info(f"Generated moodle_grades.csv with {grades_stats['total_students']} students")

            # Create moodle_comments.txt files for online text submissions
            online_text_count = 0
            for submission in self.all_submissions_data:
                if submission.get("online_text_full"):
                    # Find the corresponding directory in stage_dir
                    # Look for directories that start with the student's name and ID
                    for item in stage_dir.iterdir():
                        if item.is_dir():
                            dir_student_name, dir_student_id, _ = parse_moodle_dirname(item.name)
                            if (dir_student_name == submission["name"] and
                                dir_student_id == submission["id"]):
                                # Create moodle_comments.txt in this directory
                                comments_file = item / "moodle_comments.txt"
                                comments_file.write_text(submission["online_text_full"], encoding='utf-8')
                                online_text_count += 1
                                LOG.debug(f"Created moodle_comments.txt for {submission['name']}")
                                break

            if online_text_count > 0:
                LOG.info(f"Created {online_text_count} moodle_comments.txt files for online text submissions")

            # Convert HTML files to Markdown
            self.stats['files_converted'] = process_html_files(stage_dir, self.keep_html)

        else:
            LOG.info("[DRY RUN] Would generate moodle_grades.csv, convert HTML files to Markdown, and create moodle_comments.txt files")
    
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
            anonymizer = DirectoryAnonymizer(config=self.config, anonymize_filenames=True)  # Anonymize filenames for full privacy
            
            # Run anonymization
            results = anonymizer.process_directory(
                input_dir=str(source_dir),
                output_dir=str(stage_dir)
            )
            
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