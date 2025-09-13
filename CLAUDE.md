# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a collection of Python utilities and scripts for academic (Macalester CS/DS) and industry (Indeed AI) work. The project uses `uv` for package management and is structured as a proper Python package named `shilads_helpers`.

## Common Commands

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
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_config_loader.py -v
python -m pytest tests/test_dir_anonymizer.py -v

# Run single test
python -m pytest tests/test_dir_anonymizer.py::test_custom_config -v

# Run chunking tests
python -m pytest tests/test_text_chunker.py -v
python -m pytest tests/test_llm_backend_chunking.py -v
```

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
- **libs/**: Shared libraries (config_loader)
- **tools/**: Multi-file tools (dir_anonymizer)
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