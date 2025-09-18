# Moodle Grading Workflow Guide

This guide provides a streamlined workflow for grading Moodle assignments using the `shilads_helpers` tools.

## Quick Start

For most completion-based activities (2-point scale), follow these 7 steps:

1. **Extract & Anonymize**: `prep-moodle --zip "path/to/moodle.zip" --workdir feedback/runs/[assignment-name]`
2. **Review Samples**: Check 2-3 submissions in `feedback/runs/[assignment-name]/1_prep/` to understand the assignment
3. **Create Rubric**: Collaborate with AI to create rubric, save in `feedback/runs/[assignment-name]/2_redacted/rubric.md`
4. **Grade**: `grade-batch -s feedback/runs/[assignment-name]/2_redacted/ -r feedback/runs/[assignment-name]/2_redacted/rubric.md --summary feedback/runs/[assignment-name]/2_redacted/grading_results.yaml`
5. **Update Grades**: Create `moodle_grades_final.csv` with rounded scores in `2_redacted/`
6. **Restore Names**: `anonymize-dir restore feedback/runs/[assignment-name]/2_redacted/ feedback/runs/[assignment-name]/3_restored/ feedback/runs/[assignment-name]/2_redacted/anonymization_mapping.json`
7. **Upload**: Use `3_restored/moodle_grades_final.csv` for Moodle

## Step-by-Step Workflow

### Step 1: Extract and Prepare Submissions

```bash
prep-moodle --zip "/path/to/downloaded/moodle.zip" --workdir hw
```

This creates three directories:
- `hw/0_submitted/` - Original files (preserved)
- `hw/1_prep/` - Organized with original names
- `hw/2_redacted/` - Anonymized for grading (USE THIS)

**IMPORTANT**: The anonymization step takes approximately 6 minutes for ~25 submissions. Do not interrupt the process!

### Step 2: Understand the Assignment

Before creating a rubric, review a few submissions:

```bash
# List submissions
ls hw/1_prep/

# Check file types
find hw/1_prep -name "*.Rmd" -o -name "*.qmd" -o -name "*.py" | head -5

# Read a sample submission
cat "hw/1_prep/Student Name_ID_assignsubmission_file/submission.Rmd"
```

Identify:
- What type of assignment is it? (activity, homework, project)
- What are students submitting? (code, plots, analysis)
- Is this completion-based or performance-based grading?

### Step 3: Create Appropriate Rubric (Collaborative Process)

Work with the AI assistant to create an appropriate rubric:
1. Review 2-3 sample submissions together
2. Discuss point values and requirements
3. For completion activities, consider breaking down into 0.5 point components
4. Review the rubric before finalizing

#### For Completion Activities (0/1/2 points)

Save as `hw/2_redacted/rubric.md`:

```markdown
# Assignment Name - Completion Rubric (2 points)

## Grading Criteria

| Component | Points | Criteria |
|-----------|--------|----------|
| Completion | 2 | Complete submission with required components |

## Scoring Guide

### 2 points (Full Credit)
Student completes ALL required components:
- ✓ [Component 1, e.g., "Loads data"]
- ✓ [Component 2, e.g., "Creates visualization"]
- ✓ [Component 3, e.g., "Includes interpretation"]
- ✓ [Component 4, e.g., "Documents AI usage"]

### 1 point (Partial Credit)
Missing 1-2 major components OR significant errors preventing execution

### 0 points (No Credit)
No submission or minimal attempt

## Notes
- Focus on effort, not perfection
- Simple implementations are acceptable
- Minor errors are okay if effort is shown
```

**Important Format Requirements:**
- Table MUST have headers: `| Component | Points | Criteria |`
- Use exactly this format - the grader is strict about parsing

### Step 4: Run Batch Grading

**Important**: Always save the rubric and grading results in the `feedback/runs/[assignment-name]/2_redacted/` directory for organization.

```bash
# Standard grading
grade-batch --submissions-dir hw/2_redacted/ --rubric hw/2_redacted/rubric.md --summary hw/2_redacted/grading_results.yaml

# With more parallel threads (faster)
grade-batch -s hw/2_redacted/ -r hw/2_redacted/rubric.md --summary hw/2_redacted/grading_results.yaml --max-threads 8

# With specific model
grade-batch -s hw/2_redacted/ -r hw/2_redacted/rubric.md --model gpt-4o-mini --summary hw/2_redacted/grading_results.yaml
```

**Typical timing**: ~1-2 minutes for 25 submissions with 8 threads

### Step 5: Update Grades in CSV

After batch grading, update the `moodle_grades.csv` with final scores:

1. **Apply rounding** based on your rubric policy (e.g., ≥1.5 → 2, 0.5-1.0 → 1)
2. **Handle online-text-only submissions** (students who submitted text but no files)
3. **Save as `moodle_grades_final.csv`** in the `2_redacted/` directory

**Python snippet for updating grades:**
```python
import yaml, csv, re

# Read grading results and apply rounding
with open('feedback/runs/[assignment]/2_redacted/grading_results.yaml', 'r') as f:
    results = yaml.safe_load(f)

# Map scores with rounding logic
# Update moodle_grades.csv → moodle_grades_final.csv
```

### Step 6: Restore Original Names

**IMPORTANT**: Always restore names to see actual student identities for final upload:

```bash
# Restore original names and content
anonymize-dir restore feedback/runs/[assignment]/2_redacted/ \
  feedback/runs/[assignment]/3_restored/ \
  feedback/runs/[assignment]/2_redacted/anonymization_mapping.json
```

This creates `feedback/runs/[assignment]/3_restored/` with:
- Original student names in directories and files
- `moodle_grades_final.csv` with real names ready for Moodle
- All grading feedback files preserved

### Step 7: Finalize and Upload Grades

The AI grader may give fractional scores (1.5, 1.75). You'll need to:

1. **Review the summary**:
```bash
# Check score distribution
grep "Score Distribution" hw/2_redacted/grading_results.yaml -A 30
```

2. **Create final grades** with appropriate rounding:

For lenient completion grading (recommended for activities):
```python
# Quick Python snippet to round grades
import yaml
import csv

with open('hw/2_redacted/grading_results.yaml', 'r') as f:
    results = yaml.safe_load(f)

# Round generously: ≥1.0 → 2, <1.0 → 1
for submission in results['submissions']:
    score = submission['total_score']
    final = 2 if score >= 1.0 else 1 if score > 0 else 0
    # Process as needed...
```

3. **Generate Moodle CSV**:
The file `hw/2_redacted/moodle_grades.csv` contains the template. Update with final grades.

## Common Issues and Solutions

### Issue: Grader gives fractional scores
**Solution**: Always post-process to whole numbers. For activities, round generously (≥1.0 → 2).

### Issue: Rubric parsing errors
**Solution**: Ensure table format is exactly `| Component | Points | Criteria |` with proper markdown.

### Issue: Slow anonymization
**Solution**: The local LLM anonymization takes time. Start it and work on something else.

### Issue: Students missing AI statements
**Solution**: Decide upfront if this is required. For activities, consider being lenient.

## Tips for Efficient Grading

1. **Start with clear expectations**: Determine if it's completion or performance grading
2. **Use parallel processing**: `--max-threads 8` speeds up grading significantly
3. **Be generous with activities**: Round scores up for good faith efforts
4. **Save your rubrics**: Build a library of rubrics for common assignment types
5. **Review before grading**: Always check 2-3 submissions to calibrate the rubric

## Workflow for Different Assignment Types

### Completion Activities (Tidy Tuesday, In-class work)
- Use 2-point scale (0/1/2)
- Focus on effort and completion
- Round scores up generously
- Quick feedback is okay

### Homework Assignments
- Consider more detailed rubric with multiple components
- May use percentage or letter grades
- Balance correctness with effort
- Provide detailed feedback

### Projects
- Create detailed rubric with clear criteria
- Use performance-based grading
- Provide comprehensive feedback
- Consider peer review components

## File Organization

**Directory structure after complete workflow:**
```
feedback/runs/[assignment-name]/
├── 0_submitted/           # Original file submissions
├── 1_prep/               # Organized with original names
├── 2_redacted/           # Anonymized for grading
│   ├── rubric.md
│   ├── grading_results.yaml
│   ├── moodle_grades.csv
│   ├── moodle_grades_final.csv
│   ├── anonymization_mapping.json
│   └── REDACTED_*/       # Student submissions with feedback
└── 3_restored/           # Final output with real names
    ├── moodle_grades_final.csv  # Ready for Moodle upload
    └── [Student Name]*/          # Restored submissions
```

This keeps everything organized and makes it easy to find files for future reference.

## Next Steps

After grading:
1. **Always restore names**: `anonymize-dir restore feedback/runs/[assignment]/2_redacted/ feedback/runs/[assignment]/3_restored/ feedback/runs/[assignment]/2_redacted/anonymization_mapping.json`
2. Upload `feedback/runs/[assignment]/3_restored/moodle_grades_final.csv` to Moodle
3. Archive the entire `feedback/runs/[assignment]/` directory for records
4. Consider sending summary statistics to students
5. Update rubric templates based on common issues observed

## Known Issues and Fixes

### Token Replacement Order
The restoration process sorts tokens by length (longest first) to avoid partial replacements. For example, REDACTED_PERSON21 is replaced before REDACTED_PERSON2 to prevent incorrect substitutions. This was fixed in the deanonymizer code.