"""Presidio-based anonymizer implementation."""

import re
import logging
from typing import Dict, Tuple, Any, Optional, List
from collections import defaultdict
from .presidio_backend import PresidioBackend
from mira.libs.text_chunker import chunk_text

LOG = logging.getLogger(__name__)


class LocalAnonymizer:
    """Anonymize text using Presidio for PII detection."""

    @classmethod
    def create_from_config(cls, config: Dict[str, Any]) -> "LocalAnonymizer":
        """Create a LocalAnonymizer instance from configuration.

        Args:
            config: Configuration dictionary, typically from 'anonymizer' section

        Returns:
            Configured LocalAnonymizer instance
        """
        local_config = config.get('local_model', {})
        presidio_config = local_config.get('presidio', {})

        return cls(
            max_input_tokens=local_config.get('max_input_tokens', 1000),
            presidio_config=presidio_config
        )

    def __init__(self, max_input_tokens: int = 1000, presidio_config: Optional[Dict[str, Any]] = None):
        """Initialize the local anonymizer.

        Args:
            max_input_tokens: Maximum tokens per chunk sent to backend
            presidio_config: Configuration dictionary for Presidio backend (language, confidence_threshold, nlp_configuration)
        """
        self.max_input_tokens = max_input_tokens

        # Track entity counters for generating tags
        self.entity_counters = defaultdict(int)

        # Track entity to tag mappings for consistency
        self.entity_memory = {}  # Maps original PII text to assigned tag

        # Initialize Presidio backend
        if presidio_config is None:
            presidio_config = {}

        self.backend = PresidioBackend(
            language=presidio_config.get('language', 'en'),
            confidence_threshold=presidio_config.get('confidence_threshold', 0.0),
            nlp_configuration=presidio_config.get('nlp_configuration')
        )
        LOG.info(f"LocalAnonymizer initialized with Presidio backend (lang={presidio_config.get('language', 'en')}, confidence={presidio_config.get('confidence_threshold', 0.0)})")
    
    def anonymize_data(self, text: str) -> Tuple[str, Dict[str, str]]:
        """Anonymize PII in text.

        Args:
            text: Text to anonymize

        Returns:
            Tuple of (anonymized_text, mappings)
            where mappings is a flat dict of token -> original
        """
        if not text:
            return text, {}

        # Note: We don't reset counters or memory here anymore
        # Use reset() method to clear state for independent runs

        # Always use chunking for consistency (even for small texts)
        pii_data = self._detect_pii_chunked(text)

        # Also detect common patterns with regex for reliability
        regex_pii = self._detect_regex_patterns(text)

        # Merge LLM and regex detections
        pii_data = self._merge_pii_data(pii_data, regex_pii)

        # Generate replacements and create mappings
        mappings = {}  # Flat dict: token -> original
        anonymized_text = text

        # Process each PII category
        for category, entities in pii_data.items():
            if not entities:
                continue

            for entity in entities:
                if entity not in anonymized_text:
                    continue

                # Check if we've already seen this entity (use memory)
                if entity not in self.entity_memory:
                    # Generate new replacement and remember it
                    replacement = self._generate_replacement(category, entity)
                    self.entity_memory[entity] = replacement
                else:
                    # Use existing replacement from memory
                    replacement = self.entity_memory[entity]

                # Replace all occurrences
                anonymized_text = anonymized_text.replace(entity, replacement)

                # Store mapping as replacement -> original (flat structure)
                mappings[replacement] = entity

        return anonymized_text, mappings
    
    def reset(self) -> None:
        """Reset the anonymizer state for a new independent run.
        
        This clears the entity counters and memory, allowing the anonymizer
        to be reused for a new document or session where entities should
        get fresh tags starting from 1.
        """
        self.entity_counters = defaultdict(int)
        self.entity_memory = {}
        LOG.debug("LocalAnonymizer state reset")
    
    def _detect_regex_patterns(self, text: str) -> Dict[str, List[str]]:
        """Detect common PII patterns using regex.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dictionary of detected PII by category
        """
        # Order matters - check SSN before phone to avoid misclassification
        patterns = {
            "ssn": r'\b\d{3}-\d{2}-\d{4}\b',  # SSN format
            "credit_cards": r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
            "emails": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "phones": r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',  # More specific phone pattern
            "ipv4": r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'
        }
        
        detected = {}
        
        # First detect SSNs to exclude them from phone detection
        ssn_matches = re.findall(patterns["ssn"], text)
        if ssn_matches:
            detected["ssn"] = list(set(ssn_matches))
        
        # Detect other patterns
        for category, pattern in patterns.items():
            if category == "ssn":
                continue  # Already handled
                
            matches = re.findall(pattern, text)
            
            # For phones, exclude any SSN matches
            if category == "phones" and "ssn" in detected:
                matches = [m for m in matches if m not in detected["ssn"]]
            
            if matches:
                detected[category] = list(set(matches))  # Remove duplicates
        
        return detected
    
    def _merge_pii_data(self, llm_pii: Dict[str, List[str]], regex_pii: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """Merge PII detected by LLM and regex.
        
        Args:
            llm_pii: PII detected by LLM
            regex_pii: PII detected by regex
            
        Returns:
            Merged PII data
        """
        merged = llm_pii.copy()
        
        for category, entities in regex_pii.items():
            if category in merged:
                # Merge and deduplicate
                merged[category] = list(set(merged[category] + entities))
            else:
                merged[category] = entities
        
        return merged
    
    def _generate_replacement(self, category: str, original: str) -> str:
        """Generate a numbered entity tag replacement for a PII entity.
        
        Args:
            category: PII category
            original: Original PII value
            
        Returns:
            Entity tag like REDACTED_PERSON1, REDACTED_EMAIL2, etc.
        """
        # Map category names to tag prefixes
        tag_names = {
            "persons": "PERSON",
            "emails": "EMAIL",
            "phones": "PHONE",
            "addresses": "ADDRESS",
            "organizations": "ORG",
            "credit_cards": "CREDITCARD",
            "ssn": "SSN",
            "ipv4": "IP"
        }
        
        # Get the tag name or use the category in uppercase
        tag_name = tag_names.get(category, category.upper().rstrip('S'))
        
        # Increment counter for this category
        self.entity_counters[tag_name] += 1
        counter = self.entity_counters[tag_name]
        
        # Return the numbered entity tag
        return f"REDACTED_{tag_name}{counter}"

    def _detect_pii_chunked(self, text: str) -> Dict[str, List[str]]:
        """Detect PII in text by processing it in chunks.

        Args:
            text: Text to analyze (will be chunked)

        Returns:
            Dictionary of detected PII by category
        """
        # Use the text_chunker utility
        lookback_words = 5  # Number of words to overlap between chunks
        chunk_generator = chunk_text(
            text,
            lambda t: self.backend.num_tokens(t),
            self.max_input_tokens,
            lookback_words
        )
        chunks = list(chunk_generator)  # Convert to list for counting
        LOG.debug(f"Split text into {len(chunks)} chunks")

        # Process each chunk
        chunk_results = []
        for i, chunk in enumerate(chunks):
            LOG.debug(f"Processing chunk {i+1}/{len(chunks)}")
            result = self.backend.detect_pii(chunk)
            chunk_results.append(result)

        # Merge results from all chunks
        return self._merge_pii_results(chunk_results)

    def _merge_pii_results(self, results: List[Dict[str, List[str]]]) -> Dict[str, List[str]]:
        """Merge PII detection results from multiple chunks.

        Args:
            results: List of PII detection results from chunks

        Returns:
            Merged PII detection results with duplicates removed
        """
        merged = {}

        # Collect all results by category
        for result in results:
            for category, items in result.items():
                if category not in merged:
                    merged[category] = []
                merged[category].extend(items)

        # Remove duplicates while preserving order
        for category in merged:
            seen = set()
            unique_items = []
            for item in merged[category]:
                if item not in seen:
                    seen.add(item)
                    unique_items.append(item)
            merged[category] = unique_items

        return merged

