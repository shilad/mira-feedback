"""LLM utilities for creating and configuring AI agents."""

import os
from typing import Optional, Dict, Any

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings

from shilads_helpers.libs.config_loader import load_all_configs, get_config


def create_agent(configs: Optional[Dict[str, Any]],
                 model: Optional[str] = None,
                 settings_dict: Optional[Dict[str, Any]] = None,
                 system_prompt: Optional[str] = None) -> Agent:
    """
    Create a pydantic-ai Agent configured with OpenAI models.

    Args:
        configs: Configuration dictionary (if not provided, loaded from config files)
        model: Model to use (overrides config value)
        settings_dict: Pydantic AI settings dict (overrides config values)
        system_prompt: System prompt for the agent (optional)

    Returns:
        Configured Agent

    Raises:
        ValueError: If OpenAI API key is not found in config
    """
    # Get credentials from config
    api_key = get_config("openai.api_key", configs)
    organization = get_config("openai.organization", configs)
    model = model or get_config("openai.model", configs)
    base_settings = get_config("openai.pydantic_ai_settings", configs, default={})

    os.environ['OPENAI_API_KEY'] = api_key
    os.environ['OPENAI_ORG_ID'] = organization

    settings_dict = base_settings | (settings_dict or {})
    model_settings = OpenAIResponsesModelSettings(**settings_dict) if settings_dict else None
    openai_model = OpenAIResponsesModel(model)
    if system_prompt:
        agent = Agent(
            model=openai_model,
            model_settings=model_settings,
            system_prompt=system_prompt
        )
    else:
        agent = Agent(
            model=openai_model,
            model_settings=model_settings
        )
    return agent