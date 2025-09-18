"""OpenPipe PII redaction backend wrapper."""

import re
import logging
from typing import Dict, List, Optional, Tuple
from pii_redaction.redactor import PIIRedactor, PIIHandlingMode, parse_tagged_string

LOG = logging.getLogger(__name__)


class OpenPipeBackend:
    """Backend that uses OpenPipe's PII redaction models for anonymization."""

    def __init__(self, device: Optional[str] = None):
        """Initialize the OpenPipe backend.

        Args:
            device: Device to use for inference ('cpu', 'cuda', or None for auto)
        """
        self.device = device
        self.redactor = None
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy initialization of the PIIRedactor."""
        if not self._initialized:
            LOG.info(f"Initializing OpenPipe PIIRedactor with device: {self.device}")
            self.redactor = PIIRedactor(device=self.device)
            self._initialized = True

    def detect_pii(self, text: str, system_prompt: Optional[str] = None) -> Dict[str, List[str]]:
        """Detect PII in text using OpenPipe models.

        Args:
            text: Text to analyze
            system_prompt: Ignored for OpenPipe backend (uses pre-trained models)

        Returns:
            Dictionary mapping PII categories to list of detected entities
        """
        if not text:
            return {}

        self._ensure_initialized()

        # Process text with OpenPipe models in TAG mode to get PII annotations
        tagged_result = self.redactor.tag_pii_in_documents([text], mode=PIIHandlingMode.TAG)[0]

        # Parse the tagged result to extract PII entities
        _, annotations = parse_tagged_string(tagged_result)

        # Group entities by category
        pii_data = {}
        for start, end, tag, annotated_text in annotations:
            # Map OpenPipe tags to our standard categories
            category = self._map_tag_to_category(tag)
            if category not in pii_data:
                pii_data[category] = []
            if annotated_text not in pii_data[category]:
                pii_data[category].append(annotated_text)

        LOG.debug(f"OpenPipe detected PII: {pii_data}")
        return pii_data

    def num_tokens(self, text: str) -> int:
        """Count the number of tokens in the given text."""
        self._ensure_initialized()
        # Initialize the first model if needed for tokenization
        self.redactor._initialize_model(0)
        return len(self.redactor.tokenizers[0].encode(text, add_special_tokens=False))

    def _map_tag_to_category(self, tag: str) -> str:
        """Map OpenPipe PII tags to our standard categories.

        Args:
            tag: OpenPipe PII type tag

        Returns:
            Standard category name
        """
        # Map OpenPipe tags to our categories
        tag_mapping = {
            "person_name": "persons",
            "organization_name": "organizations",
            "email_address": "emails",
            "phone_number": "phones",
            "street_address": "addresses",
            "credit_card_info": "credit_cards",
            "banking_number": "credit_cards",
            "personal_id": "ssn",
            "date_of_birth": "dates",
            "date": "dates",
            "domain_name": "domains",
            "password": "passwords",
            "secure_credential": "passwords",
            "medical_condition": "medical",
            "age": "ages",
            "gender": "genders",
            "nationality": "nationalities",
            "demographic_group": "demographics",
            "religious_affiliation": "religions",
            "other_id": "ids"
        }

        return tag_mapping.get(tag, tag + "s")