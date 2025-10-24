# MIRA Workflow Guide

Complete guide for grading with MIRA, including manual and AI-assisted workflows.

## Quick Reference

### Standard Workflow (5 Steps)
```bash
# 1. Prepare submissions
prep-moodle --zip moodle.zip --workdir hw/

# 2. Create rubric in hw/2_redacted/rubric.md

# 3. Grade with AI
grade-batch -s hw/2_redacted/ -r hw/2_redacted/rubric.md

# 4. Review and edit
grade-review --workdir hw/

# 5. Restore names
anonymize-dir restore hw/2_redacted/ hw/3_restored/ hw/2_redacted/anonymization_mapping.json
```

### AI-Assisted with Claude (1 Command)
```bash
grade-with-claude --zip moodle.zip --workdir hw/
```
Claude interactively helps create rubric, runs grading, launches review interface, and generates moodle_grades_final.csv.

---

## Part 1: Standard Workflow

### Step 1: Extract and Prepare Submissions

```bash
prep-moodle --zip downloaded_moodle.zip --workdir hw/
```

This creates three directories:
- `hw/0_submitted/` - Original Moodle files (preserved)
- `hw/1_prep/` - Organized with HTML converted to Markdown
- `hw/2_redacted/` - Anonymized for grading (REDACTED_PERSON1, etc.)

**Note:** Anonymization takes ~6 minutes for 25 submissions. Don't interrupt.

### Step 2: Create Grading Rubric

Review a few submissions to understand the assignment:
```bash
# List submissions
ls hw/1_prep/

# View a sample
cat "hw/1_prep/Student Name_ID_assignsubmission_file/submission.Rmd"
```

Create `hw/2_redacted/rubric.md`:

#### For Completion Activities (2-point scale)
```markdown
| Component | Points | Criteria |
|-----------|--------|----------|
| Completion | 2 | Complete submission with required components |

## Scoring
- 2 points: All components complete
- 1 point: Missing 1-2 major components
- 0 points: No submission or minimal attempt
```

#### For Performance Grading
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

**Important:**
- Table must have headers: `| Component | Points | Criteria |`
- Final grades should be whole numbers

### Step 3: Run AI Grading

```bash
grade-batch --submissions-dir hw/2_redacted/ --rubric hw/2_redacted/rubric.md \
  --summary hw/2_redacted/grading_results.yaml
```

Options:
- `--max-threads 8` - Increase parallel processing
- `--model gpt-4` - Use different AI model
- Takes ~2 minutes for 25 submissions

Creates:
- `feedback.yaml` in each submission directory
- `grading_results.yaml` with summary statistics

### Step 4: Review and Edit Feedback

Launch the web interface:
```bash
grade-review --workdir hw/ --port 5001
```

The interface shows:
- **Left panel**: List of all submissions with scores
- **Center**: Editable feedback and scores
- **Right panel**: Files and rubric reference

Features:
- Real names displayed (de-anonymized view)
- Edit scores and comments
- Auto-save with backups
- Export to CSV

### Step 5: Finalize and Export

After reviewing:

1. **Export from interface** - Click "Export" to save final grades

2. **Restore original names**:
```bash
anonymize-dir restore hw/2_redacted/ hw/3_restored/ \
  hw/2_redacted/anonymization_mapping.json
```

3. **Update Moodle grades CSV** - Populate grades from YAML into CSV template:
```bash
update-moodle-grades --restored-dir hw/3_restored/
```

4. **Upload to Moodle** - Use `hw/3_restored/moodle_grades_final.csv`

---

## Part 2: AI-Assisted Workflow with Claude

### Using grade-with-claude

The `grade-with-claude` command automates the entire workflow:

```bash
grade-with-claude --zip submissions.zip --workdir hw/
```

What happens:
1. Runs `prep-moodle` to prepare submissions
2. Launches Claude Code in the anonymized directory
3. Claude helps you create a rubric interactively
4. Claude runs two-pass grading with calibration
5. Claude launches the review interface
6. After you exit, restores real names automatically
7. Updates moodle_grades.csv with final scores

### Claude's Workflow

When Claude launches, it will:

1. **Ask about the assignment** (immediately)
   - Total point value
   - Assignment description

2. **Create draft rubric**
   - Reviews sample submissions
   - Proposes rubric based on requirements
   - Iterates with you until approved

3. **Run two-pass grading**
   - Pass 1: Initial grading with base rubric
   - Calibration: Analyzes patterns, creates adjustments
   - Pass 2: Final grading with calibrated rubric

4. **Launch review interface**
   - Opens web UI for you to review/edit
   - Waits while you work in browser

5. **Complete when you're done**
   - You tell Claude you're finished
   - Exit restores real names automatically

### Working with Claude

**Claude will:**
- Create and refine rubrics
- Run grading commands
- Answer questions about submissions
- Help interpret results

**Claude won't:**
- Access original (non-anonymized) data
- Edit feedback while review interface is open
- Make changes after you say you're done

**Common commands Claude uses:**
```bash
# View submissions
cat REDACTED_PERSON1_*/*.Rmd

# Grade all submissions
grade-batch --submissions-dir . --rubric rubric.md

# Generate calibrated rubric
grade-calibrate -r rubric.md -g grading_pass1.yaml -o calibrated_rubric.md

# Launch review interface
grade-review --workdir .. --port 5001
```

---

## Part 3: Reference

### Directory Structure

```
hw/
├── 0_submitted/              # Original Moodle exports
│   └── Student Name_ID_assignsubmission_file/
├── 1_prep/                   # Processed, original names
│   ├── moodle_grades.csv    # All students listed
│   └── Student Name_ID_assignsubmission_file/
│       └── submission.md     # HTML converted to Markdown
├── 2_redacted/               # Anonymized for grading
│   ├── rubric.md
│   ├── grading_results.yaml
│   ├── anonymization_mapping.json
│   └── REDACTED_PERSON1_ID_assignsubmission_file/
│       ├── submission.md
│       └── feedback.yaml
└── 3_restored/               # Final with real names
    ├── moodle_grades_final.csv
    └── Student Name_ID_assignsubmission_file/
        └── feedback.yaml
```

### Command Reference

#### Preparation
```bash
# Standard preparation
prep-moodle --zip file.zip --workdir output/

# Skip anonymization (faster)
prep-moodle --zip file.zip --workdir output/ --skip-stage 2_redacted

# Dry run
prep-moodle --zip file.zip --workdir output/ --dry-run
```

#### Grading
```bash
# Single submission
grade-submission --submission-dir path/ --rubric rubric.md

# Batch grading
grade-batch --submissions-dir path/ --rubric rubric.md

# With options
grade-batch -s path/ -r rubric.md --max-threads 8 --model gpt-4
```

#### Review
```bash
# Standard review
grade-review --workdir hw/

# Custom port
grade-review --workdir hw/ --port 8080

# No auto-browser
grade-review --workdir hw/ --no-browser
```

#### Anonymization
```bash
# Anonymize directory
anonymize-dir anonymize source/ output/

# Restore with mappings
anonymize-dir restore output/ restored/ -m mapping.json

# Test accuracy
anonymize-dir accuracy
```

#### Moodle Integration
```bash
# Update moodle_grades.csv with scores from feedback.yaml files
update-moodle-grades --restored-dir hw/3_restored/

# Custom CSV path
update-moodle-grades -d hw/3_restored/ -c hw/3_restored/custom_grades.csv
```

### Rubric Guidelines

#### Format Requirements
- Must use markdown table with specific headers
- Headers must be: `| Component | Points | Criteria |`
- Include total row with `**Total**` in component column

#### Scoring Philosophy
- **Completion grading**: Focus on effort, round generously
- **Performance grading**: Balance correctness with effort
- **Whole numbers**: Final scores should be integers

#### Common Rubric Templates

**Simple Completion (2 points)**
```markdown
| Component | Points | Criteria |
|-----------|--------|----------|
| Submission | 2 | Completed all required elements |
```

**Multi-component Activity (10 points)**
```markdown
| Component | Points | Criteria |
|-----------|--------|----------|
| Data Loading | 2 | Successfully loads dataset |
| Analysis | 4 | Performs required analysis |
| Visualization | 3 | Creates appropriate plots |
| Interpretation | 1 | Explains findings |
| **Total** | **10** | |
```

**Full Assignment (100 points)**
```markdown
| Component | Points | Criteria |
|-----------|--------|----------|
| Problem 1 | 25 | Solution correctness and approach |
| Problem 2 | 25 | Solution correctness and approach |
| Code Quality | 20 | Style, structure, readability |
| Documentation | 15 | Comments, docstrings, explanations |
| Testing | 15 | Test coverage and quality |
| **Total** | **100** | |
```

### Troubleshooting

#### Issue: Grader gives fractional scores
Round according to your policy. For activities, round up generously (≥1.0 → 2).

#### Issue: Rubric parsing errors
Check table format matches exactly: `| Component | Points | Criteria |`

#### Issue: Slow anonymization
The local LLM takes time (~6 min for 25 submissions). Start it and work on something else.

#### Issue: Can't access review interface
Check port isn't in use. Try `--port 8080` instead of default 5001.

#### Issue: Missing students in CSV
Check `1_prep/moodle_grades.csv` - all enrolled students should be listed.

### Tips for Efficient Grading

1. **Review samples first** - Check 2-3 submissions before creating rubric
2. **Use parallel processing** - `--max-threads 8` speeds up batch grading
3. **Be consistent** - Use calibrated rubrics for large batches
4. **Save rubric templates** - Reuse for similar assignments
5. **Document decisions** - Note any grading policies in rubric

### Privacy and Security

- **Anonymization**: All grading happens on REDACTED_PERSON tokens
- **Local processing**: Anonymization uses local LLM (no external API)
- **Reversible**: All anonymization can be perfectly reversed
- **No data leakage**: Original names never sent to OpenAI

### Performance Expectations

For 25 submissions:
- Prep-moodle: ~30 seconds (with anonymization)
- Batch grading: ~2 minutes (8 threads)
- Review interface: Instant
- Restoration: ~30 seconds

---

## Next Steps

After grading:
1. Archive the entire `hw/` directory for records
2. Update rubric templates based on common issues
3. Share summary statistics with students (optional)
4. Note any assignment improvements for next time