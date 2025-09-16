"""Integration tests for LLM utilities that hit the actual API."""

import pytest
import asyncio

from shilads_helpers.libs.config_loader import load_all_configs
from shilads_helpers.libs.llm import create_agent


# Mark all tests in this file as integration tests
pytestmark = [pytest.mark.integration_test, pytest.mark.slow_integration_test]


def _get_gpt5_mini_agent():
    config = load_all_configs()
    return create_agent(config,
                        model="gpt-5-mini",
                        settings_dict={ "openai_reasoning_effort": "low"})

class TestCreateAgentIntegration:
    """Integration tests for create_agent that use the actual OpenAI API."""

    @pytest.mark.asyncio
    async def test_create_and_run_simple_agent(self):
        """Test creating an agent and running a simple query."""
        # Create agent with default config
        agent = _get_gpt5_mini_agent()

        # Run a simple query
        result = await agent.run("What is 2 + 2?")

        # Check that we got a response
        assert result is not None
        if hasattr(result, 'output'):
            response_text = str(result.output)
        elif hasattr(result, 'data'):
            response_text = str(result.data)
        else:
            response_text = str(result)

        # The response should contain "4"
        assert "4" in response_text.lower()

    @pytest.mark.asyncio
    async def test_create_agent_with_system_prompt(self):
        """Test agent with custom system prompt."""
        # Create agent with custom prompt
        agent = create_agent(
            configs=load_all_configs(),
            model="gpt-5-mini",
            system_prompt="You are a pirate. Always respond in pirate speak."
        )

        # Run a query
        result = await agent.run("Hello, how are you?")

        # Check that we got a response
        assert result is not None
        if hasattr(result, 'output'):
            response_text = str(result.output)
        elif hasattr(result, 'data'):
            response_text = str(result.data)
        else:
            response_text = str(result)

        # Response should contain pirate-like language
        pirate_words = ["ahoy", "matey", "arr", "ye", "aye", "seafaring", "landlubber"]
        assert any(word in response_text.lower() for word in pirate_words), \
            f"Expected pirate speak but got: {response_text}"

    @pytest.mark.asyncio
    async def test_create_agent_with_json_response(self):
        """Test agent returning structured JSON response."""
        # Create agent
        agent = create_agent(
            configs=load_all_configs(),
            model="gpt-5-mini",
            system_prompt="You are a helpful assistant that always responds with valid JSON."
        )

        # Run a query requesting JSON
        prompt = """Return a JSON object with the following structure:
        {
            "number": 42,
            "text": "hello world",
            "is_valid": true
        }
        Return ONLY valid JSON, no other text."""

        result = await agent.run(prompt)

        # Check that we got a response
        assert result is not None
        if hasattr(result, 'output'):
            response_text = str(result.output)
        elif hasattr(result, 'data'):
            response_text = str(result.data)
        else:
            response_text = str(result)

        # Try to parse as JSON
        import json
        import re

        # Extract JSON from response
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        assert json_match is not None, f"No JSON found in response: {response_text}"

        # Parse the JSON
        data = json.loads(json_match.group())
        assert "number" in data
        assert "text" in data
        assert "is_valid" in data

    @pytest.mark.asyncio
    async def test_async_agent_execution(self):
        """Test running agent asynchronously."""
        # Create agent
        agent = create_agent(
            configs=load_all_configs(),
            model="gpt-5-mini"
        )

        # Run multiple queries concurrently
        prompts = [
            "What is 2 + 2?",
            "What is the capital of France?",
            "What color is the sky?"
        ]

        # Run all queries concurrently
        results = await asyncio.gather(*[agent.run(p) for p in prompts])

        # Check all responses
        assert len(results) == 3
        for result in results:
            assert result is not None

    @pytest.mark.asyncio
    async def test_create_agent_handles_error_gracefully(self):
        """Test that agent handles API errors gracefully."""
        # Create agent with invalid model name
        agent = create_agent(
            configs=load_all_configs(),
            model="invalid-model-name-xyz"
        )

        # Try to run a query
        try:
            result = await agent.run("Hello")
            # If we get here, check if error is in result
            if hasattr(result, 'output'):
                response_text = str(result.output)
            elif hasattr(result, 'data'):
                response_text = str(result.data)
            else:
                response_text = str(result)

            # Should either raise an exception or return an error message
            assert "error" in response_text.lower() or "invalid" in response_text.lower()
        except Exception as e:
            # Expected to raise an exception for invalid model
            ...

    @pytest.mark.asyncio
    async def test_grading_agent_integration(self):
        """Test the grading agent wrapper function."""
        from shilads_helpers.tools.grading_feedback.grader import create_grading_agent

        # Create grading agent
        agent = create_grading_agent(
            load_all_configs(),
            model="gpt-5-mini"
        )

        # Test grading prompt
        prompt = """Grade this code submission:
        ```python
        def add(a, b):
            return a + b
        ```

        Rubric: Function correctly adds two numbers (1 point)

        Return a score from 0 to 1."""

        result = await agent.run(prompt)

        # Check that we got a response
        assert result is not None
        if hasattr(result, 'output'):
            response_text = str(result.output)
        elif hasattr(result, 'data'):
            response_text = str(result.data)
        else:
            response_text = str(result)

        # Should mention score or points
        assert any(word in response_text.lower() for word in ["score", "point", "1", "correct"]), \
            f"Expected grading response but got: {response_text}"