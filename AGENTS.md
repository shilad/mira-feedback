# AGENTS.md

This file provides guidance to Codex (OpenAI's GPT-5-based coding agent) when working with code in this repository.

## Project Overview

MIRA (Mentor-Informed Review Assistant) - AI-assisted grading with human review. The project uses `uv` for package management and is structured as a Python package.

## Common Commands

### Grading Commands
**📚 Complete Grading Guide:** See [feedback/MIRA_WORKFLOW.md](feedback/MIRA_WORKFLOW.md) for step-by-step instructions, rubric templates, and troubleshooting.

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

# Review and edit AI-generated feedback (human-in-the-loop web interface)
grade-review --workdir hw/
```

### Evidence Builder (Default)
Grading now runs through the deterministic evidence pipeline, which summarizes notebooks, R Markdown, CSVs, JSON/YAML, PDFs, HTML, and code before sending anything to the model.

**Recent Improvements:**
- **Truncation tracking**: Evidence cards now include warnings when content exceeds size limits
- **HTML support**: New HTML plugin processes .html and .htm files
- **Increased file size limit**: Now 100KB per file (up from 60KB) for better coverage
- **Smart content processing**:
  - Enhanced image redaction in markdown/HTML files
  - Long line truncation for better readability
  - Intelligent code block handling

Tune behavior via `config/local.yaml`:
```yaml
# config/local.yaml
grading:
  evidence_builder:
    save_artifacts: true         # writes .mira_evidence/evidence.{json,txt} per submission
    cache_dir: ".mira_cache/evidence"
    policy:
      max_total_bytes: 500000
      max_files: 40
      max_text_bytes_per_file: 100000  # increased from 60000
      max_notebook_cells: 200
      max_csv_head_rows: 50
      max_csv_random_rows: 150
```
Caches default to `.mira_cache/evidence` at the project root and are automatically ignored when compiling evidence cards.

### Development Setup
```bash
# Install uv (if not already installed)
brew install uv  # macOS with Homebrew

# Create and activate virtual environment
uv venv
source .venv/bin/activate

# Install package in editable mode with dependencies
uv pip install -e .

# Download spaCy model for Presidio PII detection
python -m spacy download en_core_web_lg

# REQUIRED: Create config/local.yaml with OpenAI API key
# Copy config/local.yaml.example or create from scratch:
# openai:
#   api_key: "your-api-key-here"
#   organization: "your-org-id"  # Optional
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

# Run only integration tests (API tests)
pytest -m "integration_test"

# Run only slow integration tests
pytest -m "slow_integration_test"
```

**Important:** Always use plain `pytest` command, not `python -m pytest`. The project is configured to use `pytest` directly with proper markers and settings.

The test suite is organized with pytest markers:
- **Fast tests** (default): Unit tests and quick integration tests that run in ~15 seconds total
- **`integration_test`**: Tests that require API keys (OpenAI) but run relatively quickly
- **`slow_integration_test`**: Tests that take 40+ seconds each (heavy processing)

### Linting
```bash
# Install and run ruff
uv pip install ruff
ruff check mira/
ruff format mira/
```

## Architecture

### Package Structure
The codebase follows a standard Python package layout with `mira/` as the main package:
- **libs/**: Shared libraries (config_loader, local_anonymizer, text_chunker, llm, evidence)
- **tools/**: Multi-file tools (dir_anonymizer, moodle_prep, grading_feedback, grading_review_interface)
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
- **presidio_backend.py**: Microsoft Presidio PII detection with spaCy NER models

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
  - System prompts explicitly inform the LLM that submissions are anonymized with REDACTED_* tags
  - Grading prompts include privacy notice about anonymization placeholders
  - Uses adjustments-based feedback model (detailed feedback in score adjustments)
  - Includes truncation warnings from evidence processing
- **batch_grader.py**: Parallel batch grading for multiple submissions with async/await
- **batch_cli.py**: CLI for batch grading with progress tracking
- **submission_utils.py**: Utilities for processing submission directories
- **rubric_parser.py**: Parses rubric criteria from markdown tables (ignores situational adjustments section)
- **models.py**: Pydantic models for grading results
  - ComponentFeedback uses adjustments list for detailed feedback
  - GradingResult includes optional truncation warnings
- **cli.py**: Command-line interface for single submission grading

### Evidence Library
In `libs/evidence/`:
- **builder.py**: Orchestrates evidence extraction from submission directories
- **models.py**: Core data models (EvidenceCard, EvidencePack, EvidencePolicy)
  - Evidence cards now include truncation warnings when content is clamped
- **plugins/**: File type handlers
  - **code.py**: Source code files
  - **notebook.py**: Jupyter notebooks (.ipynb)
  - **pdf.py**: PDF documents
  - **html.py**: HTML files (NEW - supports .html, .htm)
  - **markdown.py**: Markdown and R Markdown files (enhanced image redaction and line truncation)
  - **text.py**: Plain text files
  - **csv_plugin.py**: CSV/TSV files
  - **json_yaml.py**: JSON and YAML files
  - **utils.py**: Shared utilities (file reading with size caps)

### Grading Review Interface
In `tools/grading_review_interface/`:
- **app.py**: Flask web application for reviewing and editing AI-generated feedback
  - DebouncedSaver class for auto-save functionality (2-second debounce)
  - Endpoints for updating submissions, regenerating comments, and batch operations
- **review_interface.py**: Core interface logic for loading/saving grading results
  - Auto-backup on major operations
  - Comment regeneration using evidence packs
- **cli.py**: Command-line interface to launch the web interface
- **templates/index.html**: Main web interface with split-pane layout
  - Regenerate comment button for on-demand feedback updates
- **static/app.js**: JavaScript for interactive editing and navigation
  - Auto-save indicators
  - Comment regeneration UI
- **static/style.css**: Styling with demo mode support
