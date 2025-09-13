"""LLM backend for PII detection using Hugging Face models."""

import json
import logging
from typing import Dict, List, Any, Optional
import torch
from transformers import pipeline

from shilads_helpers.libs.text_chunker import chunk_text

LOG = logging.getLogger(__name__)


class LLMBackend:
    """Handles LLM model loading and inference for PII detection."""
    
    def __init__(self, model_name: str = "mistralai/Mistral-7B-Instruct-v0.3", device: str = "cpu", max_input_tokens: int = 100):
        """Initialize the LLM backend.
        
        Args:
            model_name: Hugging Face model name
            device: Device to run on ('cpu' or 'cuda')
            max_input_tokens: Maximum tokens per chunk sent to LLM
        """
        self.model_name = model_name
        self.device = device
        self.max_input_tokens = max_input_tokens
        self.lookback_words = 5  # Number of words to overlap between chunks
        
        LOG.info(f"Loading model: {model_name} on {device}")
        
        try:
            device_num = 0 if device in ("cuda", "mps") else -1
            self.pipe = pipeline("text-generation", model=model_name, device=device_num)
            
            # Get the tokenizer for counting tokens
            self.tokenizer = self.pipe.tokenizer
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
        
        try:
            # Check if text needs chunking
            total_tokens = len(self.tokenizer.encode(text, add_special_tokens=False))
            
            if total_tokens <= self.max_input_tokens:
                # Process as single chunk
                return self._detect_pii_single_chunk(text, system_prompt)
            else:
                # Process in chunks
                LOG.debug(f"Text has {total_tokens} tokens, chunking with max {self.max_input_tokens} tokens per chunk")
                # Use the text_chunker utility
                chunk_generator = chunk_text(
                    text, 
                    lambda t: len(self.tokenizer.encode(t, add_special_tokens=False)),
                    self.max_input_tokens,
                    self.lookback_words
                )
                chunks = list(chunk_generator)  # Convert to list for counting
                LOG.debug(f"Split text into {len(chunks)} chunks")
                
                # Process each chunk
                chunk_results = []
                for i, chunk in enumerate(chunks):
                    LOG.debug(f"Processing chunk {i+1}/{len(chunks)}")
                    result = self._detect_pii_single_chunk(chunk, system_prompt)
                    chunk_results.append(result)
                
                # Merge results
                merged_results = self._merge_pii_results(chunk_results)
                return merged_results
                
        except Exception as e:
            LOG.error(f"Error detecting PII: {e}")
            # Return empty structure on error
            return {
                "persons": [],
                "emails": [],
                "phones": [],
                "addresses": [],
                "organizations": [],
                "credit_cards": [],
                "ssn": []
            }
    
    def _detect_pii_single_chunk(self, text: str, system_prompt: str) -> Dict[str, List[str]]:
        """Detect PII in a single chunk of text.
        
        Args:
            text: Text chunk to analyze
            system_prompt: System prompt for PII detection
            
        Returns:
            Dictionary with PII categories and detected entities
        """
        # Construct the full prompt
        user_prompt = f"""Detect PII for the following content:
        
        <content>        
        {text}
        </content>
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response = self.pipe(messages)
            response_text = response[0]['generated_text'][-1]['content']
            
            # Extract JSON from response
            return self._extract_json(response_text)
        except Exception as e:
            LOG.error(f"Error in LLM inference: {e}")
            return {
                "persons": [],
                "emails": [],
                "phones": [],
                "addresses": [],
                "organizations": [],
                "credit_cards": [],
                "ssn": []
            }

    def _get_default_prompt(self) -> str:
        """Get the default system prompt for PII detection."""
        return """You are a PII (Personally Identifiable Information) detection system. Your task is to identify all PII in the given text.

Categories to detect if explicitly disclosed:
- persons: Full names of individuals
- emails: Email addresses
- phones: Phone numbers in any format
- addresses: Physical addresses
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
    
    def _merge_pii_results(self, results: List[Dict[str, List[str]]]) -> Dict[str, List[str]]:
        """Merge PII detection results from multiple chunks.
        
        Args:
            results: List of PII detection results from chunks
            
        Returns:
            Merged PII detection results with duplicates removed
        """
        merged = {
            "persons": [],
            "emails": [],
            "phones": [],
            "addresses": [],
            "organizations": [],
            "credit_cards": [],
            "ssn": []
        }
        
        for result in results:
            for category, items in result.items():
                if category in merged:
                    # Use set to remove duplicates, then convert back to list
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