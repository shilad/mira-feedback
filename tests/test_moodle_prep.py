"""Tests for Moodle submission preparation tool."""

import csv
import json
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from shilads_helpers.tools.moodle_prep.processor import MoodleProcessor
from shilads_helpers.tools.moodle_prep.utils import (
    anonymize_csv,
    parse_moodle_dirname,
    anonymize_directory_names,
    convert_html_to_markdown
)


class TestMoodleUtils:
    """Test utility functions."""
    
    def test_parse_moodle_dirname(self):
        """Test parsing Moodle directory names."""
        # Standard format
        name, id, type = parse_moodle_dirname("John Doe_12345_assignsubmission_file")
        assert name == "John Doe"
        assert id == "12345"
        assert type == "file"
        
        # Online text submission
        name, id, type = parse_moodle_dirname("Jane Smith_67890_assignsubmission_onlinetext")
        assert name == "Jane Smith"
        assert id == "67890"
        assert type == "onlinetext"
        
        # Invalid format
        name, id, type = parse_moodle_dirname("InvalidDirectory")
        assert name == "InvalidDirectory"
        assert id == ""
        assert type == ""
    
    def test_anonymize_csv(self, tmp_path):
        """Test CSV anonymization."""
        # Create test CSV
        csv_path = tmp_path / "test_grades.csv"
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=["Identifier", "Full name", "Email address", "Grade"])
            writer.writeheader()
            writer.writerows([
                {"Identifier": "001", "Full name": "John Doe", "Email address": "john@example.com", "Grade": "85"},
                {"Identifier": "002", "Full name": "Jane Smith", "Email address": "jane@example.com", "Grade": "92"},
                {"Identifier": "003", "Full name": "Bob Johnson", "Email address": "bob@example.com", "Grade": "78"},
            ])
        
        # Anonymize
        output_path = tmp_path / "anonymized.csv"
        name_mapping = anonymize_csv(csv_path, output_path)
        
        # Check mapping
        assert len(name_mapping) == 3
        assert "John Doe" in name_mapping
        assert "Jane Smith" in name_mapping
        assert "Bob Johnson" in name_mapping
        assert name_mapping["John Doe"] == "Student_001"
        assert name_mapping["Jane Smith"] == "Student_002"
        assert name_mapping["Bob Johnson"] == "Student_003"
        
        # Check output CSV
        with open(output_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
            # Email should be removed
            assert "Email address" not in reader.fieldnames
            
            # Names should be anonymized
            assert rows[0]["Full name"] == "Student_001"
            assert rows[1]["Full name"] == "Student_002"
            assert rows[2]["Full name"] == "Student_003"
            
            # Grades should be preserved
            assert rows[0]["Grade"] == "85"
            assert rows[1]["Grade"] == "92"
            assert rows[2]["Grade"] == "78"
    
    def test_anonymize_directory_names(self, tmp_path):
        """Test directory name anonymization."""
        # Create test directories
        (tmp_path / "John Doe_12345_assignsubmission_file").mkdir()
        (tmp_path / "Jane Smith_67890_assignsubmission_onlinetext").mkdir()
        (tmp_path / "Bob Johnson_11111_assignsubmission_file").mkdir()
        
        # Create name mapping
        name_mapping = {
            "John Doe": "Student_001",
            "Jane Smith": "Student_002",
            "Bob Johnson": "Student_003"
        }
        
        # Get directory mapping
        dir_mapping = anonymize_directory_names(tmp_path, name_mapping)
        
        # Check mappings
        assert dir_mapping["John Doe_12345_assignsubmission_file"] == "Student_001_12345_assignsubmission_file"
        assert dir_mapping["Jane Smith_67890_assignsubmission_onlinetext"] == "Student_002_67890_assignsubmission_onlinetext"
        assert dir_mapping["Bob Johnson_11111_assignsubmission_file"] == "Student_003_11111_assignsubmission_file"
    
    def test_convert_html_to_markdown(self):
        """Test HTML to Markdown conversion with html-to-markdown."""
        html = "<h1>Title</h1><p>This is a <strong>test</strong> paragraph.</p>"
        
        with patch('shilads_helpers.tools.moodle_prep.utils.convert_to_markdown') as mock_converter:
            mock_converter.return_value = "# Title\n\nThis is a **test** paragraph.\n"
            
            result = convert_html_to_markdown(html)
            
            assert result == "# Title\n\nThis is a **test** paragraph.\n"
            mock_converter.assert_called_once_with(html)


class TestMoodleProcessor:
    """Test the main processor."""
    
    def test_processor_initialization(self, tmp_path):
        """Test processor initialization."""
        processor = MoodleProcessor(tmp_path)
        
        assert processor.working_dir == tmp_path
        assert processor.stage_dirs['0_submitted'] == tmp_path / '0_submitted'
        assert processor.stage_dirs['1_prep'] == tmp_path / '1_prep'
        assert processor.stage_dirs['2_redacted'] == tmp_path / '2_redacted'
    
    def test_stage_info(self, tmp_path):
        """Test getting stage information."""
        processor = MoodleProcessor(tmp_path)
        
        # Create some test directories
        (tmp_path / '0_submitted').mkdir()
        (tmp_path / '0_submitted' / 'test.txt').write_text("test")
        
        info = processor.get_stage_info()
        
        assert info['0_submitted']['exists'] is True
        assert info['0_submitted']['file_count'] == 1
        assert info['1_prep']['exists'] is False
        assert info['2_redacted']['exists'] is False
    
    def test_dry_run_mode(self, tmp_path):
        """Test dry run mode doesn't create files."""
        # Create test files
        zip_path = tmp_path / "test.zip"
        grades_path = tmp_path / "grades.csv"
        work_dir = tmp_path / "work"
        
        # Create minimal test zip
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("test_file.txt", "test content")
        
        # Create minimal grades CSV
        with open(grades_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=["Full name", "Grade"])
            writer.writeheader()
            writer.writerow({"Full name": "Test Student", "Grade": "100"})
        
        # Run processor in dry run mode
        processor = MoodleProcessor(work_dir, dry_run=True)
        
        # Mock the DirectoryAnonymizer to avoid dependency issues
        with patch('shilads_helpers.tools.moodle_prep.processor.DirectoryAnonymizer'):
            results = processor.process(zip_path, grades_path)
        
        # Check that no directories were created
        assert not work_dir.exists()
        assert results['stats']['files_extracted'] == 1
    
    def test_skip_stages(self, tmp_path):
        """Test skipping stages."""
        # Create test files
        zip_path = tmp_path / "test.zip"
        grades_path = tmp_path / "grades.csv"
        work_dir = tmp_path / "work"
        
        # Create minimal test files
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("test_file.txt", "test content")
        grades_path.write_text("Full name,Grade\nTest,100\n")
        
        # Create processor
        processor = MoodleProcessor(work_dir)
        
        # Create stage 1 directory manually
        stage1_dir = work_dir / '0_submitted'
        stage1_dir.mkdir(parents=True)
        (stage1_dir / 'grades.csv').write_text("Full name,Grade\nTest,100\n")
        
        # Skip stage 1, only run stage 2
        with patch('shilads_helpers.tools.moodle_prep.processor.DirectoryAnonymizer'):
            results = processor.process(
                zip_path, 
                grades_path,
                skip_stages={'0_submitted', '2_redacted'}
            )
        
        # Check that stage 2 directory was created
        assert (work_dir / '1_prep').exists()


class TestCLI:
    """Test CLI functionality."""
    
    def test_cli_import(self):
        """Test that CLI can be imported."""
        from shilads_helpers.tools.moodle_prep import cli
        assert hasattr(cli, 'main')
    
    @patch('sys.argv', ['prep-moodle', '--help'])
    def test_cli_help(self):
        """Test CLI help message."""
        from shilads_helpers.tools.moodle_prep.cli import main
        
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        # Help should exit with 0
        assert exc_info.value.code == 0