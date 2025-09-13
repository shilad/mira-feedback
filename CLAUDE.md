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

# Install spaCy model (required for anonymizer tool)
uv pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
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
- **anonymizer.py**: Uses anonLLM to anonymize PII in files, config-driven file type filtering
- **deanonymizer.py**: Restores original content using saved mappings
- **cli.py**: Command-line interface, registered as `anonymize-dir` entry point
- Handles the problematic address pattern from anonLLM by using a simplified regex

### Import Structure
All imports use absolute imports from `shilads_helpers` package:
```python
from shilads_helpers.libs.config_loader import load_all_configs
from shilads_helpers.tools.dir_anonymizer.anonymizer import DirectoryAnonymizer
```

## Key Dependencies
- **uv**: Fast package manager (replaces pip)
- **anonLLM**: PII anonymization library
- **spaCy**: NLP for entity recognition (requires en_core_web_sm model)
- **PyYAML**: Configuration file handling
- **tqdm**: Progress bars

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