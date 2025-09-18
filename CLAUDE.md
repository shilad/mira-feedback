# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a collection of Python utilities and scripts for academic (Macalester CS/DS) and industry (Indeed AI) work. The project uses `uv` for package management and is structured as a proper Python package named `shilads_helpers`.

## Common Commands

### Grading Commands
**📚 Complete Grading Guide:** See [feedback/GRADING_WORKFLOW.md](feedback/GRADING_WORKFLOW.md) for step-by-step instructions, rubric templates, and troubleshooting.

**IMPORTANT:** Always use the `2_redacted` directory when grading to protect student privacy. Never grade from `0_submitted` or `1_prep` directories.

#### Quick Reference
```bash
# Grade a single submission (from redacted directory)
grade-submission --submission-dir hw/2_redacted/REDACTED_PERSON1_ID/ --rubric rubric.md

# Grade all submissions in parallel (ALWAYS use 2_redacted)
grade-batch --submissions-dir hw/2_redacted/ --rubric rubric.md

# Batch grade with custom settings (from redacted directory)
grade-batch -s hw/2_redacted/ -r rubric.md --max-threads 8 --model gpt-4

# Save summary to specific location
grade-batch -s hw/2_redacted/ -r rubric.md --summary grading_results.yaml
```

### Development Setup
```bash
# Install uv (if not already installed)
brew install uv  # macOS with Homebrew

# Create and activate virtual environment
uv venv
source .venv/bin/activate

# Install package in editable mode with dependencies
uv pip install -e .

# For local LLM anonymization with gated models, authenticate with Hugging Face
huggingface-cli login  # You'll need a token from https://huggingface.co/settings/tokens
```

### Testing
```bash
# Run fast tests only (default, ~15 seconds)
pytest

# Run all tests including slow integration tests
pytest --with-slow-integration

# Run specific test files
pytest tests/test_config_loader.py -v
pytest tests/test_dir_anonymizer.py -v
pytest tests/test_moodle_prep.py -v
pytest tests/test_moodle_integration.py -v
pytest tests/test_llm.py -v
pytest tests/test_llm_integration.py -v
pytest tests/test_grading_feedback.py -v
pytest tests/test_batch_grader.py -v
pytest tests/test_submission_utils.py -v

# Run single test
pytest tests/test_dir_anonymizer.py::test_custom_config -v

# Run chunking tests
pytest tests/test_text_chunker.py -v
pytest tests/test_llm_backend_chunking.py -v

# Run only integration tests (API tests)
pytest -m "integration_test"

# Run only slow integration tests
pytest -m "slow_integration_test"
```

**Important:** Always use plain `pytest` command, not `python -m pytest`. The project is configured to use `pytest` directly with proper markers and settings.

The test suite is organized with pytest markers:
- **Fast tests** (default): Unit tests and quick integration tests that run in ~15 seconds total
- **`integration_test`**: Tests that require API keys (OpenAI) but run relatively quickly
- **`slow_integration_test`**: Tests that take 40+ seconds each (LLM model loading, heavy processing)

### Linting
```bash
# Install and run ruff
uv pip install ruff
ruff check shilads_helpers/
ruff format shilads_helpers/
```

## Architecture

### Package Structure
The codebase follows a standard Python package layout with `shilads_helpers/` as the main package:
- **libs/**: Shared libraries (config_loader, local_anonymizer, text_chunker, llm)
- **tools/**: Multi-file tools (dir_anonymizer, moodle_prep, grading_feedback)
- **scripts/**: Single-file utilities (currently empty, ready for simple scripts)

### Configuration System
- Uses YAML-based configuration in `config/` directory
- `config_loader.py` provides functions to load and merge configs
- `default.yaml` contains base settings
- `local.yaml` (gitignored) for local overrides
- Config paths are resolved relative to project root (2 levels up from libs/)

### Directory Anonymizer Tool
Main tool in `tools/dir_anonymizer/`:
- **anonymizer.py**: Main anonymization logic with file/directory processing
- **deanonymizer.py**: Restores original content using saved mappings
- **cli.py**: Command-line interface with anonymize, restore, and accuracy commands
- **accuracy.py**: Accuracy testing framework for PII detection validation

### Local Anonymizer Library
In `libs/local_anonymizer/`:
- **anonymizer.py**: LocalAnonymizer class with entity memory and reset functionality
- **llm_backend.py**: LLM integration with automatic text chunking for large files
- **regex_backend.py**: Fallback regex patterns for PII detection

### Text Processing Utilities
In `libs/`:
- **text_chunker.py**: Generator-based text chunking with token counting and overlap

### LLM Utilities
In `libs/`:
- **llm.py**: Utilities for creating pydantic-ai agents with OpenAI models
  - Automatic configuration loading from YAML
  - Support for o1 reasoning models with automatic settings management
  - System prompt customization

### Grading Feedback Tool
In `tools/grading_feedback/`:
- **grader.py**: OpenAI-based grading with structured output and async support
- **batch_grader.py**: Parallel batch grading for multiple submissions with async/await
- **batch_cli.py**: CLI for batch grading with progress tracking
- **submission_utils.py**: Utilities for processing submission directories
- **rubric_parser.py**: Parses rubric criteria from markdown tables
- **models.py**: Pydantic models for grading results
- **cli.py**: Command-line interface for single submission grading

### Import Structure
All imports use absolute imports from `shilads_helpers` package:
```python
from shilads_helpers.libs.config_loader import load_all_configs
from shilads_helpers.tools.dir_anonymizer.anonymizer import DirectoryAnonymizer
```

## Key Dependencies
- **uv**: Fast package manager (replaces pip)
- **transformers**: Hugging Face library for local LLM models
- **torch**: PyTorch for model inference
- **huggingface-hub**: For authenticated model access
- **sentencepiece**: Tokenizer for certain models
- **protobuf**: Required for some model formats
- **PyYAML**: Configuration file handling
- **tqdm**: Progress bars
- **faker**: Fallback for generating replacement data
- **pydantic-ai**: Framework for structured LLM output with OpenAI
- **openai**: OpenAI API client
- **pytest**: Testing framework with marker support

## Adding New Tools

1. Create directory under `shilads_helpers/tools/your_tool/`
2. Add `__init__.py` with exports
3. For CLI tools, add entry point in `pyproject.toml`:
   ```toml
   [project.scripts]
   your-command = "shilads_helpers.tools.your_tool.cli:main"
   ```
4. Reinstall package: `uv pip install -e .`

## Configuration Usage
Tools should use the config system:
```python
from shilads_helpers.libs.config_loader import load_all_configs, get_config

config = load_all_configs()  # Loads all YAML files from config/
value = get_config("anonymizer.file_types", config)  # Dot notation access
```

## Important Implementation Notes

### Anonymizer Improvements (Recent Changes)
1. **Removed anonLLM dependency**: Now uses only local LLM models via Hugging Face transformers
2. **Entity memory**: LocalAnonymizer remembers entities and reuses tags (John Doe always becomes REDACTED_PERSON1)
3. **Text chunking**: Automatically handles large files by chunking with overlap
4. **Filename anonymization**: Uses systematic naming (FILE_0001, DIR_0001) instead of random words
5. **Accuracy testing**: Standalone CLI command for testing PII detection accuracy
6. **Required arguments**: `anonymize` command now requires both input and output directories

### Testing Strategy
- Unit tests use mocks to avoid downloading LLM models
- Accuracy tests can run against YAML test cases
- Text chunking has comprehensive test coverage
- All imports should be absolute from `shilads_helpers` package
- Tests are organized with pytest markers for performance optimization
- Slow tests (40+ seconds) are marked with `@pytest.mark.slow_integration_test`
- Fast tests run by default, slow tests can be run with `--with-slow-integration`

### Recent LLM Integration Changes
1. **Centralized LLM agent creation**: `libs/llm.py` provides `create_agent()` function
2. **Simplified configuration**: Agent creation now loads configs automatically
3. **o1 model support**: Automatic handling of reasoning-specific settings
4. **Test organization**: Tests split into fast (default) and slow (opt-in) categories
5. **Grading feedback tool**: Automated grading with OpenAI
   - Async/await support for parallel processing
   - New batch grading CLI (`grade-batch`) for processing multiple submissions concurrently
   - Smart file selection for large submissions
   - Progress tracking with tqdm
   - Unified mappings format for anonymization (flat dict structure)
6. **Anonymization improvements**:
   - Simplified mappings to flat dict format (token -> original)
   - Path caching for consistent directory anonymization
   - Improved consistency testing
- Note: gpt-5-mini and gpt-5 are both legitimate models with reasoning capabilities