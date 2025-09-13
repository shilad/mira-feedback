"""Local deanonymizer implementation."""

import logging
from typing import Dict, Any

LOG = logging.getLogger(__name__)


class LocalDeanonymizer:
    """Restore anonymized text using mappings."""
    
    def __init__(self):
        """Initialize the deanonymizer."""
        pass
    
    def deanonymize(self, text: str, mappings: Dict[str, Any]) -> str:
        """Restore original content from anonymized text.
        
        Args:
            text: Anonymized text
            mappings: Dictionary mapping categories to {anonymized: original} pairs
            
        Returns:
            Original text with PII restored
        """
        if not text or not mappings:
            return text
        
        restored_text = text
        
        # Process each category of mappings
        for category, replacements in mappings.items():
            if not isinstance(replacements, dict):
                continue
                
            # Replace each anonymized value with its original
            for original, anonymized in replacements.items():
                # The mappings are stored as {original: anonymized}
                # So we need to reverse the replacement
                restored_text = restored_text.replace(anonymized, original)
        
        return restored_text