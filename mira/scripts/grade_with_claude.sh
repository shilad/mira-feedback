#!/bin/bash
# Grade submissions with Claude Code
# Usage: grade-with-claude <submissions.zip> <workdir>

set -e  # Exit on error

# Check arguments
if [ "$#" -ne 2 ]; then
    echo "Usage: grade-with-claude <submissions.zip> <workdir>"
    echo ""
    echo "Example:"
    echo "  grade-with-claude submissions.zip ./fp1/"
    echo ""
    echo "This will:"
    echo "  1. Run prep-moodle to create 0_submitted, 1_prep, 2_redacted"
    echo "  2. Launch Claude Code in the redacted directory"
    exit 1
fi

ZIP_FILE="$1"
WORKDIR="$2"

# Validate zip file exists
if [ ! -f "$ZIP_FILE" ]; then
    echo "Error: Zip file not found: $ZIP_FILE"
    exit 1
fi

# Create workdir if needed
mkdir -p "$WORKDIR"

echo "=========================================="
echo "Grading with Claude Code"
echo "=========================================="
echo "Zip file: $ZIP_FILE"
echo "Work directory: $WORKDIR"
echo ""

# Step 1: Run prep-moodle
echo "Step 1: Preparing submissions..."
prep-moodle --zip "$ZIP_FILE" --workdir "$WORKDIR"

if [ $? -ne 0 ]; then
    echo "Error: prep-moodle failed"
    exit 1
fi

echo ""
echo "✓ Preparation complete!"
echo ""

# Step 2: Launch Claude Code in redacted directory
REDACTED_DIR="$WORKDIR/2_redacted"

if [ ! -d "$REDACTED_DIR" ]; then
    echo "Error: Redacted directory not found: $REDACTED_DIR"
    exit 1
fi

echo "Step 2: Launching Claude Code..."
echo "Working directory: $REDACTED_DIR"
echo ""
echo "Next steps in Claude Code:"
echo "  1. Create rubric with Claude"
echo "  2. Run: grade-batch --submissions-dir . --rubric rubric.md"
echo "  3. Run: grade-review --workdir .."
echo ""

cd "$REDACTED_DIR"
exec claude code .
