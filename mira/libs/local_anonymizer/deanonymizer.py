"""Local deanonymizer implementation."""

import logging
from typing import Dict, Any

LOG = logging.getLogger(__name__)


class LocalDeanonymizer:
    """Restore anonymized text using mappings."""
    
    def __init__(self):
        """Initialize the deanonymizer."""
        pass
    
    def deanonymize(self, text: str, mappings: Dict[str, str]) -> str:
        """Restore original content from anonymized text.

        Args:
            text: Anonymized text
            mappings: Flat dictionary mapping redacted tokens to original values
                     Format: {redacted_token: original_value}
                     Example: {"REDACTED_EMAIL1": "john@example.com"}

        Returns:
            Original text with PII restored
        """
        if not text or not mappings:
            return text

        restored_text = text

        # Simple flat format: directly replace each redacted token with its original value
        for redacted_token, original_value in mappings.items():
            restored_text = restored_text.replace(redacted_token, original_value)

        return restored_text