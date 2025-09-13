"""LLM backend for PII detection using Hugging Face models."""

import json
import logging
from typing import Dict, List, Any, Optional
import torch
from transformers import pipeline

LOG = logging.getLogger(__name__)


class LLMBackend:
    """Handles LLM model loading and inference for PII detection."""
    
    def __init__(self, model_name: str = "mistralai/Mistral-7B-Instruct-v0.3", device: str = "cpu"):
        """Initialize the LLM backend.
        
        Args:
            model_name: Hugging Face model name
            device: Device to run on ('cpu' or 'cuda')
        """
        self.model_name = model_name
        self.device = device
        
        LOG.info(f"Loading model: {model_name} on {device}")
        
        try:
            device_num = 0 if device in ("cuda", "mps") else -1
            self.pipe = pipeline("text-generation", model=model_name, device=device_num)
            LOG.info(f"Model loaded successfully")
            
        except Exception as e:
            LOG.error(f"Failed to load model {model_name}: {e}")
            raise
    
    def detect_pii(self, text: str, system_prompt: Optional[str] = None) -> Dict[str, List[str]]:
        """Detect PII in text using the LLM.
        
        Args:
            text: Text to analyze for PII
            system_prompt: Optional custom system prompt
            
        Returns:
            Dictionary with PII categories and detected entities
        """
        if system_prompt is None:
            system_prompt = self._get_default_prompt()
        
        # Construct the full prompt
        user_prompt = f"""Text to analyze:
        
        ```txt
        {text}
        ```

        Return ONLY a JSON object with the detected PII. 
        
        JSON output:"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        # print(json.dumps(messages, indent=2))
        response = self.pipe(messages)
        response_text = response[0]['generated_text'][-1]['content']
        # print(response_text + '\n' + '='*80 + '\n')

        # Extract JSON from response
        return self._extract_json(response_text)

    def _get_default_prompt(self) -> str:
        """Get the default system prompt for PII detection."""
        return """You are a PII (Personally Identifiable Information) detection system. Your task is to identify all PII in the given text.

Categories to detect if explicitly disclosed:
- persons: Full names of individuals
- emails: Email addresses
- phones: Phone numbers in any format
- addresses: Physical addresses
- organizations: Company or organization names
- credit_cards: Credit card numbers
- ssn: Social Security Numbers

Return only a valid JSON object with the following structure, where the values are lists of detected items (strings):

        {{"persons": [], "emails": [], "phones": [], "addresses": [], "organizations": [], "credit_cards": [], "ssn": []}}

If no PII exists for the category, the list should be empty.

"""
    
    def _extract_json(self, response: str) -> Dict[str, List[str]]:
        """Extract JSON from LLM response.
        
        Args:
            response: Raw LLM response
            
        Returns:
            Parsed JSON as dictionary
        """
        try:
            # Try to find JSON in the response
            response = response.strip()
            
            # Look for JSON object
            start_idx = response.find('{')
            end_idx = response.rfind('}')
            
            if start_idx != -1 and end_idx != -1:
                json_str = response[start_idx:end_idx + 1]
                return json.loads(json_str)
            else:
                # Try parsing the whole response
                return json.loads(response)
                
        except json.JSONDecodeError as e:
            LOG.warning(f"Failed to parse JSON from LLM response: {e}")
            LOG.debug(f"Response was: {response}")
            
            # Return empty structure
            return {
                "persons": [],
                "emails": [],
                "phones": [],
                "addresses": [],
                "organizations": [],
                "credit_cards": [],
                "ssn": []
            }