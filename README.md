# Shilad's Helper Scripts & Tools

A collection of Python utilities and scripts for academic and industry work.

## Installation

This project uses [`uv`](https://github.com/astral-sh/uv) for fast Python package management.

```bash
# Install uv (macOS)
brew install uv

# Create virtual environment and install package
uv venv
source .venv/bin/activate
uv pip install -e .

# For local LLM anonymization with gated models (e.g., Llama), authenticate with Hugging Face
# First, install the Hugging Face CLI and get a token from https://huggingface.co/settings/tokens
uv pip install huggingface-hub

# Then use one of these methods:

# Option 1: Interactive login
huggingface-cli login
# Enter your Hugging Face token when prompted

# Option 2: Login with token directly
huggingface-cli login --token YOUR_HF_TOKEN

# Option 3: Set environment variable
export HF_TOKEN="YOUR_HF_TOKEN"
huggingface-cli login --token $HF_TOKEN
```

**Notes:** 
- For gated models like Llama, you need to accept the license agreement on the model's Hugging Face page first
- You may see warnings about `flash-attn` not being available. This is normal on systems without CUDA (like macOS). The models will automatically use an alternative attention implementation

## Directory Structure

```
shilads-helpers/
├── shilads_helpers/     # Python package
│   ├── libs/           # Shared libraries (config loader)
│   ├── tools/          # Multi-file tools (dir_anonymizer)
│   └── scripts/        # Single-file utilities
├── config/             # YAML configuration files
├── tests/              # Test suite
└── pyproject.toml      # Package configuration
```

## Available Tools

### Moodle Submission Preparation Tool
Prepares Moodle homework submissions for anonymized feedback through a three-stage processing pipeline.

```bash
# Basic usage (grades.csv is automatically generated from submissions)
prep-moodle --zip submissions.zip --workdir ./output/

# Skip the redaction stage (faster processing)
prep-moodle --zip submissions.zip --workdir ./output/ --skip-stage 2_redacted

# Keep original HTML files alongside converted Markdown
prep-moodle --zip submissions.zip --workdir ./output/ --keep-html

# Dry run to see what would be done
prep-moodle --zip submissions.zip --workdir ./output/ --dry-run

# Check existing stage directories
prep-moodle --workdir ./output/ --info
```

#### Processing Stages:
1. **0_submitted**: Extracts file submissions only (online text directories removed)
2. **1_prep**: Generates moodle_grades.csv with all students + converts HTML to Markdown
3. **2_redacted**: Runs full PII redaction for clean output (ready for distribution)

#### Key Features:
- **Automatic moodle_grades.csv generation**: Creates grading spreadsheet from submission directory structure
- **Online text handling**: Captures online text submissions in moodle_grades.csv without copying directories
- **Smart CSV anonymization**: moodle_grades.csv uses column-based redaction (Full name, Email address)
- **HTML to Markdown conversion**: Automatically converts HTML submissions to readable Markdown using html-to-markdown
- **LLM-based PII redaction**: Uses local LLM models to detect and redact PII in both content and filenames
- **Feedback preservation**: Keeps assignfeedback directories and content untouched
- **Clean output**: 2_redacted directory contains only anonymized content
- **Flexible processing**: Skip stages as needed for faster processing
- **Preserves structure**: Maintains Moodle directory naming (Student_ID_type) while redacting names

#### Output Structure:
```
working_dir/
├── 0_submitted/           # File submissions only (no onlinetext dirs)
│   └── [file submissions]/
├── 1_prep/               # HTML converted to Markdown + grades
│   ├── moodle_grades.csv # Generated with all students + online text content
│   └── [file submissions]/
│       └── assignment.md
└── 2_redacted/          # Clean, PII-redacted output
    ├── moodle_grades.csv # Anonymized (REDACTED_PERSON1, etc.)
    └── [REDACTED_PERSON1_ID_type]/  # LLM-redacted filenames
        └── assignment.md
```

### Directory Anonymizer
Anonymizes personally identifiable information (PII) in directories using a local LLM while preserving structure. Useful for sharing code/data samples without exposing sensitive information.

```bash
# Anonymize a directory (both input and output paths are required)
anonymize-dir anonymize /path/to/source /path/to/output

# Keep original filenames (don't anonymize them)
anonymize-dir anonymize /path/to/source /path/to/output --keep-original-filenames

# Restore using saved mappings
anonymize-dir restore anonymized_output restored_output -m anonymization_mapping.json

# Run accuracy tests on built-in test cases
anonymize-dir accuracy

# Run accuracy tests on custom test directory
anonymize-dir accuracy -t /path/to/test/yaml/files
```

#### Key Features:
- **Local LLM-based PII detection**: Uses Hugging Face models (Qwen, Mistral, Gemma) running locally
- **Smart text chunking**: Automatically splits large files into overlapping chunks for LLM processing
- **Entity memory**: Consistently anonymizes the same entities across files (e.g., "John Doe" → "REDACTED_PERSON1")
- **LLM-based filename anonymization**: Uses LLM to detect and redact PII in filenames intelligently
- **Complete reversibility**: All anonymization mappings are saved for perfect restoration
- **Accuracy testing framework**: Built-in test suite to validate PII detection accuracy
- **Moodle integration**: Special handling for moodle_grades.csv with column-based anonymization

#### Detected PII Types:
- Names (persons)
- Email addresses
- Phone numbers
- Physical addresses
- Organizations
- Social Security Numbers (SSN)
- Credit card numbers

#### Configuration:
- Edit `config/default.yaml` to change:
  - LLM model selection (default: Qwen/Qwen3-4B-Instruct-2507)
  - File types to process
  - Exclude patterns
  - Maximum tokens per chunk (for large file handling)
  - Device selection (cpu/cuda/mps)

## Configuration

The project uses a YAML-based configuration system. Settings are loaded from:
- `config/default.yaml` - Base configuration
- `config/local.yaml` - Local overrides (not committed to git)

## Development

### Running Tests
```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test files
python -m pytest tests/test_config_loader.py -v
python -m pytest tests/test_dir_anonymizer.py -v
python -m pytest tests/test_text_chunker.py -v
python -m pytest tests/test_llm_backend_chunking.py -v
python -m pytest tests/test_moodle_prep.py -v
python -m pytest tests/test_moodle_integration.py -v

# Run tests for local anonymizer
python -m pytest tests/test_local_anonymizer.py -v
```

### Adding New Tools

1. Create directory under `shilads_helpers/tools/your_tool/`
2. Add entry point in `pyproject.toml`:
   ```toml
   [project.scripts]
   your-command = "shilads_helpers.tools.your_tool.cli:main"
   ```
3. Reinstall package: `uv pip install -e .`

## Git Conventions

- Keep sensitive data and credentials out of the repository
- Use `.gitignore` for generated files and local configs
- Document complex scripts with inline comments and/or README files

## License

Personal use - not for distribution