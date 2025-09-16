"""Test suite for local anonymizer with entity tags."""

import pytest
import tempfile
import shutil
import json
from pathlib import Path
from unittest.mock import Mock, patch

from shilads_helpers.libs.config_loader import ConfigType
from shilads_helpers.libs.local_anonymizer import LocalAnonymizer, LocalDeanonymizer
from shilads_helpers.tools.dir_anonymizer.anonymizer import DirectoryAnonymizer
from shilads_helpers.tools.dir_anonymizer.deanonymizer import DirectoryDeanonymizer


def get_test_config() -> ConfigType:
    """Create a test configuration for DirectoryAnonymizer."""
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
                'name': 'microsoft/Phi-3-mini-4k-instruct',
                'device': 'cpu',
                'max_input_tokens': 100
            }
        }
    }


@pytest.fixture
def mock_llm_backend():
    """Mock LLM backend to avoid model downloads during tests."""
    with patch('shilads_helpers.libs.local_anonymizer.anonymizer.LLMBackend') as mock:
        # Create a mock instance that returns empty PII detection
        mock_instance = Mock()
        mock_instance.detect_pii.return_value = {
            "persons": [],
            "emails": [],
            "phones": [],
            "addresses": [],
            "organizations": [],
            "credit_cards": [],
            "ssn": []
        }
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def temp_test_dir():
    """Create a temporary test directory with sample files."""
    temp_dir = tempfile.mkdtemp()
    
    # Create directory structure
    src_dir = Path(temp_dir) / "src"
    src_dir.mkdir()
    
    docs_dir = Path(temp_dir) / "docs"
    docs_dir.mkdir()
    
    # Create test files with PII
    (src_dir / "main.py").write_text("""
# Author: John Smith (john.smith@example.com)
# Phone: 555-123-4567

def process_user(email):
    # Process user with email
    return f"Processing {email}"
    
# Contact: jane.doe@example.com for questions
""")
    
    (src_dir / "config.json").write_text(json.dumps({
        "admin_email": "admin@example.com",
        "support_phone": "555-987-6543",
        "api_key": "not-really-pii-but-sensitive"
    }, indent=2))
    
    (docs_dir / "README.md").write_text("""
# Project Documentation

Contact Information:
- Lead Developer: Alice Johnson (alice@example.com)
- Support: 555-555-5555
- Address: 123 Main St, Springfield, IL 62701

## Contributors
- Bob Wilson (bob.wilson@example.com)
- SSN (do not share): 123-45-6789
""")
    
    (Path(temp_dir) / "secrets.txt").write_text("""
Database Password: secretpass123
Credit Card: 4111-1111-1111-1111
IP Address: 192.168.1.100
""")
    
    # Create a .git directory to test exclusion
    git_dir = Path(temp_dir) / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("git config with sensitive@email.com")
    
    yield temp_dir
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestLocalAnonymizer:
    """Test the LocalAnonymizer class."""
    
    def test_entity_tag_generation(self, mock_llm_backend):
        """Test that entity tags are generated correctly."""
        anonymizer = LocalAnonymizer()
        
        text = "Contact john.smith@example.com or call 555-123-4567"
        anon_text, mappings = anonymizer.anonymize_data(text)
        
        # Check that entity tags are used
        assert "REDACTED_EMAIL1" in anon_text
        assert "REDACTED_PHONE1" in anon_text
        assert "john.smith@example.com" not in anon_text
        assert "555-123-4567" not in anon_text
        
    def test_consistent_entity_tagging(self, mock_llm_backend):
        """Test that same entity gets same tag."""
        anonymizer = LocalAnonymizer()
        
        text = """
        John's email is john@example.com.
        Please contact john@example.com for details.
        """
        anon_text, mappings = anonymizer.anonymize_data(text)
        
        # Same email should get same tag
        assert anon_text.count("REDACTED_EMAIL1") == 2
        
    def test_multiple_entity_types(self, mock_llm_backend):
        """Test detection of multiple PII types."""
        anonymizer = LocalAnonymizer()
        
        text = """
        Name: John Smith
        Email: john@example.com
        Phone: 555-123-4567
        SSN: 123-45-6789
        Credit Card: 4111-1111-1111-1111
        IP: 192.168.1.1
        """
        anon_text, mappings = anonymizer.anonymize_data(text)
        
        # Check different entity types
        assert "REDACTED_EMAIL" in anon_text
        assert "REDACTED_PHONE" in anon_text
        assert "REDACTED_SSN" in anon_text
        assert "REDACTED_CREDITCARD" in anon_text
        assert "REDACTED_IP" in anon_text
        
    def test_ssn_not_confused_with_phone(self, mock_llm_backend):
        """Test that SSN is correctly identified and not confused with phone."""
        anonymizer = LocalAnonymizer()
        
        text = "Phone: 555-123-4567, SSN: 123-45-6789"
        anon_text, mappings = anonymizer.anonymize_data(text)
        
        assert "REDACTED_PHONE1" in anon_text
        assert "REDACTED_SSN1" in anon_text
        assert "123-45-6789" not in anon_text
        assert "555-123-4567" not in anon_text
        
    def test_memory_and_reset(self, mock_llm_backend):
        """Test that anonymizer remembers entities and can be reset."""
        anonymizer = LocalAnonymizer()
        
        # First call
        text1 = "Email: test@example.com"
        anon_text1, _ = anonymizer.anonymize_data(text1)
        assert "REDACTED_EMAIL1" in anon_text1
        
        # Second call with different email should get next number
        text2 = "Email: other@example.com"
        anon_text2, _ = anonymizer.anonymize_data(text2)
        assert "REDACTED_EMAIL2" in anon_text2
        
        # Same email as first should get same tag
        text3 = "Email: test@example.com"
        anon_text3, _ = anonymizer.anonymize_data(text3)
        assert "REDACTED_EMAIL1" in anon_text3
        
        # After reset, counters should start over
        anonymizer.reset()
        text4 = "Email: new@example.com"
        anon_text4, _ = anonymizer.anonymize_data(text4)
        assert "REDACTED_EMAIL1" in anon_text4


class TestLocalDeanonymizer:
    """Test the LocalDeanonymizer class."""
    
    def test_basic_deanonymization(self, mock_llm_backend):
        """Test basic deanonymization."""
        # Configure mock to detect PII
        mock_llm_backend.detect_pii.return_value = {
            "persons": [],
            "emails": ["john@example.com"],
            "phones": ["555-123-4567"],
            "addresses": [],
            "organizations": [],
            "credit_cards": [],
            "ssn": []
        }

        anonymizer = LocalAnonymizer()
        anonymizer.llm_backend = mock_llm_backend
        deanonymizer = LocalDeanonymizer()

        original = "Contact john@example.com or call 555-123-4567"
        anon_text, mappings = anonymizer.anonymize_data(original)
        restored = deanonymizer.deanonymize(anon_text, mappings)

        assert restored == original
        
    def test_complex_deanonymization(self, mock_llm_backend):
        """Test deanonymization with multiple occurrences."""
        # Configure mock to detect PII
        mock_llm_backend.detect_pii.return_value = {
            "persons": [],
            "emails": ["john@example.com", "jane@example.com"],
            "phones": [],
            "addresses": [],
            "organizations": [],
            "credit_cards": [],
            "ssn": []
        }

        anonymizer = LocalAnonymizer()
        anonymizer.llm_backend = mock_llm_backend
        deanonymizer = LocalDeanonymizer()

        original = """
        John's email is john@example.com.
        Contact john@example.com for details.
        Alternative: jane@example.com
        """

        anon_text, mappings = anonymizer.anonymize_data(original)
        restored = deanonymizer.deanonymize(anon_text, mappings)

        assert restored == original


class TestDirectoryAnonymization:
    """Test directory-level anonymization."""
    
    def test_directory_anonymization(self, temp_test_dir, mock_llm_backend):
        """Test anonymizing an entire directory."""
        output_dir = tempfile.mkdtemp()
        
        try:
            # Use local backend which will use our mock
            config = get_test_config()
            anonymizer = DirectoryAnonymizer(config=config, anonymize_filenames=False)
            
            # Process directory
            results = anonymizer.process_directory(
                input_dir=temp_test_dir,
                output_dir=output_dir
            )
            
            # Check that files were processed
            assert results['statistics']['processed_files'] > 0
            assert results['statistics']['total_files'] > 0
            
            # Check output files exist
            assert Path(output_dir).exists()
            output_files = list(Path(output_dir).rglob('*'))
            assert len(output_files) > 0
            
            # Check that .git was excluded
            assert not (Path(output_dir) / '.git').exists()
            
            # Check specific file content was anonymized
            main_py = Path(output_dir) / 'src' / 'main.py'
            assert main_py.exists()
            content = main_py.read_text()
            assert "REDACTED_EMAIL" in content
            assert "john.smith@example.com" not in content
            
        finally:
            shutil.rmtree(output_dir, ignore_errors=True)
    
    @pytest.mark.skip(reason="Filename anonymization uses actual LLM backend, tested in integration tests")
    def test_filename_anonymization(self, temp_test_dir, mock_llm_backend):
        """Test anonymizing filenames."""
        # This test is skipped because DirectoryAnonymizer creates its own LLMBackend
        # instance and doesn't use the mocked one. Filename anonymization is properly
        # tested in the integration tests (test_dir_anonymizer.py)
        pass
    
    def test_restoration(self, temp_test_dir, mock_llm_backend):
        """Test restoration of anonymized directory."""
        anon_dir = tempfile.mkdtemp()
        restored_dir = tempfile.mkdtemp()
        
        try:
            # Anonymize
            config = get_test_config()
            anonymizer = DirectoryAnonymizer(config=config, anonymize_filenames=False)
            results = anonymizer.process_directory(
                input_dir=temp_test_dir,
                output_dir=anon_dir
            )
            
            # Check mapping file was created in output directory
            mapping_file = Path(anon_dir) / 'anonymization_mapping.json'
            assert mapping_file.exists()
            
            # Restore
            deanonymizer = DirectoryDeanonymizer(str(mapping_file))
            restore_stats = deanonymizer.restore_directory(
                anonymized_dir=anon_dir,
                output_dir=restored_dir,
                restore_filenames=True
            )
            
            assert restore_stats['restored_files'] > 0
            
            # Check restored content matches original
            original_main = Path(temp_test_dir) / 'src' / 'main.py'
            restored_main = Path(restored_dir) / 'src' / 'main.py'
            
            assert restored_main.exists()
            assert restored_main.read_text() == original_main.read_text()
            
        finally:
            shutil.rmtree(anon_dir, ignore_errors=True)
            shutil.rmtree(restored_dir, ignore_errors=True)
    
    
    def test_file_type_filtering(self, temp_test_dir, mock_llm_backend):
        """Test that only configured file types are processed."""
        output_dir = tempfile.mkdtemp()
        
        try:
            # Create a custom config that only processes .md files
            custom_config = {
                'anonymizer': {
                    'backend': 'local',
                    'file_types': ['.md'],
                    'exclude_patterns': ['.git'],
                    'output': {
                        'output_dir': output_dir,
                        'mapping_file': 'anonymization_mapping.json'
                    },
                    'options': {
                        'anonymize_filenames': False,
                        'preserve_structure': True,
                        'create_report': False
                    }
                }
            }
            
            anonymizer = DirectoryAnonymizer(config=custom_config)
            results = anonymizer.process_directory(
                input_dir=temp_test_dir,
                output_dir=output_dir
            )
            
            # Only .md files should be processed
            assert results['statistics']['processed_files'] == 1
            assert (Path(output_dir) / 'docs' / 'README.md').exists()
            assert not (Path(output_dir) / 'src' / 'main.py').exists()
            
        finally:
            shutil.rmtree(output_dir, ignore_errors=True)


class TestEntityTagFormats:
    """Test specific entity tag format requirements."""
    
    def test_entity_tag_format(self, mock_llm_backend):
        """Test that entity tags follow the correct format."""
        anonymizer = LocalAnonymizer()
        
        text = """
        Email: test@example.com
        Phone: 555-123-4567
        SSN: 123-45-6789
        Credit Card: 4111-1111-1111-1111
        IP: 192.168.1.1
        """
        
        anon_text, mappings = anonymizer.anonymize_data(text)
        
        # Check format REDACTED_{TYPE}{NUMBER}
        import re
        pattern = r'REDACTED_[A-Z]+\d+'
        tags = re.findall(pattern, anon_text)
        
        assert len(tags) >= 5  # At least 5 different PII items
        
        # Verify specific formats
        assert any('REDACTED_EMAIL' in tag for tag in tags)
        assert any('REDACTED_PHONE' in tag for tag in tags)
        assert any('REDACTED_SSN' in tag for tag in tags)
        assert any('REDACTED_CREDITCARD' in tag for tag in tags)
        assert any('REDACTED_IP' in tag for tag in tags)
    
    def test_incremental_numbering(self, mock_llm_backend):
        """Test that entity numbers increment correctly."""
        anonymizer = LocalAnonymizer()
        
        text = """
        Emails: alice@example.com, bob@example.com, charlie@example.com
        Phones: 555-111-1111, 555-222-2222
        """
        
        anon_text, _ = anonymizer.anonymize_data(text)
        
        # Should have EMAIL1, EMAIL2, EMAIL3
        assert "REDACTED_EMAIL1" in anon_text
        assert "REDACTED_EMAIL2" in anon_text
        assert "REDACTED_EMAIL3" in anon_text
        
        # Should have PHONE1, PHONE2
        assert "REDACTED_PHONE1" in anon_text
        assert "REDACTED_PHONE2" in anon_text