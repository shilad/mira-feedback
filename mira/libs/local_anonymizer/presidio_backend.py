"""Presidio backend for PII detection."""

import logging
from typing import Dict, List, Optional

from markdown_it.common.entities import entities
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.predefined_recognizers import SpacyRecognizer, EmailRecognizer, PhoneRecognizer, \
    CreditCardRecognizer, UsSsnRecognizer

LOG = logging.getLogger(__name__)


# Set log level to presidio to WARNING to reduce noise
logging.getLogger("presidio-analyzer").setLevel(logging.WARNING)


class PresidioBackend:
    """Backend that uses Microsoft Presidio for PII detection."""


    # Map Presidio entity types to our standard categories
    ENTITY_TYPE_MAPPING = {
        "PERSON": "persons",
        "EMAIL_ADDRESS": "emails",
        "PHONE_NUMBER": "phones",
        "LOCATION": "addresses",
        "US_SSN": "ssn",
        "CREDIT_CARD": "credit_cards",
        "IP_ADDRESS": "ipv4",
        "URL": "urls",
        "DATE_TIME": "dates",
        "MEDICAL_LICENSE": "medical",
        "US_DRIVER_LICENSE": "ids",
        "US_PASSPORT": "ids",
        "IBAN_CODE": "banking",
        "US_BANK_NUMBER": "banking",
        "CRYPTO": "crypto_addresses",
        "NRP": "nationalities"  # Nationality/religion/political
    }

    def __init__(self, language: str = "en", confidence_threshold: float = 0.0,
                 nlp_configuration: Optional[Dict] = None,
                 entities=None):
        """Initialize the Presidio backend.

        Args:
            language: Language for analysis (default: "en")
            confidence_threshold: Minimum confidence score for detection (0.0-1.0)
            nlp_configuration: Complete NLP configuration dict for NlpEngineProvider
        """
        self.language = language
        self.confidence_threshold = confidence_threshold
        self.nlp_configuration = nlp_configuration or {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}]
        }
        self.analyzer: AnalyzerEngine = None
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy initialization of the AnalyzerEngine."""
        if not self._initialized:
            model_info = self.nlp_configuration.get('models', [{}])[0]
            model_name = model_info.get('model_name', 'default')
            LOG.info(f"Initializing Presidio AnalyzerEngine with {model_name}")

            # Use the configured spaCy model
            from presidio_analyzer.nlp_engine import NlpEngineProvider

            # Use the nlp_configuration directly
            provider = NlpEngineProvider(nlp_configuration=self.nlp_configuration)

            nlp_engine = provider.create_engine()

            registry = RecognizerRegistry([
                SpacyRecognizer(supported_entities=["PERSON"], supported_language="en"),
                EmailRecognizer(),
                PhoneRecognizer(),
                CreditCardRecognizer(),
                UsSsnRecognizer(),
            ])
            self.analyzer = AnalyzerEngine(registry=registry, nlp_engine=nlp_engine)
            LOG.info(f"Initialized with {model_name} model for language {self.language}")

            self._initialized = True

    def detect_pii(self, text: str, system_prompt: Optional[str] = None) -> Dict[str, List[str]]:
        """Detect PII in text using Presidio.

        Args:
            text: Text to analyze
            system_prompt: Ignored for Presidio backend (uses pre-trained models)

        Returns:
            Dictionary mapping PII categories to list of detected entities
        """
        if not text:
            return {}

        self._ensure_initialized()

        try:
            # Analyze text for PII
            analyzer_results = self.analyzer.analyze(
                text=text,
                language=self.language,
                score_threshold=self.confidence_threshold
            )

            # Group detected entities by category
            pii_data = {}
            for result in analyzer_results:
                # Get the actual text for this entity
                entity_text = text[result.start:result.end]

                # Map Presidio entity type to our categories
                category = self.ENTITY_TYPE_MAPPING.get(result.entity_type)

                if category:
                    if category not in pii_data:
                        pii_data[category] = []

                    # Avoid duplicates
                    if entity_text not in pii_data[category]:
                        pii_data[category].append(entity_text)
                else:
                    # Log unmapped entity types for debugging
                    LOG.debug(f"Unmapped Presidio entity type: {result.entity_type}")

                    # Use the entity type as-is with lowercase
                    category = result.entity_type.lower() + "s"
                    if category not in pii_data:
                        pii_data[category] = []
                    if entity_text not in pii_data[category]:
                        pii_data[category].append(entity_text)

            LOG.debug(f"Presidio detected PII: {pii_data}")
            return pii_data

        except Exception as e:
            LOG.error(f"Error detecting PII with Presidio: {e}")
            return {}

    def num_tokens(self, text: str) -> int:
        """Estimate the number of tokens in text.

        For Presidio, we use a simple word count approximation.
        Average English word is ~1.5 tokens.
        """
        word_count = len(text.split())
        return int(word_count * 1.5)