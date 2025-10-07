# MIRA (Mentor-Informed Review Assistant)

AI-assisted feedback with human review. 
MIRA collaborates with an instructor on grading criteria and then drafts feedback that instructors can review and edit before finalizing.

## What MIRA Does

1. **Rubric co-creation** - AI helps you create and refine a rubric for your assignment
2. **Common mistake calibration** - AI reviews submissions and your rubric to create a *calibrated* rubric that includes common mistakes and scoring adjustments   
3. **Drafts grading feedback** - AI generates initial feedback based on your rubric
4. **Provides human review interface** - Web UI for editing all AI-generated feedback
5. **Protects privacy** - Automatically anonymizes student data during grading
6. **Integrates with Moodle** - Works with standard Moodle export format

## Installation

```bash
# Install uv package manager (macOS)
brew install uv

# Create virtual environment and install
uv venv
source .venv/bin/activate
uv pip install -e .

# Install claude code (optional, for grade-with-claude, license required)
npm install -g @anthropic-ai/claude-code

# Download spaCy model for PII detection
python -m spacy download en_core_web_lg

# Create config/local.yaml with your OpenAI API key (see Configuration section below)
```

## Quick Start

Generate feedback using the AI-assisted workflow:

```bash
grade-with-claude moodle_download.zip hw/
```

Or, if you want to run the steps without Claude, by hand:

```bash
# 1. Prepare submissions (creates 3 directories)
prep-moodle --zip moodle_download.zip --workdir hw/

# 2. Create your rubric in hw/2_redacted/rubric.md

# 3. Run grading (AI drafts feedback)
grade-batch -s hw/2_redacted/ -r hw/2_redacted/rubric.md

# 4. Review and edit in web interface
grade-review --workdir hw/

# 5. Restore names for final upload
anonymize-dir restore hw/2_redacted/ hw/3_restored/ hw/2_redacted/anonymization_mapping.json
```

Upload `hw/3_restored/moodle_grades_final.csv` to Moodle.

📚 **Full documentation:** See [feedback/MIRA_WORKFLOW.md](feedback/MIRA_WORKFLOW.md)

## Main Components

### Grading Tools

#### grade-batch
Runs AI grading on multiple submissions in parallel:
```bash
grade-batch --submissions-dir hw/2_redacted/ --rubric rubric.md
```

#### grade-review
Web interface for reviewing and editing AI-generated feedback:
```bash
grade-review --workdir hw/
```
Opens browser with:
- Side-by-side view of submissions and feedback
- Editable scores and comments
- Real-time statistics
- Export to CSV

#### grade-with-claude
Interactive grading session with Claude Code:
```bash
grade-with-claude --zip submissions.zip --workdir hw/
```
Claude helps create rubric, runs grading, and launches review interface.

### Privacy Tools

#### prep-moodle
Prepares Moodle submissions with automatic anonymization:
```bash
prep-moodle --zip submissions.zip --workdir hw/
```
Creates:
- `0_submitted/` - Original files
- `1_prep/` - Processed submissions with original names
- `2_redacted/` - Anonymized for grading

#### anonymize-dir
General-purpose directory anonymization:
```bash
# Anonymize any directory
anonymize-dir anonymize source/ output/

# Restore original content
anonymize-dir restore output/ restored/ -m anonymization_mapping.json
```

## Directory Structure After Grading

```
hw/
├── 0_submitted/          # Original Moodle files
├── 1_prep/              # Processed with real names
├── 2_redacted/          # Anonymized for grading
│   ├── rubric.md
│   ├── grading_results.yaml
│   └── REDACTED_*/feedback.yaml
└── 3_restored/          # Final output with real names
    └── moodle_grades_final.csv
```

## Creating Rubrics

Rubrics use markdown table format:

```markdown
| Component | Points | Criteria |
|-----------|--------|----------|
| Code Functionality | 40 | Runs correctly, produces expected output |
| Code Quality | 20 | Clean, readable, well-structured |
| Documentation | 15 | Clear comments and docstrings |
| Testing | 15 | Appropriate test cases |
| Style | 10 | Follows conventions |
| **Total** | **100** | |
```

## Configuration

**Required:** Create `config/local.yaml` with your OpenAI API key:

```yaml
openai:
  api_key: "your-api-key-here"
  organization: "your-org-id"  # Optional
```

Edit `config/default.yaml` to change:
- AI model selection for grading (default: gpt-5)
- Presidio PII detection settings
- File types to process
- Exclude patterns

## Development

### Running Tests
```bash
# Fast tests only (default, ~15 seconds)
pytest

# Include slow integration tests
pytest --with-slow-integration

# Specific test file
pytest tests/test_grading_feedback.py -v
```

### Project Structure
```
mira-grader/
├── mira/               # Python package
│   ├── libs/           # Shared libraries
│   ├── tools/          # Main tools
│   └── scripts/        # Utility scripts
├── config/             # YAML configuration
├── feedback/           # Documentation and workflows
└── tests/              # Test suite
```

### Adding New Tools
1. Create directory under `mira/tools/your_tool/`
2. Add entry point in `pyproject.toml`
3. Reinstall: `uv pip install -e .`

## API Keys Required

- **OpenAI API key** for grading - must be configured in `config/local.yaml` (see Configuration section above)

## License

Personal use - not for distribution