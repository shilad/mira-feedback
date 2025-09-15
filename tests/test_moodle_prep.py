"""Tests for Moodle submission preparation tool."""

import csv
import json
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from shilads_helpers.libs.config_loader import ConfigType
from shilads_helpers.tools.moodle_prep.processor import MoodleProcessor


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
from shilads_helpers.tools.moodle_prep.utils import (
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
        
        with patch('shilads_helpers.tools.moodle_prep.utils.convert_to_markdown') as mock_converter:
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
        with patch('shilads_helpers.tools.moodle_prep.processor.DirectoryAnonymizer'):
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
        with patch('shilads_helpers.tools.moodle_prep.processor.DirectoryAnonymizer'):
            results = processor.process(
                zip_path,
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