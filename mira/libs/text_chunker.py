"""Simple text chunking utility for splitting text into token-limited chunks."""

from typing import Generator, Callable, List


def chunk_text(
    text: str,
    count_tokens: Callable[[str], int],
    max_tokens: int,
    lookback_words: int = 5
) -> Generator[str, None, None]:
    """
    Generate text chunks that fit within token limits with overlap.
    
    This is a simple chunker that favors simplicity over perfect token limits.
    It splits by lines, handles long lines by splitting at whitespace, and
    adds lookback words from the previous chunk for context.
    
    Args:
        text: The text to chunk
        count_tokens: Function that counts tokens in a string
        max_tokens: Maximum tokens per chunk
        lookback_words: Number of words to overlap between chunks
        
    Yields:
        Text chunks with overlap
    """
    lines = text.split('\n')
    current_chunk_lines = []
    current_tokens = 0
    previous_words = []
    
    for line in lines:
        line_tokens = count_tokens(line)
        
        # Handle lines that are too long by themselves
        if line_tokens > max_tokens:
            # First flush any accumulated lines
            if current_chunk_lines:
                chunk = _format_chunk(current_chunk_lines, previous_words)
                yield chunk
                previous_words = _get_last_words('\n'.join(current_chunk_lines), lookback_words)
                current_chunk_lines = []
                current_tokens = 0
            
            # Split the long line into approximately equal chunks
            # Simple approach: split by words and divide roughly equally
            words = line.split()
            if not words:
                continue
                
            # Estimate how many chunks we need
            chunks_needed = max(1, (line_tokens + max_tokens - 1) // max_tokens)
            words_per_chunk = max(1, len(words) // chunks_needed)
            
            # Split the line
            for i in range(0, len(words), words_per_chunk):
                fragment_words = words[i:i + words_per_chunk]
                fragment = ' '.join(fragment_words)
                
                # Add lookback and yield
                chunk = _format_chunk([fragment], previous_words)
                yield chunk
                previous_words = fragment_words[-lookback_words:] if len(fragment_words) > lookback_words else fragment_words
        
        # Check if adding this normal line would exceed limit
        elif current_tokens + line_tokens > max_tokens and current_chunk_lines:
            # Yield current chunk and start new one
            chunk = _format_chunk(current_chunk_lines, previous_words)
            yield chunk
            previous_words = _get_last_words('\n'.join(current_chunk_lines), lookback_words)
            current_chunk_lines = [line]
            current_tokens = line_tokens
        else:
            # Add line to current chunk (always take at least one line)
            current_chunk_lines.append(line)
            current_tokens += line_tokens
    
    # Yield any remaining lines
    if current_chunk_lines:
        chunk = _format_chunk(current_chunk_lines, previous_words)
        yield chunk


def _format_chunk(lines: List[str], previous_words: List[str]) -> str:
    """Format a chunk with optional lookback words."""
    chunk_text = '\n'.join(lines)
    if previous_words:
        # Add previous words as context at the beginning
        lookback_text = ' '.join(previous_words)
        # If the chunk already starts with the lookback words, don't duplicate
        if not chunk_text.startswith(lookback_text):
            chunk_text = lookback_text + '\n' + chunk_text
    return chunk_text


def _get_last_words(text: str, num_words: int) -> List[str]:
    """Get the last N words from text."""
    words = text.replace('\n', ' ').split()
    if len(words) <= num_words:
        return words
    return words[-num_words:]