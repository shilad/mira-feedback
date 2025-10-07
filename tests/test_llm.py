"""Unit tests for LLM utilities."""

import os
import pytest
from unittest.mock import patch, Mock, MagicMock

from mira.libs.llm import create_agent


class TestCreateAgent:
    """Test the create_agent function."""

    def test_create_agent_with_defaults(self):
        """Test creating agent with default configuration."""

        config_map = {
            "openai": {
                "api_key": "test-key",
                "organization": "test-org",
                "model": "gpt-4",
                "pydantic_ai_settings": {}
            }
        }

        # Create agent
        agent = create_agent(config_map)

        # Check that environment variables were set
        assert os.environ.get('OPENAI_API_KEY') == 'test-key'
        assert os.environ.get('OPENAI_ORG_ID') == 'test-org'

        # Check that agent was created
        assert agent is not None

    def test_create_agent_with_custom_config(self):
        """Test creating agent with custom configuration."""
        custom_configs = {
            "openai": {
                "api_key": "custom-key",
                "organization": "custom-org",
                "model": "gpt-3.5-turbo"
            }
        }

        # Create agent with custom config
        agent = create_agent(configs=custom_configs, model="gpt-3.5-turbo")

        # Check that environment variables were set
        assert os.environ.get('OPENAI_API_KEY') == 'custom-key'
        assert os.environ.get('OPENAI_ORG_ID') == 'custom-org'

        # Check that agent was created
        assert agent is not None

    def test_create_agent_with_o1_model(self):
        """Test creating agent with o1 model (reasoning model)."""

        test_configs = {
            "openai": {
                "api_key": "test-key",
                "organization": "test-org"
            }
        }

        # Create agent with o1 model
        agent = create_agent(
            configs=test_configs,
            model="o1-mini",
            settings_dict={
                "openai_reasoning_effort": "high"
            }
        )

        # Check that agent was created
        assert agent is not None

    def test_create_agent_with_system_prompt(self):
        """Test creating agent with custom system prompt."""

        test_configs = {
            "openai": {
                "api_key": "test-key",
                "organization": "test-org"
            }
        }

        # Create agent with custom prompt
        custom_prompt = "You are a helpful coding assistant."
        agent = create_agent(
            configs=test_configs,
            model="gpt-4",
            system_prompt=custom_prompt
        )

        # Check that agent was created
        assert agent is not None

    def test_create_agent_missing_api_key(self):
        """Test that missing API key raises ValueError."""
        # Should raise KeyError for missing API key
        with pytest.raises(KeyError, match="Key.*not found.*"):
            create_agent({})

    def test_create_agent_with_settings_dict(self):
        """Test creating agent with custom settings dictionary."""

        test_configs = {
            "openai": {
                "api_key": "test-key",
                "organization": "test-org"
            }
        }

        # Custom settings
        custom_settings = {
            "temperature": 0.7,
            "max_tokens": 1000
        }

        # Create agent with custom settings
        agent = create_agent(
            configs=test_configs,
            model="gpt-4",
            settings_dict=custom_settings
        )

        # Check that agent was created
        assert agent is not None