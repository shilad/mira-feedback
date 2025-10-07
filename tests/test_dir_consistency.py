"""Test directory name consistency in anonymization."""

import tempfile
import shutil
from pathlib import Path
import json
import pytest

from mira.libs.config_loader import ConfigType
from mira.tools.dir_anonymizer.anonymizer import DirectoryAnonymizer


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
                'create_report': False
            },
            'local_model': {
                'max_input_tokens': 1000,
                'presidio': {
                    'language': 'en',
                    'confidence_threshold': 0.3,
                    'nlp_configuration': {
                        'nlp_engine_name': 'spacy',
                        'models': [{'lang_code': 'en', 'model_name': 'en_core_web_lg'}]
                    }
                }
            }
        }
    }


@pytest.mark.slow_integration_test
@pytest.mark.skip(reason="Directory name PII detection not supported by Presidio backend - requires LLM backend")
def test_directory_name_consistency():
    """Test that the same directory name is consistently anonymized across the tree."""
    temp_dir = tempfile.mkdtemp()
    output_dir = tempfile.mkdtemp()

    try:
        # Create a directory structure with repeated directory names
        # Structure:
        # /John_Smith/
        #   project1/main.py
        #   project2/test.py
        # /data/John_Smith/
        #   analysis.py
        # /backup/John_Smith/
        #   old.py

        paths_to_create = [
            'John_Smith/project1',
            'John_Smith/project2',
            'data/John_Smith',
            'backup/John_Smith'
        ]

        for dir_path in paths_to_create:
            full_dir = Path(temp_dir) / dir_path
            full_dir.mkdir(parents=True, exist_ok=True)

            # Add a Python file to each directory
            (full_dir / 'test.py').write_text(f'# Code in {dir_path}\nprint("test")')

        # Run anonymization
        config = get_test_config()
        anonymizer = DirectoryAnonymizer(config=config, anonymize_filenames=True)
        results = anonymizer.process_directory(
            input_dir=temp_dir,
            output_dir=output_dir
        )

        # Load the mappings
        mapping_file = Path(output_dir) / 'anonymization_mapping.json'
        with open(mapping_file, 'r') as f:
            mappings = json.load(f)

        # Check that John_Smith was consistently anonymized
        unified_mappings = mappings.get('mappings', {})

        # Find the anonymized version of John_Smith
        john_smith_token = None
        for token, original in unified_mappings.items():
            if original == 'John_Smith':
                john_smith_token = token
                break

        assert john_smith_token is not None, "John_Smith should be in mappings"
        assert john_smith_token.startswith('REDACTED_'), f"Token should start with REDACTED_: {john_smith_token}"

        # Verify all John_Smith directories were renamed to the same token
        output_paths = list(Path(output_dir).rglob('*'))
        john_smith_dirs = [p for p in output_paths if john_smith_token in str(p)]

        # We should have multiple directories with the anonymized name
        assert len(john_smith_dirs) >= 4, f"Should have at least 4 paths containing {john_smith_token}"

        # Verify the structure is preserved
        expected_patterns = [
            f'{john_smith_token}/project1',
            f'{john_smith_token}/project2',
            f'data/{john_smith_token}',
            f'backup/{john_smith_token}'
        ]

        for pattern in expected_patterns:
            matching = [p for p in output_paths if pattern in str(p.relative_to(output_dir))]
            assert len(matching) > 0, f"Pattern {pattern} should exist in output"

        print(f"✓ Directory 'John_Smith' consistently anonymized to '{john_smith_token}'")
        print(f"✓ Found {len(john_smith_dirs)} paths with consistent anonymization")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        shutil.rmtree(output_dir, ignore_errors=True)


@pytest.mark.slow_integration_test
@pytest.mark.skip(reason="Directory name PII detection not supported by Presidio backend - requires LLM backend")
def test_nested_directory_consistency():
    """Test that nested directories with the same name are consistently anonymized."""
    temp_dir = tempfile.mkdtemp()
    output_dir = tempfile.mkdtemp()

    try:
        # Create nested structure with repeated names
        # Alice_Johnson/
        #   Alice_Johnson/
        #     code.py
        #   projects/
        #     Alice_Johnson/
        #       test.py

        paths = [
            'Alice_Johnson/Alice_Johnson',
            'Alice_Johnson/projects/Alice_Johnson'
        ]

        for dir_path in paths:
            full_dir = Path(temp_dir) / dir_path
            full_dir.mkdir(parents=True, exist_ok=True)
            (full_dir / 'test.py').write_text('print("test")')

        # Run anonymization
        config = get_test_config()
        anonymizer = DirectoryAnonymizer(config=config, anonymize_filenames=True)
        results = anonymizer.process_directory(
            input_dir=temp_dir,
            output_dir=output_dir
        )

        # Load mappings
        mapping_file = Path(output_dir) / 'anonymization_mapping.json'
        with open(mapping_file, 'r') as f:
            mappings = json.load(f)

        unified_mappings = mappings.get('mappings', {})

        # Find the token for Alice_Johnson
        alice_token = None
        for token, original in unified_mappings.items():
            if original == 'Alice_Johnson':
                alice_token = token
                break

        assert alice_token is not None, "Alice_Johnson should be in mappings"

        # Verify the nested structure uses the same token
        expected_paths = [
            Path(output_dir) / alice_token / alice_token / 'test.py',
            Path(output_dir) / alice_token / 'projects' / alice_token / 'test.py'
        ]

        for expected_path in expected_paths:
            assert expected_path.exists(), f"Path should exist: {expected_path}"

        print(f"✓ Nested directories 'Alice_Johnson' all anonymized to '{alice_token}'")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        shutil.rmtree(output_dir, ignore_errors=True)