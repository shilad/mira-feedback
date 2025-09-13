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
# Anonymize a directory
anonymize-dir anonymize /path/to/source

# Restore using saved mappings
anonymize-dir restore anonymized_output restored_output -m anonymization_mapping.json

# Run accuracy tests
anonymize-dir accuracy
```

The tool:
- Uses local LLM models (e.g., Llama, Qwen) for PII detection
- Falls back to regex patterns when LLM is unavailable
- Detects and anonymizes names, emails, phone numbers, SSNs, credit cards, IP addresses
- Preserves file structure and functionality
- Saves mappings for complete reversibility
- Configurable via `config/default.yaml`

## Configuration

The project uses a YAML-based configuration system. Settings are loaded from:
- `config/default.yaml` - Base configuration
- `config/local.yaml` - Local overrides (not committed to git)

## Development

### Running Tests
```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_config_loader.py -v
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