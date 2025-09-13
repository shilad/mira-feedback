"""Tests for the text chunking utility."""

import pytest
from shilads_helpers.libs.text_chunker import chunk_text


class TestTextChunker:
    """Test the text chunking functionality."""
    
    def simple_token_counter(self, text: str) -> int:
        """Simple token counter that counts words for predictable testing."""
        return len(text.split())
    
    def test_single_chunk_no_split(self):
        """Test that short text yields a single chunk."""
        text = "This is a short text."
        chunks = list(chunk_text(text, self.simple_token_counter, max_tokens=10))
        
        assert len(chunks) == 1
        assert chunks[0].strip() == text
    
    def test_multiple_lines_chunking(self):
        """Test chunking across multiple lines."""
        text = "Line one here.\nLine two here.\nLine three here."
        chunks = list(chunk_text(text, self.simple_token_counter, max_tokens=5))
        
        # Should create multiple chunks
        assert len(chunks) > 1
        
        # All lines should appear somewhere
        full_text = ' '.join(chunks)
        assert "Line one" in full_text
        assert "Line two" in full_text
        assert "Line three" in full_text
    
    def test_long_line_splitting(self):
        """Test that long lines are split into chunks."""
        # Line with 10 words
        long_line = "one two three four five six seven eight nine ten"
        chunks = list(chunk_text(long_line, self.simple_token_counter, max_tokens=3))
        
        # Should be split into multiple chunks
        assert len(chunks) > 1
        
        # All words should appear
        all_text = ' '.join(chunks)
        for word in long_line.split():
            assert word in all_text
    
    def test_lookback_overlap(self):
        """Test that chunks have overlapping words."""
        text = "word1 word2 word3 word4 word5 word6 word7 word8"
        chunks = list(chunk_text(text, self.simple_token_counter, max_tokens=3, lookback_words=2))
        
        # Should have multiple chunks
        assert len(chunks) > 1
        
        # Check for overlap between consecutive chunks
        for i in range(1, len(chunks)):
            prev_chunk = chunks[i-1]
            curr_chunk = chunks[i]
            
            # Get last words from previous chunk
            prev_words = prev_chunk.split()[-2:]
            
            # At least one should appear in current chunk
            overlap_found = any(word in curr_chunk for word in prev_words)
            assert overlap_found, f"No overlap between chunk {i-1} and {i}"
    
    def test_empty_lines_handling(self):
        """Test that empty lines are handled correctly."""
        text = "Line one\n\nLine two\n\n\nLine three"
        chunks = list(chunk_text(text, self.simple_token_counter, max_tokens=5))
        
        # Should handle empty lines without error
        assert len(chunks) >= 1
        
        # Content should be preserved
        all_text = ' '.join(chunks)
        assert "Line one" in all_text
        assert "Line two" in all_text
        assert "Line three" in all_text
    
    def test_generator_behavior(self):
        """Test that chunk_text is a proper generator."""
        text = "word1 word2 word3 word4 word5 word6"
        chunker = chunk_text(text, self.simple_token_counter, max_tokens=2)
        
        # Should be a generator
        assert hasattr(chunker, '__iter__')
        assert hasattr(chunker, '__next__')
        
        # Should yield chunks on demand
        first_chunk = next(chunker)
        assert isinstance(first_chunk, str)
        assert len(first_chunk) > 0
    
    def test_always_take_one_line(self):
        """Test that at least one line is always taken even if it exceeds limit."""
        # Single line that exceeds limit
        text = "This line has five words"
        chunks = list(chunk_text(text, self.simple_token_counter, max_tokens=3))
        
        # Should still process it (by splitting)
        assert len(chunks) > 0
        
        # All words should appear
        all_text = ' '.join(chunks)
        for word in text.split():
            assert word in all_text
    
    def test_custom_lookback_words(self):
        """Test custom lookback word count."""
        text = "w1 w2 w3 w4 w5 w6 w7 w8 w9 w10"
        
        # Test with different lookback values
        chunks_1 = list(chunk_text(text, self.simple_token_counter, max_tokens=3, lookback_words=1))
        chunks_3 = list(chunk_text(text, self.simple_token_counter, max_tokens=3, lookback_words=3))
        
        # Both should chunk the text
        assert len(chunks_1) > 1
        assert len(chunks_3) > 1
        
        # More lookback should result in more overlap
        # This is a simple check - with more lookback, chunks tend to be longer
        total_length_1 = sum(len(c.split()) for c in chunks_1)
        total_length_3 = sum(len(c.split()) for c in chunks_3)
        assert total_length_3 >= total_length_1
    
    def test_realistic_token_counter(self):
        """Test with a more realistic token counter."""
        # Simulate a tokenizer that counts more tokens than words
        def realistic_counter(text):
            # Punctuation and special chars count as tokens
            import re
            tokens = re.findall(r'\w+|[^\w\s]', text)
            return len(tokens)
        
        text = "Hello, world! This is a test."
        chunks = list(chunk_text(text, realistic_counter, max_tokens=5))
        
        # Should handle the different token counting
        assert len(chunks) >= 1
        
        # Original text should be represented
        all_text = ' '.join(chunks)
        assert "Hello" in all_text
        assert "world" in all_text
        assert "test" in all_text