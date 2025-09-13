"""Unit tests for LLMBackend chunking functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from shilads_helpers.libs.local_anonymizer.llm_backend import LLMBackend


class TestLLMBackendChunking:
    """Test the chunking functionality of LLMBackend."""
    
    @pytest.fixture
    def mock_tokenizer(self):
        """Create a mock tokenizer that counts words as tokens for simplicity."""
        tokenizer = Mock()
        
        def encode_side_effect(text, add_special_tokens=False):
            # Simple tokenization: split by spaces and punctuation
            import re
            tokens = re.findall(r'\w+|[^\w\s]', text)
            return list(range(len(tokens)))  # Return list with length equal to token count
        
        tokenizer.encode.side_effect = encode_side_effect
        return tokenizer
    
    @pytest.fixture
    def mock_pipeline(self, mock_tokenizer):
        """Create a mock pipeline with tokenizer."""
        with patch('shilads_helpers.libs.local_anonymizer.llm_backend.pipeline') as mock_pipe:
            pipe_instance = Mock()
            pipe_instance.tokenizer = mock_tokenizer
            
            # Mock the LLM response
            def pipe_response(messages):
                return [{
                    'generated_text': [
                        {'role': 'assistant', 'content': '{"persons": [], "emails": [], "phones": [], "addresses": [], "organizations": [], "credit_cards": [], "ssn": []}'}
                    ]
                }]
            
            pipe_instance.side_effect = pipe_response
            mock_pipe.return_value = pipe_instance
            
            yield mock_pipe
    
    def test_no_chunking_for_short_text(self, mock_pipeline):
        """Test that short text is not chunked."""
        backend = LLMBackend(max_input_tokens=100)
        
        short_text = "This is a short text."
        
        # Call detect_pii which handles chunking internally
        result = backend.detect_pii(short_text)
        
        # Should process without chunking (verify by checking it works)
        assert isinstance(result, dict)
        assert "persons" in result
    
    def test_chunking_with_multiple_lines(self, mock_pipeline):
        """Test chunking with multiple lines."""
        backend = LLMBackend(max_input_tokens=10)
        
        # Mock to track chunks processed
        chunks_processed = []
        
        def track_chunks(messages):
            text = messages[1]['content']
            start = text.find('```txt\n') + 7
            end = text.find('\n```', start)
            chunks_processed.append(text[start:end])
            return [{
                'generated_text': [
                    {'role': 'assistant', 'content': '{"persons": [], "emails": [], "phones": [], "addresses": [], "organizations": [], "credit_cards": [], "ssn": []}'}
                ]
            }]
        
        backend.pipe = track_chunks
        
        text = "Line one here.\nLine two here.\nLine three here."
        backend.detect_pii(text)
        
        # Should create multiple chunks due to token limit
        assert len(chunks_processed) > 1
    
    def test_chunking_long_line(self, mock_pipeline):
        """Test chunking when a single line exceeds max tokens."""
        backend = LLMBackend(max_input_tokens=5)
        
        chunks_processed = []
        
        def track_chunks(messages):
            text = messages[1]['content']
            start = text.find('```txt\n') + 7
            end = text.find('\n```', start)
            chunks_processed.append(text[start:end])
            return [{
                'generated_text': [
                    {'role': 'assistant', 'content': '{"persons": [], "emails": [], "phones": [], "addresses": [], "organizations": [], "credit_cards": [], "ssn": []}'}
                ]
            }]
        
        backend.pipe = track_chunks
        
        # This line has more than 5 tokens
        long_line = "This is a very long line that definitely exceeds the token limit"
        backend.detect_pii(long_line)
        
        # Should be split into multiple chunks
        assert len(chunks_processed) > 1
        
        # All words should appear somewhere
        all_text = ' '.join(chunks_processed)
        for word in long_line.split():
            assert word in all_text
    
    def test_chunking_with_empty_lines(self, mock_pipeline):
        """Test chunking handles empty lines correctly."""
        backend = LLMBackend(max_input_tokens=10)
        
        chunks_processed = []
        
        def track_chunks(messages):
            text = messages[1]['content']
            start = text.find('```txt\n') + 7
            end = text.find('\n```', start)
            chunks_processed.append(text[start:end])
            return [{
                'generated_text': [
                    {'role': 'assistant', 'content': '{"persons": [], "emails": [], "phones": [], "addresses": [], "organizations": [], "credit_cards": [], "ssn": []}'}
                ]
            }]
        
        backend.pipe = track_chunks
        
        text = "First line.\n\nSecond line after empty.\n\nThird line."
        backend.detect_pii(text)
        
        # Should handle empty lines without error
        assert len(chunks_processed) >= 1
        
        # Verify text integrity
        combined = ' '.join(chunks_processed)
        assert "First line" in combined
        assert "Second line" in combined
        assert "Third line" in combined
    
    def test_merge_pii_results(self, mock_pipeline):
        """Test merging PII results from multiple chunks."""
        backend = LLMBackend()
        
        # Create sample results from different chunks
        result1 = {
            "persons": ["John Doe", "Jane Smith"],
            "emails": ["john@example.com"],
            "phones": [],
            "addresses": ["123 Main St"],
            "organizations": ["Acme Corp"],
            "credit_cards": [],
            "ssn": []
        }
        
        result2 = {
            "persons": ["Jane Smith", "Bob Wilson"],  # Jane Smith is duplicate
            "emails": ["jane@example.com"],
            "phones": ["555-1234"],
            "addresses": [],
            "organizations": ["Acme Corp", "Tech Inc"],  # Acme Corp is duplicate
            "credit_cards": [],
            "ssn": ["123-45-6789"]
        }
        
        merged = backend._merge_pii_results([result1, result2])
        
        # Check that duplicates are removed
        assert len(merged["persons"]) == 3  # John Doe, Jane Smith, Bob Wilson
        assert "John Doe" in merged["persons"]
        assert "Jane Smith" in merged["persons"]
        assert "Bob Wilson" in merged["persons"]
        
        assert len(merged["organizations"]) == 2  # Acme Corp, Tech Inc
        assert "Acme Corp" in merged["organizations"]
        assert "Tech Inc" in merged["organizations"]
        
        # Check that all unique items are included
        assert len(merged["emails"]) == 2
        assert "john@example.com" in merged["emails"]
        assert "jane@example.com" in merged["emails"]
        
        assert merged["phones"] == ["555-1234"]
        assert merged["addresses"] == ["123 Main St"]
        assert merged["ssn"] == ["123-45-6789"]
    
    def test_merge_pii_results_empty(self, mock_pipeline):
        """Test merging empty results."""
        backend = LLMBackend()
        
        empty_result = {
            "persons": [],
            "emails": [],
            "phones": [],
            "addresses": [],
            "organizations": [],
            "credit_cards": [],
            "ssn": []
        }
        
        merged = backend._merge_pii_results([empty_result, empty_result])
        
        # All categories should be empty
        for category in merged:
            assert merged[category] == []
    
    def test_detect_pii_with_chunking(self, mock_pipeline):
        """Test that detect_pii properly chunks large text."""
        backend = LLMBackend(max_input_tokens=10)
        
        # Create a mock that tracks how many times the LLM is called
        call_count = 0
        chunk_texts = []
        
        def mock_pipe_response(messages):
            nonlocal call_count, chunk_texts
            call_count += 1
            # Extract the text being analyzed from the user message
            user_msg = messages[1]['content']
            start = user_msg.find('```txt\n') + 7
            end = user_msg.find('\n```', start)
            chunk_texts.append(user_msg[start:end])
            
            return [{
                'generated_text': [
                    {'role': 'assistant', 'content': f'{{"persons": ["Person{call_count}"], "emails": [], "phones": [], "addresses": [], "organizations": [], "credit_cards": [], "ssn": []}}'}
                ]
            }]
        
        backend.pipe = mock_pipe_response
        
        # Long text that will be chunked
        long_text = " ".join(["Word" + str(i) for i in range(50)])  # 50 words
        
        result = backend.detect_pii(long_text)
        
        # Should have called the LLM multiple times (once per chunk)
        assert call_count > 1
        
        # Results should be merged
        assert len(result["persons"]) == call_count
        
        # Verify chunks had overlap by checking for repeated words
        # Note: The first few chunks might not have overlap if they're very small
        overlaps_found = 0
        for i in range(1, len(chunk_texts)):
            prev_words = set(chunk_texts[i-1].split()[-backend.lookback_words:])
            curr_words = set(chunk_texts[i].split())  # Check entire chunk for overlap words
            # Check if there's overlap
            if prev_words and curr_words:
                overlap = prev_words.intersection(curr_words)
                if len(overlap) > 0:
                    overlaps_found += 1
        
        # At least some chunks should have overlap
        assert overlaps_found > 0, "No overlap found between any chunks"
    
    def test_detect_pii_no_chunking_needed(self, mock_pipeline):
        """Test that small text is not chunked unnecessarily."""
        backend = LLMBackend(max_input_tokens=100)
        
        call_count = 0
        
        def mock_pipe_response(messages):
            nonlocal call_count
            call_count += 1
            return [{
                'generated_text': [
                    {'role': 'assistant', 'content': '{"persons": ["John"], "emails": [], "phones": [], "addresses": [], "organizations": [], "credit_cards": [], "ssn": []}'}
                ]
            }]
        
        backend.pipe = mock_pipe_response
        
        short_text = "John is here."
        result = backend.detect_pii(short_text)
        
        # Should only call LLM once (no chunking)
        assert call_count == 1
        assert result["persons"] == ["John"]
    
