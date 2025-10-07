#!/usr/bin/env python3
"""CLI wrapper to prep submissions and launch Claude Code."""

import argparse
import subprocess
import sys
import shutil
from pathlib import Path
from datetime import datetime
import importlib.resources


def main():
    """Main entry point for grade-with-claude command."""
    parser = argparse.ArgumentParser(
        description='Prep submissions and launch Claude Code for grading',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  grade-with-claude submissions.zip ./fp1/

This will:
  1. Run prep-moodle to create 0_submitted, 1_prep, 2_redacted
  2. Launch Claude Code in the 2_redacted directory

Next steps in Claude Code:
  - Create rubric with Claude
  - Run: grade-batch --submissions-dir . --rubric rubric.md
  - Run: grade-review --workdir ..
        """
    )

    parser.add_argument(
        'zip_file',
        type=Path,
        help='Path to Moodle submissions zip file'
    )

    parser.add_argument(
        'workdir',
        type=Path,
        help='Working directory (will create 0/1/2 subdirectories)'
    )

    args = parser.parse_args()

    # Validate zip file
    if not args.zip_file.exists():
        print(f"Error: Zip file not found: {args.zip_file}", file=sys.stderr)
        sys.exit(1)

    # Create workdir if needed
    args.workdir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("  GRADING WITH CLAUDE CODE")
    print("=" * 70)
    print(f"Zip file: {args.zip_file}")
    print(f"Work directory: {args.workdir}")
    print()

    # Step 1: Run prep-moodle
    print("Step 1: Preparing submissions...")
    try:
        subprocess.run(
            ['prep-moodle', '--zip', str(args.zip_file), '--workdir', str(args.workdir)],
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"\nError: prep-moodle failed with exit code {e.returncode}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("\nError: prep-moodle command not found. Is it installed?", file=sys.stderr)
        sys.exit(1)

    print("\n✓ Preparation complete!")
    print()

    # Step 1.5: Copy README template
    redacted_dir = args.workdir / '2_redacted'
    if not redacted_dir.exists():
        print(f"Error: Redacted directory not found: {redacted_dir}", file=sys.stderr)
        sys.exit(1)

    print("Creating CLAUDE.md in grading directory...")
    copy_readme_template(redacted_dir, args.workdir)
    print("✓ CLAUDE.md created")
    print()

    # Step 2: Launch Claude Code
    print("Step 2: Launching Claude Code...")
    print(f"Working directory: {redacted_dir}")
    print()
    print("Claude will guide you through:")
    print("  1. Creating a grading rubric")
    print("  2. Running grade-batch")
    print("  3. Running grade-review for manual edits")
    print()
    print("See CLAUDE.md in the grading directory for detailed instructions.")
    print()

    try:
        subprocess.run(['claude', 'code', '--dangerously-skip-permissions', '.'], cwd=str(redacted_dir), check=True)
    except subprocess.CalledProcessError as e:
        print(f"\nError: Claude Code exited with code {e.returncode}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("\nError: 'claude' command not found. Is Claude Code installed?", file=sys.stderr)
        sys.exit(1)

    # Step 3: Restore real names
    print("\n" + "=" * 70)
    print("Step 3: Restoring real student names...")
    print("=" * 70)

    final_dir = args.workdir / '3_final'
    mapping_file = redacted_dir / 'anonymization_mapping.json'

    if not mapping_file.exists():
        print(f"Warning: Mapping file not found: {mapping_file}", file=sys.stderr)
        print("Skipping de-anonymization.")
        sys.exit(0)

    try:
        subprocess.run([
            'anonymize-dir', 'restore',
            str(redacted_dir),
            str(final_dir),
            str(mapping_file)
        ], check=True)
    except subprocess.CalledProcessError as e:
        print(f"\nError: De-anonymization failed with exit code {e.returncode}", file=sys.stderr)
        sys.exit(1)

    print("\n✓ De-anonymization complete!")
    print("\n" + "=" * 70)
    print("  GRADING COMPLETE")
    print("=" * 70)
    print(f"\nFinal results with real names: {final_dir}")
    print(f"\nKey files:")
    print(f"  - {final_dir}/grading_results.yaml")
    print(f"  - {final_dir}/STUDENT_NAME_*/moodle_feedback.yaml")
    print("\nReady to upload to Moodle!")
    print()


def copy_readme_template(dest_dir: Path, workdir: Path):
    """Copy and customize CLAUDE.md template to destination."""
    # Read template
    template_path = Path(__file__).parent / 'templates' / 'CLAUDE_TEMPLATE.md'

    if not template_path.exists():
        print(f"Warning: CLAUDE.md template not found: {template_path}", file=sys.stderr)
        return

    template_content = template_path.read_text()

    # Count submissions
    num_submissions = len([d for d in dest_dir.iterdir() if d.is_dir() and not d.name.startswith('.')])

    # Substitute variables
    claude_content = template_content.format(
        date=datetime.now().strftime('%Y-%m-%d'),
        num_submissions=num_submissions,
        workdir=str(workdir)
    )

    # Write to destination as CLAUDE.md
    claude_path = dest_dir / 'CLAUDE.md'
    claude_path.write_text(claude_content)


if __name__ == '__main__':
    main()
