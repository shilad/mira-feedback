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
- **Systematic filename anonymization**: Files become FILE_0001.ext, directories become DIR_0001
- **Complete reversibility**: All anonymization mappings are saved for perfect restoration
- **Accuracy testing framework**: Built-in test suite to validate PII detection accuracy

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