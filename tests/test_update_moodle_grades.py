"""Tests for update_grades_csv_from_feedback functionality."""

import csv
import tempfile
import yaml
from pathlib import Path

import pytest

from mira.tools.moodle_prep.utils import update_grades_csv_from_feedback


def test_update_grades_csv_from_feedback():
    """Test updating moodle_grades.csv with scores from feedback.yaml files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create directory structure
        restored_dir = tmpdir / '3_restored'
        restored_dir.mkdir()

        prep_dir = tmpdir / '1_prep'
        prep_dir.mkdir()

        # Create template CSV
        template_csv = prep_dir / 'moodle_grades.csv'
        with open(template_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "Identifier", "Full name", "Email address", "Status", "Grade",
                "Maximum grade", "Grade can be changed", "Last modified (grade)", "Feedback comments"
            ])
            writer.writeheader()
            writer.writerow({
                "Identifier": "Participant 12345",
                "Full name": "John Doe",
                "Email address": "",
                "Status": "",
                "Grade": "",
                "Maximum grade": "",
                "Grade can be changed": "",
                "Last modified (grade)": "",
                "Feedback comments": ""
            })
            writer.writerow({
                "Identifier": "Participant 67890",
                "Full name": "Jane Smith",
                "Email address": "",
                "Status": "",
                "Grade": "",
                "Maximum grade": "",
                "Grade can be changed": "",
                "Last modified (grade)": "",
                "Feedback comments": ""
            })

        # Create submission directories with feedback.yaml
        john_dir = restored_dir / 'John Doe_12345_assignsubmission_file'
        john_dir.mkdir()

        feedback_john = {
            'total_score': 85.0,
            'max_score': 100.0,
            'comment': 'Great work!',
            'components': {}
        }
        with open(john_dir / 'feedback.yaml', 'w') as f:
            yaml.dump(feedback_john, f)

        jane_dir = restored_dir / 'Jane Smith_67890_assignsubmission_file'
        jane_dir.mkdir()

        feedback_jane = {
            'total_score': 92.5,
            'max_score': 100.0,
            'comment': 'Excellent submission!',
            'components': {}
        }
        with open(jane_dir / 'feedback.yaml', 'w') as f:
            yaml.dump(feedback_jane, f)

        # Run the update
        stats = update_grades_csv_from_feedback(restored_dir)

        # Check statistics
        assert stats['total_students'] == 2
        assert stats['updated'] == 2
        assert stats['missing_feedback'] == 0
        assert len(stats['errors']) == 0

        # Check the updated CSV
        csv_path = restored_dir / 'moodle_grades_final.csv'
        assert csv_path.exists()

        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 2

        # Check John's row
        john_row = next(r for r in rows if r['Full name'] == 'John Doe')
        assert john_row['Grade'] == '85.0'
        assert john_row['Feedback comments'] == 'Great work!'

        # Check Jane's row
        jane_row = next(r for r in rows if r['Full name'] == 'Jane Smith')
        assert jane_row['Grade'] == '92.5'
        assert jane_row['Feedback comments'] == 'Excellent submission!'


def test_update_grades_csv_missing_feedback():
    """Test handling of missing feedback files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create directory structure
        restored_dir = tmpdir / '3_restored'
        restored_dir.mkdir()

        prep_dir = tmpdir / '1_prep'
        prep_dir.mkdir()

        # Create template CSV
        template_csv = prep_dir / 'moodle_grades.csv'
        with open(template_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "Identifier", "Full name", "Email address", "Status", "Grade",
                "Maximum grade", "Grade can be changed", "Last modified (grade)", "Feedback comments"
            ])
            writer.writeheader()
            writer.writerow({
                "Identifier": "Participant 12345",
                "Full name": "John Doe",
                "Email address": "",
                "Status": "",
                "Grade": "",
                "Maximum grade": "",
                "Grade can be changed": "",
                "Last modified (grade)": "",
                "Feedback comments": ""
            })
            writer.writerow({
                "Identifier": "Participant 67890",
                "Full name": "Jane Smith",
                "Email address": "",
                "Status": "",
                "Grade": "",
                "Maximum grade": "",
                "Grade can be changed": "",
                "Last modified (grade)": "",
                "Feedback comments": ""
            })

        # Create only one submission directory with feedback
        john_dir = restored_dir / 'John Doe_12345_assignsubmission_file'
        john_dir.mkdir()

        feedback_john = {
            'total_score': 85.0,
            'max_score': 100.0,
            'comment': 'Great work!',
            'components': {}
        }
        with open(john_dir / 'feedback.yaml', 'w') as f:
            yaml.dump(feedback_john, f)

        # Jane has no directory (didn't submit)

        # Run the update
        stats = update_grades_csv_from_feedback(restored_dir)

        # Check statistics
        assert stats['total_students'] == 2
        assert stats['updated'] == 1
        assert stats['missing_feedback'] == 1
        assert len(stats['errors']) == 0

        # Check the updated CSV
        csv_path = restored_dir / 'moodle_grades_final.csv'
        assert csv_path.exists()

        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Check John's row is updated
        john_row = next(r for r in rows if r['Full name'] == 'John Doe')
        assert john_row['Grade'] == '85.0'

        # Check Jane's row is empty
        jane_row = next(r for r in rows if r['Full name'] == 'Jane Smith')
        assert jane_row['Grade'] == ''


def test_update_grades_csv_existing_final_csv():
    """Test updating an existing moodle_grades_final.csv file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create directory structure
        restored_dir = tmpdir / '3_restored'
        restored_dir.mkdir()

        # Create existing CSV with old grades
        existing_csv = restored_dir / 'moodle_grades_final.csv'
        with open(existing_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "Identifier", "Full name", "Email address", "Status", "Grade",
                "Maximum grade", "Grade can be changed", "Last modified (grade)", "Feedback comments"
            ])
            writer.writeheader()
            writer.writerow({
                "Identifier": "Participant 12345",
                "Full name": "John Doe",
                "Email address": "",
                "Status": "",
                "Grade": "70",
                "Maximum grade": "",
                "Grade can be changed": "",
                "Last modified (grade)": "",
                "Feedback comments": "Old feedback"
            })

        # Create submission directory with new feedback
        john_dir = restored_dir / 'John Doe_12345_assignsubmission_file'
        john_dir.mkdir()

        feedback_john = {
            'total_score': 85.0,
            'max_score': 100.0,
            'comment': 'Updated feedback!',
            'components': {}
        }
        with open(john_dir / 'feedback.yaml', 'w') as f:
            yaml.dump(feedback_john, f)

        # Run the update
        stats = update_grades_csv_from_feedback(restored_dir)

        # Check that old grades were replaced
        with open(existing_csv, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        john_row = rows[0]
        assert john_row['Grade'] == '85.0'
        assert john_row['Feedback comments'] == 'Updated feedback!'
