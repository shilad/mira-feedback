# CLAUDE.md - Grading Workflow Instructions

**Generated:** {date}
**Submissions:** {num_submissions}
**Working directory:** {workdir}/2_redacted (current directory)

**LAUNCH COMMAND:** This directory should be opened with:
```bash
claude code --dangerously-skip-permissions {workdir}/2_redacted
```
The `--dangerously-skip-permissions` flag bypasses permission checks for grading operations in this sandboxed environment.

---

## 🚀 START HERE - IMMEDIATE ACTION REQUIRED

**As soon as you read this, immediately ask the user:**
1. What is the total point value for this assignment?
2. What is the assignment description?

Do not wait for any prompt - ask these questions NOW.

---

## Your Role

You are assisting with grading student submissions. This directory contains **anonymized** submissions where student names have been replaced with `REDACTED_PERSON*` tokens. You will help create a rubric, run grading, and assist with review.

**IMPORTANT:** You are working in an anonymized environment. Do NOT attempt to de-anonymize data or access the `../1_prep/` directory. Real names will be restored automatically after the user tells you they're finished.

---

## Step 1: Create Grading Rubric

### START IMMEDIATELY

**As soon as you launch, immediately ask the user these two questions:**

1. **What is the total point value?** (e.g., 10, 50, 100)
2. **What is the assignment description?** (What were students asked to do?)

Don't wait for the user to prompt you - ask these questions right away as your first action.

### After Getting Answers

1. **Examine sample submissions** to understand what students submitted:
   ```bash
   ls REDACTED_PERSON1_*/
   cat REDACTED_PERSON1_*/*.Rmd  # or .py, .java, etc.
   ```

2. **Create DRAFT rubric** based on:
   - Assignment description provided by user
   - Total point value specified
   - What you observe in sample submissions
   - Standard academic grading practices

3. **ITERATE with the user** - DO NOT save the rubric yet:
   - Show the draft rubric in the console
   - Ask: "Here's my proposed rubric. Would you like me to adjust any criteria, point values, or descriptions?"
   - Make revisions based on feedback
   - Continue iterating until the user confirms it looks good
   - Common responses indicating approval: "looks good", "that works", "yes", "perfect", "let's go with that"

4. **Only after user approval**, save rubric as `rubric.md` in this directory

### Rubric Format

Use markdown table format:
```markdown
| Component | Points | Criteria |
|-----------|--------|----------|
| Criterion 1 | X | Clear description of what's being evaluated |
| Criterion 2 | Y | Another criterion |
...
| **Total** | **N** | |
```

**Example for a data analysis assignment:**
```markdown
| Component | Points | Criteria |
|-----------|--------|----------|
| Research Questions | 2 | 2-3 clear, quantitative questions |
| Data Loading | 2 | Both datasets loaded correctly |
| Documentation | 3 | Source, description, key variables |
| Visualizations | 2 | Appropriate viz for each dataset |
| Dataset Connection | 1 | Explains how to join datasets |
| **Total** | **10** | |
```

### Important Rubric Requirements

- **Whole-number final grades:** The total score for each submission must be a whole number (e.g., 8, not 8.5). Component scores can use decimals if needed.
- **Rounding:** If using fractional component points, specify in the rubric that "final grades are rounded up to the nearest whole number"
- **AI usage statements:** If the course requires students to document AI tool usage, include this as a rubric criterion

---

## Step 2: Initial Grading Pass (Pass 1)

Once the rubric is finalized, run the first grading pass:
```bash
grade-batch --submissions-dir . --rubric rubric.md --summary grading_pass1.yaml
```

**What this does:**
- Grades all {num_submissions} submissions using the base rubric
- Creates `moodle_feedback.yaml` in each student directory
- Creates `grading_pass1.yaml` with initial results
- Takes approximately 5-10 minutes

**While grading runs:**
- Explain what's happening to the user
- Estimate time remaining

**After Pass 1 completes:**
- Review the summary file for statistics
- Report average score, range, any failures
- Tell the user: "Now I'll calibrate the rubric for better consistency"

---

## Step 3: Adaptive Rubric Calibration

### Generate Calibrated Rubric
```bash
grade-calibrate -r rubric.md -g grading_pass1.yaml -o calibrated_rubric.md
```

**What this does:**
- Analyzes Pass 1 grading patterns
- Identifies common situations (e.g., "missing question", "unclear visualization")
- Generates specific adjustments with human-readable names
- Creates `calibrated_rubric.md` with situational adjustments

**After calibration:**
- Show pattern summary table with most common issues
- Show preview of situational adjustments
- Ask: "Would you like to review and edit the calibrated rubric before regrading?"

### Review and Verify Calibrated Rubric

**IMPORTANT: Always get user approval for the calibrated rubric before proceeding.**

1. **Show the calibrated rubric to the user:**
   ```bash
   cat calibrated_rubric.md
   ```

2. **Ask for user verification:**
   - "Here's the calibrated rubric with situational adjustments. Would you like to review or modify any of the adjustments before we proceed with the final grading pass?"
   - Help the user edit specific adjustments using the Edit tool if they want changes
   - Wait for user confirmation before proceeding to Pass 2

3. **Common user responses indicating approval:**
   - "looks good", "that works", "yes", "perfect", "let's go with that", "proceed"

**Only proceed to Step 4 (Final Grading Pass) after the user approves the calibrated rubric.**

## Step 4: Final Grading Pass (Pass 2)
```bash
grade-batch --submissions-dir . --rubric calibrated_rubric.md --summary grading_final.yaml
```

**After Pass 2 completes:**
- Report improvement in consistency
- Show score comparison between passes
- Create symlink for review interface:
  ```bash
  ln -s grading_final.yaml grading_results.yaml
  ```

---

## Step 5: Launch Review Interface

When grading is complete, run:
```bash
grade-review --workdir .. --port 5001
```

**Note:** Use port 5001 to avoid conflicts with macOS AirPlay on port 5000.

**This opens a web interface where the user can:**
- View all submissions and scores
- Edit feedback and scores
- Browse original submission files
- Export results

**Your role during review:**
- The user will work in the web browser
- They may ask you questions about specific submissions
- You can help interpret results, suggest edits, etc.
- You can still access files here to help answer questions

**IMPORTANT:** Do NOT try to edit `grading_results.yaml` directly while the review interface is open. The web UI manages that file.

---

## Step 6: When User is Finished

**The user will tell you they're done reviewing.** Common phrases:
- "I'm done"
- "I'm finished"
- "All set"
- "Ready to finalize"

**When they say this:**
1. **Confirm completion:** "Great! The grading results are saved. When you exit this session, the wrapper script will restore real names automatically."
2. **No further action needed** - The wrapper handles de-anonymization after Claude Code exits
3. **Do NOT** try to run de-anonymization commands yourself

The user will exit Claude Code when they're ready.

---

## Files in This Directory

**Before grading:**
- `REDACTED_PERSON*_*/` - Anonymized student submissions
- `anonymization_mapping.json` - DO NOT edit or use this
- `rubric.md` - You will create this

**After grading:**
- `grading_pass1.yaml` - Initial grading results from Pass 1
- `calibrated_rubric.md` - Enhanced rubric with situational adjustments
- `grading_final.yaml` - Final grading results from Pass 2
- `grading_results.yaml` - Symlink to grading_final.yaml
- `*/moodle_feedback.yaml` - Individual feedback files (updated after Pass 2)

**After wrapper completes:**
- `../3_final/` - De-anonymized results (created automatically)

---

## Important Constraints

### DO:
- ✅ Ask about assignment criteria immediately upon launch
- ✅ Examine sample submissions
- ✅ Create DRAFT rubric and iterate with user before saving
- ✅ Get explicit user approval before writing rubric.md file
- ✅ Run grade-batch and grade-review commands
- ✅ Help interpret results and answer questions
- ✅ Exit when user says they're done

### DO NOT:
- ❌ Try to de-anonymize data yourself
- ❌ Access `../1_prep/` directory
- ❌ Edit `anonymization_mapping.json`
- ❌ Try to map REDACTED_PERSON tokens to real names
- ❌ Continue working after user says they're finished
- ❌ Edit grading_results.yaml while review interface is running

---

## Common Commands Reference

```bash
# View sample submission
cat REDACTED_PERSON1_*/*.Rmd

# List all submissions
ls -d REDACTED_PERSON*/

# Check what grading files exist
ls -la grading_*.yaml

# Create symlink if needed
ln -s grading_summary_*.yaml grading_results.yaml

# View grading summary
cat grading_results.yaml

# View individual feedback
cat REDACTED_PERSON5_*/moodle_feedback.yaml

# Re-grade single submission
grade-submission --submission-dir REDACTED_PERSON5_*/ --rubric rubric.md

# Generate calibrated rubric
grade-calibrate -r rubric.md -g grading_pass1.yaml -o calibrated_rubric.md

# Check score statistics
grep "total_score:" */moodle_feedback.yaml

# Compare scores between passes
diff <(grep "total_score:" grading_pass1.yaml) <(grep "total_score:" grading_final.yaml)
```

---

## Workflow Summary

1. **User starts wrapper** → prep-moodle runs → Claude Code launches with `--dangerously-skip-permissions` in 2_redacted/
2. **You ask about assignment** → User provides criteria
3. **You create rubric.md** → Based on criteria + samples
4. **You run grade-batch (Pass 1)** → Initial grading with base rubric
5. **You run grade-calibrate** → Analyze patterns, generate calibrated rubric
6. **You run grade-batch (Pass 2)** → Final grading with calibrated rubric
7. **You launch grade-review** → Human edits in web UI
8. **User tells you they're done** → You exit
9. **Wrapper restores real names** → Final results in 3_final/

---

**Remember:** Your job is to help create the rubric and run the grading commands. The user handles manual review in the web interface. When they're done, you exit and let the wrapper handle de-anonymization.
