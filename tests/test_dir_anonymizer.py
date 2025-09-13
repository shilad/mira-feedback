"""Tests for directory anonymizer."""

import os
import sys
import json
import tempfile
import shutil
from pathlib import Path
import pytest

from shilads_helpers.tools.dir_anonymizer.anonymizer import DirectoryAnonymizer
from shilads_helpers.tools.dir_anonymizer.deanonymizer import DirectoryDeanonymizer


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


def test_anonymize_directory(temp_test_dir):
    """Test basic directory anonymization."""
    output_dir = tempfile.mkdtemp()
    
    try:
        # Create anonymizer with filename anonymization disabled for this test
        anonymizer = DirectoryAnonymizer(anonymize_filenames=False)
        
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
        
        # Check mapping file was created
        mapping_file = Path('anonymization_mapping.json')
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
        if Path('anonymization_mapping.json').exists():
            Path('anonymization_mapping.json').unlink()


def test_anonymize_and_restore(temp_test_dir):
    """Test anonymization and restoration roundtrip."""
    anon_dir = tempfile.mkdtemp()
    restored_dir = tempfile.mkdtemp()
    
    try:
        # Anonymize
        anonymizer = DirectoryAnonymizer()
        results = anonymizer.process_directory(
            input_dir=temp_test_dir,
            output_dir=anon_dir,
            dry_run=False
        )
        
        # Check mapping file exists
        mapping_file = Path('anonymization_mapping.json')
        assert mapping_file.exists()
        
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
        if Path('anonymization_mapping.json').exists():
            Path('anonymization_mapping.json').unlink()


def test_dry_run(temp_test_dir):
    """Test dry run mode doesn't create files."""
    output_dir = tempfile.mkdtemp()
    
    try:
        anonymizer = DirectoryAnonymizer()
        
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


def test_file_type_filtering(temp_test_dir):
    """Test that only configured file types are processed."""
    # Create additional files with different extensions
    (Path(temp_test_dir) / 'image.jpg').write_text('binary data')
    (Path(temp_test_dir) / 'data.xlsx').write_text('excel data')
    
    output_dir = tempfile.mkdtemp()
    
    try:
        # Disable filename anonymization for this test
        anonymizer = DirectoryAnonymizer(anonymize_filenames=False)
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
        if Path('anonymization_mapping.json').exists():
            Path('anonymization_mapping.json').unlink()