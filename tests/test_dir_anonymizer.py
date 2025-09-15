"""Tests for directory anonymizer."""

import os
import sys
import json
import tempfile
import shutil
from pathlib import Path
import pytest

from shilads_helpers.libs.config_loader import ConfigType
from shilads_helpers.tools.dir_anonymizer.anonymizer import DirectoryAnonymizer
from shilads_helpers.tools.dir_anonymizer.deanonymizer import DirectoryDeanonymizer


def get_test_config() -> ConfigType:
    """Create a test configuration."""
    return {
        'anonymizer': {
            'file_types': ['.py', '.yaml', '.md', '.txt'],
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


@pytest.fixture
def temp_test_dir():
    """Create a temporary test directory with sample files."""
    temp_dir = tempfile.mkdtemp()
    
    # Create test structure
    (Path(temp_dir) / 'src').mkdir()
    (Path(temp_dir) / 'docs').mkdir()
    (Path(temp_dir) / '.git').mkdir()  # Should be excluded
    
    # Create test files with PII
    test_content = {
        'src/main.py': """# Main script
# Author: John Smith
# Email: john.smith@example.com

def main():
    print("Contact us at +1-555-123-4567")
    return "Credit card: 4111-1111-1111-1111"
""",
        'src/config.yaml': """admin:
  name: Alice Johnson
  email: alice.j@company.com
  phone: (555) 987-6543
""",
        'docs/README.md': """# Project Documentation

Contact: Bob Wilson (bob.wilson@email.com)
Phone: +1 234-567-8900
Address: 123 Main St, Anytown, CA 12345
""",
        '.git/config': """[user]
    name = Test User
    email = test@example.com
"""
    }
    
    for file_path, content in test_content.items():
        full_path = Path(temp_dir) / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
        
    yield temp_dir
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.slow_integration_test
def test_anonymize_directory(temp_test_dir):
    """Test basic directory anonymization."""
    output_dir = tempfile.mkdtemp()
    
    try:
        # Create anonymizer with filename anonymization disabled for this test
        config = get_test_config()
        anonymizer = DirectoryAnonymizer(config=config, anonymize_filenames=False)
        
        # Process directory
        results = anonymizer.process_directory(
            input_dir=temp_test_dir,
            output_dir=output_dir,
            dry_run=False
        )
        
        # Check statistics
        assert results['statistics']['processed_files'] > 0
        assert results['statistics']['total_files'] > 0
        
        # Check that output files exist
        assert Path(output_dir).exists()
        assert list(Path(output_dir).rglob('*')) != []
        
        # Check mapping file was created in output directory
        mapping_file = Path(output_dir) / 'anonymization_mapping.json'
        assert mapping_file.exists()
        
        # Check .git was excluded
        assert not (Path(output_dir) / '.git').exists()
        
        # Check that content was anonymized
        src_main = Path(output_dir) / 'src' / 'main.py'
        assert src_main.exists()
        content = src_main.read_text()
        
        # Check that PII was anonymized with entity tags
        # Emails and phones should be replaced
        assert 'john.smith@example.com' not in content
        assert '+1-555-123-4567' not in content
        assert '4111-1111-1111-1111' not in content
        
        # Entity tags should be present
        assert 'REDACTED_EMAIL' in content or 'test@example.com' not in content
        assert 'REDACTED_PHONE' in content or '555-123-4567' not in content
        assert 'REDACTED_CREDITCARD' in content or '4111-1111-1111-1111' not in content
        
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)


@pytest.mark.slow_integration_test
def test_anonymize_and_restore(temp_test_dir):
    """Test anonymization and restoration roundtrip."""
    anon_dir = tempfile.mkdtemp()
    restored_dir = tempfile.mkdtemp()
    
    try:
        # Anonymize
        config = get_test_config()
        anonymizer = DirectoryAnonymizer(config=config)
        results = anonymizer.process_directory(
            input_dir=temp_test_dir,
            output_dir=anon_dir,
            dry_run=False
        )
        
        # Check mapping file exists in output directory
        mapping_file = Path(anon_dir) / 'anonymization_mapping.json'
        assert mapping_file.exists(), f"Mapping file should exist at {mapping_file}"
        
        # Restore
        deanonymizer = DirectoryDeanonymizer(str(mapping_file))
        restore_stats = deanonymizer.restore_directory(
            anonymized_dir=anon_dir,
            output_dir=restored_dir,
            restore_filenames=True
        )
        
        assert restore_stats['restored_files'] > 0
        
        # Compare original and restored content
        for orig_file in Path(temp_test_dir).rglob('*'):
            if orig_file.is_file() and '.git' not in str(orig_file):
                rel_path = orig_file.relative_to(temp_test_dir)
                restored_file = Path(restored_dir) / rel_path
                
                if restored_file.exists():
                    orig_content = orig_file.read_text()
                    restored_content = restored_file.read_text()
                    
                    # Content should match
                    assert orig_content == restored_content, f"Content mismatch in {rel_path}"
                    
    finally:
        shutil.rmtree(anon_dir, ignore_errors=True)
        shutil.rmtree(restored_dir, ignore_errors=True)


def test_dry_run(temp_test_dir):
    """Test dry run mode doesn't create files."""
    output_dir = tempfile.mkdtemp()

    try:
        config = get_test_config()
        anonymizer = DirectoryAnonymizer(config=config)
        
        # Run in dry-run mode
        results = anonymizer.process_directory(
            input_dir=temp_test_dir,
            output_dir=output_dir,
            dry_run=True
        )
        
        # Check statistics were collected
        assert results['statistics']['total_files'] > 0
        
        # But no files should be created
        assert not list(Path(output_dir).rglob('*'))
        
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)


def test_custom_config():
    """Test loading anonymizer with custom configuration."""
    custom_config = {
        'anonymizer': {
            'file_types': ['.txt', '.py'],
            'exclude_patterns': ['test_*'],
            'output': {
                'output_dir': 'custom_output',
                'mapping_file': 'custom_mapping.json'
            },
            'options': {
                'anonymize_filenames': True,
                'preserve_structure': True,
                'create_report': False
            },
            'custom_patterns': {}
        }
    }
    
    anonymizer = DirectoryAnonymizer(config=custom_config)
    
    # Check configuration was applied
    assert anonymizer.anon_config['file_types'] == ['.txt', '.py']
    assert anonymizer.anon_config['output']['output_dir'] == 'custom_output'
    assert anonymizer.anon_config['options']['anonymize_filenames'] is True


@pytest.mark.slow_integration_test
def test_file_type_filtering(temp_test_dir):
    """Test that only configured file types are processed."""
    # Create additional files with different extensions
    (Path(temp_test_dir) / 'image.jpg').write_text('binary data')
    (Path(temp_test_dir) / 'data.xlsx').write_text('excel data')
    
    output_dir = tempfile.mkdtemp()
    
    try:
        # Disable filename anonymization for this test
        config = get_test_config()
        anonymizer = DirectoryAnonymizer(config=config, anonymize_filenames=False)
        results = anonymizer.process_directory(
            input_dir=temp_test_dir,
            output_dir=output_dir,
            dry_run=False
        )
        
        # Image and Excel files should not be processed
        assert not (Path(output_dir) / 'image.jpg').exists()
        assert not (Path(output_dir) / 'data.xlsx').exists()
        
        # But Python and markdown files should be
        assert (Path(output_dir) / 'src' / 'main.py').exists()
        assert (Path(output_dir) / 'docs' / 'README.md').exists()
        
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)


@pytest.mark.slow_integration_test
def test_moodle_submission_anonymization():
    """Test anonymization of Moodle submission directories with various name formats.
    
    This test would have caught the issues with:
    - Uncommon names not being detected as names by LLM
    - Multi-part surnames having only partial name detection
    """
    # Create a temporary directory with Moodle submission structure
    temp_dir = tempfile.mkdtemp()
    output_dir = tempfile.mkdtemp()
    
    try:
        # Create Moodle submission directories with problematic made-up names
        test_submissions = [
            'Zephyr Quixote_325223_assignsubmission_file',  # Uncommon first and last name
            'Astrid Van Der Berg_325347_assignsubmission_file',  # Multi-part surname
            'Xavier De La Cruz_325234_assignsubmission_file',  # Multi-part surname with "De La"
            'Bob Smith_325233_assignsubmission_file',  # Common name (control)
            'Jane Doe_123456_assignsubmission_file'  # Common name (control)
        ]
        
        # Create the directories and add sample files
        for submission_dir in test_submissions:
            dir_path = Path(temp_dir) / submission_dir
            dir_path.mkdir(parents=True)
            
            # Add a sample file in each directory
            (dir_path / 'assignment.py').write_text(f"""
# Assignment submission
# Student work here
print("Hello World")
""")
        
        # Also create a moodle_grades.csv file with proper Moodle format
        (Path(temp_dir) / 'moodle_grades.csv').write_text("""Full name,Email address,Grade
Zephyr Quixote,zephyr.q@example.com,90
Astrid Van Der Berg,astrid.vdb@example.com,85
Xavier De La Cruz,xavier.dlc@example.com,92
Bob Smith,bob.smith@example.com,88
Jane Doe,jane.doe@example.com,95
""")
        
        # Run anonymization with filename anonymization enabled
        anonymizer = DirectoryAnonymizer(config=get_test_config(), anonymize_filenames=True)
        
        # First verify the Moodle detection works
        for submission_dir in test_submissions:
            assert anonymizer.is_moodle_submission(submission_dir), \
                f"Failed to detect {submission_dir} as Moodle submission"
        
        # Process the directory
        results = anonymizer.process_directory(
            input_dir=temp_dir,
            output_dir=output_dir,
            dry_run=False
        )
        
        # Check that all directories were anonymized
        output_dirs = [d.name for d in Path(output_dir).iterdir() if d.is_dir()]
        
        # All directories should have been anonymized
        for dir_name in output_dirs:
            # Should match pattern REDACTED_PERSON{N}_{ID}_assignsubmission_file
            assert 'REDACTED_PERSON' in dir_name, f"Directory {dir_name} not properly anonymized"
            
            # The original name should NOT appear in the anonymized version
            for original in ['Zephyr', 'Quixote', 'Astrid', 'Van', 'Der', 'Berg',
                           'Xavier', 'Cruz', 'Bob', 'Smith', 'Jane', 'Doe']:
                assert original not in dir_name, \
                    f"Name '{original}' leaked in anonymized directory: {dir_name}"

        # Check that moodle_grades.csv was not renamed
        assert (Path(output_dir) / 'moodle_grades.csv').exists(), \
            "moodle_grades.csv should not be renamed"
        
        # Load the mapping to verify proper anonymization
        mapping_file = Path(output_dir) / 'anonymization_mapping.json'
        assert mapping_file.exists(), "Mapping file should be created"
        
        with open(mapping_file, 'r') as f:
            mappings = json.load(f)
        
        # Verify each problematic name was properly anonymized
        files_mapping = mappings.get('files', {})
        
        # Check Zephyr Quixote - should be fully anonymized
        zephyr_key = 'Zephyr Quixote_325223_assignsubmission_file'
        assert zephyr_key in files_mapping, f"Zephyr Quixote directory should be in mappings"
        zephyr_anonymized = files_mapping[zephyr_key]
        assert 'Zephyr' not in zephyr_anonymized and 'Quixote' not in zephyr_anonymized, \
            f"Zephyr Quixote not fully anonymized: {zephyr_anonymized}"
        
        # Check Astrid Van Der Berg - all parts should be anonymized
        astrid_key = 'Astrid Van Der Berg_325347_assignsubmission_file'
        assert astrid_key in files_mapping, f"Astrid Van Der Berg directory should be in mappings"
        astrid_anonymized = files_mapping[astrid_key]
        assert 'Astrid' not in astrid_anonymized and 'Van' not in astrid_anonymized \
            and 'Der' not in astrid_anonymized and 'Berg' not in astrid_anonymized, \
            f"Astrid Van Der Berg not fully anonymized: {astrid_anonymized}"
        
        # Check Xavier De La Cruz - all parts should be anonymized
        xavier_key = 'Xavier De La Cruz_325234_assignsubmission_file'
        assert xavier_key in files_mapping, f"Xavier De La Cruz directory should be in mappings"
        xavier_anonymized = files_mapping[xavier_key]
        assert 'Xavier' not in xavier_anonymized and 'Cruz' not in xavier_anonymized, \
            f"Xavier De La Cruz not fully anonymized: {xavier_anonymized}"
        
        # Verify that content was properly anonymized in moodle_grades.csv
        content_mappings = mappings.get('content_mappings', {})
        assert 'moodle_grades.csv' in content_mappings, "moodle_grades.csv should have content mappings"
        grades_mappings = content_mappings['moodle_grades.csv']
        
        # Check that all the names were anonymized in the grades file
        assert 'Zephyr Quixote' in grades_mappings, "Zephyr Quixote should be in grades mappings"
        assert 'Astrid Van Der Berg' in grades_mappings, "Astrid Van Der Berg should be in grades mappings"
        assert 'Xavier De La Cruz' in grades_mappings, "Xavier De La Cruz should be in grades mappings"
        
        print("✓ All Moodle submission directories properly anonymized")
        print(f"✓ Processed {len(test_submissions)} submissions successfully")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        shutil.rmtree(output_dir, ignore_errors=True)