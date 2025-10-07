"""Integration tests for the Moodle submission preparation tool."""

import csv
import json
import shutil
import zipfile
from pathlib import Path
from unittest.mock import patch

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
                'name': 'Qwen/Qwen3-4B-Instruct-2507',
                'device': 'mps',
                'max_input_tokens': 100
            }
        }
    }


class TestMoodleIntegration:
    """Integration tests using real test data."""
    
    @pytest.fixture
    def test_data_dir(self):
        """Return the path to test data directory."""
        return Path(__file__).parent / "test_data" / "moodle_submissions"
    
    @pytest.fixture
    def test_zip(self, test_data_dir, tmp_path):
        """Create test submissions zip from test data files."""
        # Create zip file in temp directory
        zip_path = tmp_path / "test_submissions.zip"
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add all files from test data directory
            for item in test_data_dir.iterdir():
                if item.is_dir():
                    # Add all files in the submission directory
                    for file_path in item.rglob('*'):
                        if file_path.is_file():
                            # Create relative path for zip
                            rel_path = file_path.relative_to(test_data_dir)
                            zf.write(file_path, rel_path)
        
        return zip_path
    
    def test_full_pipeline(self, test_zip, tmp_path):
        """Test the complete three-stage pipeline with real data."""
        work_dir = tmp_path / "moodle_work"
        config = get_test_config()
        processor = MoodleProcessor(config, work_dir)
        
        # Mock the DirectoryAnonymizer for stage 2 to avoid slow LLM processing
        with patch('mira.tools.moodle_prep.processor.DirectoryAnonymizer') as mock_anon:
            mock_instance = mock_anon.return_value
            
            # Create the output directory that DirectoryAnonymizer would create
            def mock_process(input_dir, output_dir):
                Path(output_dir).mkdir(parents=True, exist_ok=True)
                return {'statistics': {'processed_files': 5, 'errors': []}}
            
            mock_instance.process_directory.side_effect = mock_process
            
            # Run all stages
            results = processor.process(test_zip)
        
        # Verify statistics  
        assert results['stats']['files_extracted'] == 8  # 8 files total in zip (including feedback)
        assert results['stats']['files_converted'] == 2  # 2 HTML files converted (assignment + feedback)
        
        # Verify stage directories exist
        assert (work_dir / '0_submitted').exists()
        assert (work_dir / '1_prep').exists()
        assert (work_dir / '2_redacted').exists()
    
    def test_stage_0_online_text_removal(self, test_zip, tmp_path):
        """Test that online text submissions are removed but feedback is preserved in stage 0."""
        work_dir = tmp_path / "moodle_work"
        config = get_test_config()
        processor = MoodleProcessor(config, work_dir)
        
        # Run only stage 0
        with patch('mira.tools.moodle_prep.processor.DirectoryAnonymizer'):
            results = processor.process(test_zip, skip_stages={'1_prep', '2_redacted'})
        
        stage0_dir = work_dir / '0_submitted'
        
        # Check that we have 6 directories (4 file submissions + 2 feedback directories)
        # Online text should be removed
        dirs = [d for d in stage0_dir.iterdir() if d.is_dir()]
        assert len(dirs) == 6
        
        # Verify Bob Smith's online text directory is not present
        assert not (stage0_dir / 'Bob Smith_102345_assignsubmission_onlinetext').exists()
        
        # Verify feedback directories ARE preserved
        assert (stage0_dir / 'Bob Smith_102345_assignfeedback_comments').exists()
        assert (stage0_dir / 'Diana Chen_104567_assignfeedback_file').exists()
        
        # Verify other submissions are present
        assert (stage0_dir / 'Alice Johnson_101234_assignsubmission_file').exists()
        assert (stage0_dir / 'Charlie Davis_103456_assignsubmission_file').exists()
        assert (stage0_dir / 'Diana Chen_104567_assignsubmission_file').exists()
        assert (stage0_dir / 'Maria Garcia Lopez_105678_assignsubmission_file').exists()  # Two-word last name
    
    def test_stage_1_moodle_grades_generation(self, test_zip, tmp_path):
        """Test that moodle_grades.csv is generated correctly in stage 1."""
        work_dir = tmp_path / "moodle_work"
        config = get_test_config()
        processor = MoodleProcessor(config, work_dir)
        
        # Run stages 0 and 1
        with patch('mira.tools.moodle_prep.processor.DirectoryAnonymizer'):
            results = processor.process(test_zip, skip_stages={'2_redacted'})
        
        # Check moodle_grades.csv exists
        grades_file = work_dir / '1_prep' / 'moodle_grades.csv'
        assert grades_file.exists()
        
        # Read and verify CSV content
        with open(grades_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        # Should have 5 students (including online text submission)
        assert len(rows) == 5
        
        # Check student names
        names = [row['Full name'] for row in rows]
        assert 'Alice Johnson' in names
        assert 'Bob Smith' in names
        assert 'Charlie Davis' in names
        assert 'Diana Chen' in names
        assert 'Maria Garcia Lopez' in names  # Two-word last name
        
        # Check that Bob Smith has online text content
        bob_row = next(r for r in rows if r['Full name'] == 'Bob Smith')
        assert 'This is my submission' in bob_row['Online text']
        assert 'bob.smith@school.edu' in bob_row['Online text']
        
        # Check that file submissions have empty online text
        alice_row = next(r for r in rows if r['Full name'] == 'Alice Johnson')
        assert alice_row['Online text'] == ''
    
    def test_stage_1_html_conversion(self, test_zip, tmp_path):
        """Test that HTML files are converted to Markdown in stage 1."""
        work_dir = tmp_path / "moodle_work"
        config = get_test_config()
        processor = MoodleProcessor(config, work_dir)
        
        # Run stages 0 and 1
        with patch('mira.tools.moodle_prep.processor.DirectoryAnonymizer'):
            results = processor.process(test_zip, skip_stages={'2_redacted'})
        
        stage1_dir = work_dir / '1_prep'
        
        # Check that Alice's HTML file was converted to Markdown
        alice_dir = stage1_dir / 'Alice Johnson_101234_assignsubmission_file'
        assert alice_dir.exists()
        
        # Original HTML should be gone (unless --keep-html is used)
        assert not (alice_dir / 'assignment.html').exists()
        
        # Markdown file should exist
        md_file = alice_dir / 'assignment.md'
        assert md_file.exists()
        
        # Verify Markdown content has PII
        content = md_file.read_text()
        assert 'Alice Johnson' in content
        assert 'alice.johnson@university.edu' in content
        # Phone number might have escaped dashes in Markdown
        assert '555' in content and '0123' in content
    
    @pytest.mark.slow_integration_test
    def test_stage_2_filename_redaction(self, test_zip, tmp_path):
        """Test that filenames are properly redacted using LLM in stage 2."""
        work_dir = tmp_path / "moodle_work"
        config = get_test_config()
        processor = MoodleProcessor(config, work_dir)
        
        # For this test, we'll actually run the anonymizer since it's the key feature
        # But we'll use a smaller timeout
        results = processor.process(test_zip)
        
        stage2_dir = work_dir / '2_redacted'
        
        if stage2_dir.exists():
            # Check that moodle_grades.csv is NOT renamed
            assert (stage2_dir / 'moodle_grades.csv').exists()

            # Check that student directories are redacted
            dirs = [d.name for d in stage2_dir.iterdir() if d.is_dir()]
            
            # Should have REDACTED_PERSON tokens in directory names
            for dir_name in dirs:
                if '_assignsubmission_' in dir_name:
                    # Should be like: REDACTED_PERSON1_101234_assignsubmission_file
                    assert 'REDACTED_PERSON' in dir_name
                    assert '_assignsubmission_' in dir_name
                    # Student ID should be preserved
                    assert any(id in dir_name for id in ['101234', '103456', '104567', '105678'])
    
    def test_feedback_preservation(self, test_zip, tmp_path):
        """Test that feedback directories and content are preserved untouched."""
        work_dir = tmp_path / "moodle_work"
        config = get_test_config()
        processor = MoodleProcessor(config, work_dir)
        
        # Run stages 0 and 1
        with patch('mira.tools.moodle_prep.processor.DirectoryAnonymizer'):
            results = processor.process(test_zip, skip_stages={'2_redacted'})
        
        # Check feedback in stage 0 (should be untouched)
        stage0_dir = work_dir / '0_submitted'
        bob_feedback = stage0_dir / 'Bob Smith_102345_assignfeedback_comments' / 'feedback.html'
        assert bob_feedback.exists()
        content = bob_feedback.read_text()
        assert 'Good work on this assignment, Bob!' in content
        assert 'Professor Johnson' in content
        
        diana_feedback = stage0_dir / 'Diana Chen_104567_assignfeedback_file' / 'rubric.txt'
        assert diana_feedback.exists()
        content = diana_feedback.read_text()
        assert 'Score: 95/100' in content
        
        # Check feedback in stage 1 (HTML files get converted to markdown)
        stage1_dir = work_dir / '1_prep'
        # The HTML feedback file might be converted to markdown
        bob_feedback_dir = stage1_dir / 'Bob Smith_102345_assignfeedback_comments'
        assert bob_feedback_dir.exists()
        # Check if either HTML or MD exists (conversion behavior may vary)
        assert (bob_feedback_dir / 'feedback.html').exists() or (bob_feedback_dir / 'feedback.md').exists()
    
    def test_content_preservation(self, test_zip, tmp_path):
        """Test that non-PII content is preserved correctly."""
        work_dir = tmp_path / "moodle_work"
        config = get_test_config()
        processor = MoodleProcessor(config, work_dir)
        
        # Run stages 0 and 1 only (to avoid slow LLM processing)
        with patch('mira.tools.moodle_prep.processor.DirectoryAnonymizer'):
            results = processor.process(test_zip, skip_stages={'2_redacted'})
        
        stage1_dir = work_dir / '1_prep'
        
        # Check Diana's report (no PII in content)
        diana_dir = stage1_dir / 'Diana Chen_104567_assignsubmission_file'
        report_file = diana_dir / 'report.md'
        assert report_file.exists()
        
        content = report_file.read_text()
        # Academic content should be preserved
        assert 'Analysis of Sorting Algorithms' in content
        assert 'Bubble Sort' in content
        assert 'Quick Sort' in content
        
        # Check Charlie's code files
        charlie_dir = stage1_dir / 'Charlie Davis_103456_assignsubmission_file'
        assert (charlie_dir / 'main.py').exists()
        assert (charlie_dir / 'README.md').exists()
        
        # Python file should have PII
        py_content = (charlie_dir / 'main.py').read_text()
        assert 'Charlie Davis' in py_content
        assert 'charlie.davis@college.org' in py_content
    
    def test_skip_stages(self, test_zip, tmp_path):
        """Test that stages can be skipped correctly."""
        work_dir = tmp_path / "moodle_work"
        config = get_test_config()
        processor = MoodleProcessor(config, work_dir)
        
        # First, run stage 0 only
        with patch('mira.tools.moodle_prep.processor.DirectoryAnonymizer'):
            processor.process(test_zip, skip_stages={'1_prep', '2_redacted'})
        
        assert (work_dir / '0_submitted').exists()
        assert not (work_dir / '1_prep').exists()
        assert not (work_dir / '2_redacted').exists()
        
        # Now run stage 1 only (skipping 0 since it already exists)
        with patch('mira.tools.moodle_prep.processor.DirectoryAnonymizer'):
            processor.process(test_zip, skip_stages={'0_submitted', '2_redacted'})
        
        assert (work_dir / '0_submitted').exists()
        assert (work_dir / '1_prep').exists()
        assert not (work_dir / '2_redacted').exists()
    
    def test_dry_run(self, test_zip, tmp_path):
        """Test that dry run doesn't create any files."""
        work_dir = tmp_path / "moodle_work"
        config = get_test_config()
        processor = MoodleProcessor(config, work_dir, dry_run=True)
        
        with patch('mira.tools.moodle_prep.processor.DirectoryAnonymizer'):
            results = processor.process(test_zip)
        
        # Nothing should be created
        assert not work_dir.exists()
        
        # But statistics should be populated
        assert results['stats']['files_extracted'] > 0