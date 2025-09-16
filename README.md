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

## Libraries

### LLM Utilities (`libs/llm.py`)
Provides utilities for creating and configuring AI agents using pydantic-ai with OpenAI models.

```python
from shilads_helpers.libs.llm import create_agent

# Create a basic agent
agent = create_agent(configs=None, model="gpt-5-mini")

# Create an agent with custom settings
agent = create_agent(
    configs=None,
    model="gpt-5-mini",
    settings_dict={"openai_reasoning_effort": "high"},
    system_prompt="You are a helpful coding assistant"
)

# Run the agent
import asyncio
result = asyncio.run(agent.run("What is 2 + 2?"))
```

Features:
- Automatic configuration loading from YAML files
- Support for OpenAI models including o1 reasoning models
- Automatic handling of reasoning-specific settings
- System prompt customization

## Available Tools

### Grading Feedback Tool
Automated grading system using OpenAI for evaluating student submissions against rubrics.

#### Single Submission Grading
```bash
# Grade one submission
grade-submission --submission-dir hw/student1/ --rubric rubric.md

# Specify output file and model
grade-submission -s hw/student1/ -r rubric.md -o feedback.yaml --model gpt-4
```

#### Batch Grading (New)
```bash
# Grade all submissions in parallel
grade-batch --submissions-dir hw/submissions/ --rubric rubric.md

# Use more threads for faster processing
grade-batch -s hw/submissions/ -r rubric.md --max-threads 8

# Save summary to specific location
grade-batch -s hw/submissions/ -r rubric.md --summary grading_results.yaml

# Continue even if some submissions fail
grade-batch -s hw/submissions/ -r rubric.md --continue-on-error
```

#### Key Features:
- **Parallel Processing**: Batch grader uses async/await for concurrent grading
- **Smart File Selection**: Automatically selects relevant files for large submissions
- **Progress Tracking**: Real-time progress bars with tqdm
- **Structured Output**: Generates YAML feedback files with detailed component scores
- **Rubric Parsing**: Supports markdown tables with criteria and point values
- **Error Handling**: Graceful failure handling with detailed error reporting
- **Summary Reports**: Aggregated statistics and score distributions

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

## Grading Workflow

This section describes a complete workflow for grading student submissions downloaded from Moodle.

### Step 1: Prepare Submissions from Moodle
First, extract and organize the downloaded Moodle zip file:

```bash
# Extract submissions into organized directories
prep-moodle --zip downloaded_submissions.zip --workdir ./grading_workspace/

# This creates:
# - 0_submitted/: Raw file submissions
# - 1_prep/: HTML converted to Markdown with moodle_grades.csv
# - 2_redacted/: Anonymized submissions (optional, can skip with --skip-stage)
```

### Step 2: Gather Assignment Context
Before creating a rubric, collect:
1. The original assignment instructions
2. Any specific requirements or constraints
3. Expected deliverables and their format

### Step 3: Develop the Grading Rubric
Create a `rubric.md` file with clear criteria. The rubric should use a markdown table format:

```markdown
# Assignment Rubric

| Criteria | Points | Description |
|----------|--------|-------------|
| Code Functionality | 40 | Program runs correctly and produces expected output |
| Code Quality | 20 | Clean, readable code with proper structure |
| Documentation | 15 | Clear comments and docstrings |
| Testing | 15 | Includes appropriate test cases |
| Style | 10 | Follows language conventions and best practices |
```

Tips for effective rubrics:
- Be specific about what constitutes full vs. partial credit
- Include both objective (functionality) and subjective (quality) criteria
- Consider common mistakes you've seen in sample submissions
- Align point values with assignment emphasis

### Step 4: Run Batch Grading
Grade all submissions in parallel:

```bash
# IMPORTANT: Always grade from the 2_redacted directory to protect student privacy
# Basic batch grading
grade-batch --submissions-dir ./grading_workspace/2_redacted/ --rubric rubric.md

# With custom settings
grade-batch -s ./grading_workspace/2_redacted/ -r rubric.md \
  --max-threads 8 \
  --model gpt-4 \
  --summary grading_summary.yaml
```

**Note:** Always use the `2_redacted` directory for grading to ensure student PII is protected. The grading tool should never access the original submissions in `0_submitted` or `1_prep`.

### Step 5: Review and Analyze Results
After grading:

1. **Check the summary file** (`grading_summary.yaml`):
   - Overall statistics and score distribution
   - Common strengths and weaknesses
   - Submissions that may need manual review

2. **Review individual feedback** (in each submission directory):
   - Each submission gets a `feedback.yaml` file
   - Contains detailed scores and comments for each rubric criterion

3. **Identify patterns**:
   - Common misconceptions or errors
   - Areas where many students excelled or struggled
   - Potential improvements to assignment instructions

4. **Manual review cases**:
   - Unusually high or low scores
   - Submissions with processing errors
   - Edge cases not covered by rubric

### Step 6: Refine and Iterate
Based on patterns observed:
- Adjust rubric criteria for clarity or fairness
- Add specific examples to rubric descriptions
- Consider partial credit guidelines for common errors
- Update assignment instructions for next time

### Complete Example Workflow

```bash
# 1. Prepare Moodle submissions
prep-moodle --zip hw3_submissions.zip --workdir ./hw3_grading/

# 2. Review a few submissions to understand the landscape
ls ./hw3_grading/2_redacted/
# Examine 2-3 submissions manually (use 2_redacted to protect privacy)

# 3. Create rubric.md based on assignment requirements

# 4. Run batch grading (ALWAYS use 2_redacted directory)
grade-batch -s ./hw3_grading/2_redacted/ -r rubric.md \
  --summary ./hw3_grading/summary.yaml \
  --max-threads 10

# 5. Review summary
cat ./hw3_grading/summary.yaml

# 6. Check specific feedback
cat ./hw3_grading/2_redacted/REDACTED_PERSON1_ID_assignsubmission_file/feedback.yaml

# 7. Update grades in the CSV (if needed)
# The moodle_grades.csv in 2_redacted will contain anonymized results
```

## Configuration

The project uses a YAML-based configuration system. Settings are loaded from:
- `config/default.yaml` - Base configuration
- `config/local.yaml` - Local overrides (not committed to git)

## Development

### Running Tests
```bash
# Run fast tests only (default) - takes ~15 seconds
pytest

# Run all tests including slow integration tests
pytest --with-slow-integration

# Run specific test files
pytest tests/test_config_loader.py -v
pytest tests/test_dir_anonymizer.py -v
pytest tests/test_text_chunker.py -v
pytest tests/test_llm_backend_chunking.py -v
pytest tests/test_moodle_prep.py -v
pytest tests/test_moodle_integration.py -v

# Run tests for local anonymizer
pytest tests/test_local_anonymizer.py -v
pytest tests/test_grading_feedback.py -v
pytest tests/test_batch_grader.py -v
pytest tests/test_submission_utils.py -v

# Run only integration tests (API tests)
pytest -m "integration_test"

# Run only slow integration tests
pytest -m "slow_integration_test"
```

**Note:** Always use plain `pytest` command, not `python -m pytest`. The project is configured to use `pytest` directly.

The test suite is organized with pytest markers:
- **Fast tests** (default): Unit tests and quick integration tests that run in ~15 seconds
- **`integration_test`**: (run by default) Tests that require API keys but run relatively quickly
- **`slow_integration_test`**: Tests that take 40+ seconds (LLM model loading, etc.)

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