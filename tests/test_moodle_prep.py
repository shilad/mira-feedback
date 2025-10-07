"""Tests for Moodle submission preparation tool."""

import csv
import json
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from mira.libs.config_loader import ConfigType
from mira.tools.moodle_prep.processor import MoodleProcessor


def get_test_config() -> ConfigType:
    """Create a test configuration."""
    return {
        'anonymizer': {
            'file_types': ['.py', '.yaml', '.md', '.txt', '.html'],
            'exclude_patterns': ['.git/*', '__pycache__/*'],
            'output': {
                'output_dir': 'anonymized_output',
                'mapping_file': 'anonymization_mapping.json'
            },
            'options': {
                'anonymize_filenames': True,
                'preserve_structure': True,
                'create_report': True
            },
            'local_model': {
                'name': 'microsoft/Phi-3-mini-4k-instruct',
                'device': 'cpu',
                'max_input_tokens': 100
            }
        }
    }
from mira.tools.moodle_prep.utils import (
    parse_moodle_dirname,
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
    
    
    def test_convert_html_to_markdown(self):
        """Test HTML to Markdown conversion with html-to-markdown."""
        html = "<h1>Title</h1><p>This is a <strong>test</strong> paragraph.</p>"
        
        with patch('mira.tools.moodle_prep.utils.convert_to_markdown') as mock_converter:
            mock_converter.return_value = "# Title\n\nThis is a **test** paragraph.\n"
            
            result = convert_html_to_markdown(html)
            
            assert result == "# Title\n\nThis is a **test** paragraph.\n"
            mock_converter.assert_called_once_with(html)


class TestMoodleProcessor:
    """Test the main processor."""
    
    def test_processor_initialization(self, tmp_path):
        """Test processor initialization."""
        config = get_test_config()
        processor = MoodleProcessor(config, tmp_path)
        
        assert processor.working_dir == tmp_path
        assert processor.stage_dirs['0_submitted'] == tmp_path / '0_submitted'
        assert processor.stage_dirs['1_prep'] == tmp_path / '1_prep'
        assert processor.stage_dirs['2_redacted'] == tmp_path / '2_redacted'
    
    def test_stage_info(self, tmp_path):
        """Test getting stage information."""
        config = get_test_config()
        processor = MoodleProcessor(config, tmp_path)
        
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
        work_dir = tmp_path / "work"
        
        # Create minimal test zip with Moodle directory structure
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("John Doe_12345_assignsubmission_file/test.txt", "test content")
            zf.writestr("Jane Smith_67890_assignsubmission_onlinetext/onlinetext.html", "<p>Online submission</p>")
        
        # Run processor in dry run mode
        config = get_test_config()
        processor = MoodleProcessor(config, work_dir, dry_run=True)
        
        # Mock the DirectoryAnonymizer to avoid dependency issues
        with patch('mira.tools.moodle_prep.processor.DirectoryAnonymizer'):
            results = processor.process(zip_path)
        
        # Check that no directories were created
        assert not work_dir.exists()
        assert results['stats']['files_extracted'] == 2
    
    def test_skip_stages(self, tmp_path):
        """Test skipping stages."""
        # Create test files
        zip_path = tmp_path / "test.zip"
        work_dir = tmp_path / "work"
        
        # Create minimal test files with Moodle structure
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("John Doe_12345_assignsubmission_file/test.txt", "test content")
        
        # Create processor
        config = get_test_config()
        processor = MoodleProcessor(config, work_dir)
        
        # Create stage 0 directory manually to test skipping
        stage0_dir = work_dir / '0_submitted'
        stage0_dir.mkdir(parents=True)
        (stage0_dir / 'John Doe_12345_assignsubmission_file').mkdir(parents=True)
        (stage0_dir / 'John Doe_12345_assignsubmission_file' / 'test.txt').write_text("test content")
        
        # Populate processor's submission data for stage 1
        processor.all_submissions_data = [
            {"name": "John Doe", "id": "12345", "type": "file", "online_text": ""}
        ]
        
        # Skip stage 0 and 2, only run stage 1
        with patch('mira.tools.moodle_prep.processor.DirectoryAnonymizer'):
            results = processor.process(
                zip_path,
                skip_stages={'0_submitted', '2_redacted'}
            )
        
        # Check that stage 2 directory was created
        assert (work_dir / '1_prep').exists()


    def test_online_text_to_moodle_comments(self, tmp_path):
        """Test that online text submissions create moodle_comments.txt files."""
        # Create test files
        zip_path = tmp_path / "test.zip"
        work_dir = tmp_path / "work"

        # Create test zip with both file and online text submissions
        with zipfile.ZipFile(zip_path, 'w') as zf:
            # File submission
            zf.writestr("John Doe_12345_assignsubmission_file/homework.py", "print('Hello World')")

            # Online text submission with HTML
            online_html = "<p>This is my <strong>online submission</strong>.</p><p>It has multiple paragraphs.</p>"
            zf.writestr("Jane Smith_67890_assignsubmission_onlinetext/onlinetext.html", online_html)

            # Another online text submission with plain text
            zf.writestr("Bob Johnson_11111_assignsubmission_onlinetext/onlinetext.txt", "Plain text submission content")

        # Run processor through stages 0 and 1
        config = get_test_config()
        processor = MoodleProcessor(config, work_dir)

        # Mock the DirectoryAnonymizer to avoid dependency issues
        with patch('mira.tools.moodle_prep.processor.DirectoryAnonymizer'):
            # Process only stages 0 and 1
            results = processor.process(zip_path, skip_stages={'2_redacted'})

        # Check stage 1_prep for moodle_comments.txt files
        stage1_dir = work_dir / '1_prep'

        # John Doe should have his file submission but no moodle_comments.txt
        john_dir = stage1_dir / "John Doe_12345_assignsubmission_file"
        assert john_dir.exists()
        assert (john_dir / "homework.py").exists()
        assert not (john_dir / "moodle_comments.txt").exists()

        # Jane Smith's online text should NOT have a directory (removed in stage 0)
        # But should have moodle_comments.txt in any existing directory for her
        jane_dir = stage1_dir / "Jane Smith_67890_assignsubmission_onlinetext"
        assert not jane_dir.exists()

        # Bob Johnson's online text should also not have a directory
        bob_dir = stage1_dir / "Bob Johnson_11111_assignsubmission_onlinetext"
        assert not bob_dir.exists()

        # Check that moodle_grades.csv was created and contains all students
        grades_file = stage1_dir / "moodle_grades.csv"
        assert grades_file.exists()

        with open(grades_file, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 3  # All three students should be in the CSV

            # Find Jane's entry and verify online text is captured (truncated)
            jane_row = next((r for r in rows if 'Jane Smith' in r.get('Full name', '')), None)
            assert jane_row is not None
            assert "online submission" in jane_row.get('Online text', '')

    def test_online_text_with_file_submission(self, tmp_path):
        """Test when a student has both file and online text submission."""
        # Create test files
        zip_path = tmp_path / "test.zip"
        work_dir = tmp_path / "work"

        # Create test zip with a student who has both submissions
        with zipfile.ZipFile(zip_path, 'w') as zf:
            # File submission for the same student
            zf.writestr("Alice Brown_99999_assignsubmission_file/project.py", "def main(): pass")
            # Online text submission for the same student
            zf.writestr("Alice Brown_99999_assignsubmission_onlinetext/onlinetext.html",
                       "<p>Here are my comments about the project</p>")

        # Run processor
        config = get_test_config()
        processor = MoodleProcessor(config, work_dir)

        with patch('mira.tools.moodle_prep.processor.DirectoryAnonymizer'):
            results = processor.process(zip_path, skip_stages={'2_redacted'})

        # Check that Alice has her file submission directory
        stage1_dir = work_dir / '1_prep'
        alice_dir = stage1_dir / "Alice Brown_99999_assignsubmission_file"
        assert alice_dir.exists()
        assert (alice_dir / "project.py").exists()

        # And she should have moodle_comments.txt with her online text
        comments_file = alice_dir / "moodle_comments.txt"
        assert comments_file.exists()

        # Verify content (should be converted from HTML to Markdown)
        content = comments_file.read_text()
        assert "comments about the project" in content


class TestCLI:
    """Test CLI functionality."""

    def test_cli_import(self):
        """Test that CLI can be imported."""
        from mira.tools.moodle_prep import cli
        assert hasattr(cli, 'main')

    @patch('sys.argv', ['prep-moodle', '--help'])
    def test_cli_help(self):
        """Test CLI help message."""
        from mira.tools.moodle_prep.cli import main

        with pytest.raises(SystemExit) as exc_info:
            main()

        # Help should exit with 0
        assert exc_info.value.code == 0