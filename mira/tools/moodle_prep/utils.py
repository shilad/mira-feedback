"""Utilities for Moodle submission processing."""

import csv
import json
import re
import yaml
from pathlib import Path
from typing import Dict, List, Tuple
import logging

from html_to_markdown import convert_to_markdown

LOG = logging.getLogger(__name__)


def convert_html_to_markdown(html_content: str) -> str:
    """Convert HTML content to Markdown.
    
    Args:
        html_content: HTML string to convert
        
    Returns:
        Markdown formatted string
    """
    return convert_to_markdown(html_content)


def anonymize_csv(input_path: Path, output_path: Path) -> Dict[str, str]:
    """Anonymize student names in Moodle grading CSV.
    
    Args:
        input_path: Path to input CSV file
        output_path: Path to output anonymized CSV file
        
    Returns:
        Dictionary mapping original names to anonymized IDs
    """
    name_mapping = {}
    student_counter = 1
    
    with open(input_path, 'r', encoding='utf-8-sig') as infile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames
        
        # Prepare output fieldnames (remove email if present)
        output_fieldnames = [f for f in fieldnames if f != "Email address"]
        
        rows = []
        for row in reader:
            # Get original name
            original_name = row.get("Full name", "")
            
            # Create anonymized ID if not already mapped
            if original_name and original_name not in name_mapping:
                anonymized_id = f"Student_{student_counter:03d}"
                name_mapping[original_name] = anonymized_id
                student_counter += 1
            
            # Create new row with anonymized data
            new_row = {}
            for field in output_fieldnames:
                if field == "Full name" and original_name:
                    new_row[field] = name_mapping[original_name]
                elif field != "Email address":  # Skip email field
                    new_row[field] = row.get(field, "")
            
            rows.append(new_row)
    
    # Write anonymized CSV
    with open(output_path, 'w', newline='', encoding='utf-8') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=output_fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    LOG.info(f"Anonymized {len(name_mapping)} student names in CSV")
    return name_mapping


def parse_moodle_dirname(dirname: str) -> Tuple[str, str, str]:
    """Parse Moodle submission directory name.
    
    Args:
        dirname: Directory name like "Student Name_12345_assignsubmission_file"
        
    Returns:
        Tuple of (student_name, student_id, submission_type)
    """
    # Pattern: Name_ID_assignsubmission_type
    match = re.match(r"(.+?)_(\d+)_assignsubmission_(\w+)", dirname)
    if match:
        return match.group(1), match.group(2), match.group(3)
    return dirname, "", ""


def generate_grades_csv_from_data(submissions_data: list, output_path: Path) -> Dict[str, str]:
    """Generate moodle_grades.csv from submission data.

    Args:
        submissions_data: List of submission records with name, id, type, online_text
        output_path: Path where moodle_grades.csv will be written

    Returns:
        Dictionary with statistics about what was processed
    """
    rows = []
    online_text_count = 0
    file_submission_count = 0

    for submission in submissions_data:
        row = {
            "Identifier": f"Participant {submission['id']}",
            "Full name": submission['name'],
            "Email address": "",
            "Status": "",
            "Grade": "",
            "Maximum grade": "",
            "Grade can be changed": "",
            "Last modified (grade)": "",
            "Feedback comments": "",
            "Online text": submission.get('online_text', '')
        }

        if submission['type'] == 'onlinetext':
            online_text_count += 1
        else:
            file_submission_count += 1

        rows.append(row)

    # Write CSV file
    if rows:
        fieldnames = [
            "Identifier",
            "Full name",
            "Email address",
            "Status",
            "Grade",
            "Maximum grade",
            "Grade can be changed",
            "Last modified (grade)",
            "Feedback comments",
            "Online text",
        ]
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        LOG.info(f"Generated moodle_grades.csv with {len(rows)} students")
        LOG.info(f"  Online text submissions: {online_text_count}")
        LOG.info(f"  File submissions: {file_submission_count}")
    else:
        LOG.warning("No student submissions found to generate moodle_grades.csv")

    return {
        "total_students": len(rows),
        "online_text": online_text_count,
        "file_submissions": file_submission_count
    }


def generate_grades_csv(submission_dir: Path, output_path: Path) -> Dict[str, str]:
    """Generate moodle_grades.csv from Moodle submission directory structure.

    Args:
        submission_dir: Directory containing student submissions
        output_path: Path where moodle_grades.csv will be written

    Returns:
        Dictionary with statistics about what was processed
    """
    # Use dict to track students by ID (avoids duplicates)
    students = {}
    online_text_count = 0
    file_submission_count = 0

    # Scan submission directories
    for item in sorted(submission_dir.iterdir()):
        if item.is_dir():
            student_name, student_id, submission_type = parse_moodle_dirname(item.name)

            if student_name and student_id:
                identifier = f"Participant {student_id}"

                # Only create row if we haven't seen this student yet
                if identifier not in students:
                    students[identifier] = {
                        "Identifier": identifier,
                        "Full name": student_name,
                        "Email address": "",
                        "Status": "",
                        "Grade": "",
                        "Maximum grade": "",
                        "Grade can be changed": "",
                        "Last modified (grade)": "",
                        "Feedback comments": ""
                    }

                # Count submission types
                if submission_type == "onlinetext":
                    online_text_count += 1
                else:
                    file_submission_count += 1

    # Convert to list of rows
    rows = list(students.values())

    # Write CSV file
    if rows:
        fieldnames = ["Identifier", "Full name", "Email address", "Status", "Grade",
                      "Maximum grade", "Grade can be changed", "Last modified (grade)", "Feedback comments"]
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        LOG.info(f"Generated moodle_grades.csv with {len(rows)} students")
        LOG.info(f"  Online text submissions: {online_text_count}")
        LOG.info(f"  File submissions: {file_submission_count}")
    else:
        LOG.warning("No student submissions found to generate moodle_grades.csv")

    return {
        "total_students": len(rows),
        "online_text": online_text_count,
        "file_submissions": file_submission_count
    }


def anonymize_directory_names(base_path: Path, name_mapping: Dict[str, str]) -> Dict[str, str]:
    """Anonymize student directory names based on name mapping.
    
    Args:
        base_path: Base directory containing student submissions
        name_mapping: Dictionary mapping student names to anonymized IDs
        
    Returns:
        Dictionary mapping original directory names to new names
    """
    dir_mapping = {}
    
    for item in base_path.iterdir():
        if item.is_dir():
            student_name, student_id, submission_type = parse_moodle_dirname(item.name)
            
            # Find matching anonymized name
            anonymized_name = name_mapping.get(student_name, None)
            
            if anonymized_name:
                # Create new directory name with anonymized student ID
                new_name = f"{anonymized_name}_{student_id}_assignsubmission_{submission_type}"
                dir_mapping[item.name] = new_name
            else:
                # Keep original if no mapping found
                LOG.warning(f"No mapping found for student: {student_name}")
                dir_mapping[item.name] = item.name
    
    return dir_mapping


def process_html_files(directory: Path, keep_html: bool = False) -> int:
    """Convert all HTML files in a directory tree to Markdown.
    
    Args:
        directory: Root directory to process
        keep_html: If True, keep original HTML files alongside Markdown
        
    Returns:
        Number of files converted
    """
    converted_count = 0
    
    for html_file in directory.rglob("*.html"):
        try:
            # Read HTML content
            html_content = html_file.read_text(encoding='utf-8')
            
            # Convert to markdown
            markdown_content = convert_html_to_markdown(html_content)
            
            # Write markdown file
            md_file = html_file.with_suffix('.md')
            md_file.write_text(markdown_content, encoding='utf-8')
            
            # Remove HTML file unless keeping it
            if not keep_html:
                html_file.unlink()
            
            converted_count += 1
            LOG.debug(f"Converted {html_file} to {md_file}")
            
        except Exception as e:
            LOG.error(f"Failed to convert {html_file}: {e}")
    
    LOG.info(f"Converted {converted_count} HTML files to Markdown")
    return converted_count


def update_grades_csv_from_feedback(restored_dir: Path, csv_path: Path = None) -> Dict[str, any]:
    """Update moodle_grades.csv with scores from grading_final.yaml.

    Args:
        restored_dir: Directory containing restored submissions and grading_final.yaml
        csv_path: Path to moodle_grades.csv (defaults to restored_dir/moodle_grades_final.csv)

    Returns:
        Dictionary with statistics about what was updated
    """
    if csv_path is None:
        csv_path = restored_dir / 'moodle_grades_final.csv'

    # First, check if we should copy from the template
    template_csv = restored_dir.parent / '1_prep' / 'moodle_grades.csv'

    if not csv_path.exists() and template_csv.exists():
        LOG.info(f"Copying template CSV from {template_csv} to {csv_path}")
        import shutil
        shutil.copy(template_csv, csv_path)

    if not csv_path.exists():
        raise ValueError(f"moodle_grades.csv not found at {csv_path}")

    # Read grading_final.yaml (the authoritative source after review)
    grading_final_path = restored_dir / 'grading_final.yaml'
    if not grading_final_path.exists():
        # Fall back to grading_results.yaml if it exists
        grading_final_path = restored_dir / 'grading_results.yaml'

    if not grading_final_path.exists():
        raise ValueError(f"grading_final.yaml not found at {restored_dir}")

    LOG.info(f"Reading grades from {grading_final_path}")
    with open(grading_final_path, 'r', encoding='utf-8') as f:
        grading_data = yaml.safe_load(f)

    # Create mapping of student names to grades/comments
    student_grades = {}
    for submission in grading_data.get('submissions', []):
        student_name = submission.get('student_id', '')
        if student_name:
            student_grades[student_name] = {
                'score': submission.get('total_score', ''),
                'comment': submission.get('comment', '')
            }

    # Read existing CSV
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    # Statistics
    stats = {
        'total_students': len(rows),
        'updated': 0,
        'missing_feedback': 0,
        'errors': []
    }

    # Update each row with feedback data from grading_final.yaml
    for row in rows:
        student_name = row.get("Full name", "")

        if not student_name:
            continue

        # Look up grade in grading_final.yaml
        grade_info = student_grades.get(student_name)

        if not grade_info:
            LOG.debug(f"No grade found in grading_final.yaml for {student_name}")
            stats['missing_feedback'] += 1
            continue

        try:
            # Update the row
            total_score = grade_info['score']
            comment = grade_info['comment']

            row['Grade'] = str(total_score) if total_score != '' else ''
            row['Feedback comments'] = comment

            stats['updated'] += 1
            LOG.debug(f"Updated grade for {student_name}: {total_score}")

        except Exception as e:
            LOG.error(f"Error updating grade for {student_name}: {e}")
            stats['errors'].append({
                'student': student_name,
                'error': str(e)
            })

    # Deduplicate rows based on Identifier (Participant ID)
    # Moodle exports sometimes contain duplicate rows for the same student
    seen_identifiers = set()
    unique_rows = []
    duplicates_removed = 0

    for row in rows:
        identifier = row.get("Identifier", "")
        if identifier and identifier not in seen_identifiers:
            seen_identifiers.add(identifier)
            unique_rows.append(row)
        elif identifier:
            duplicates_removed += 1
            LOG.debug(f"Removing duplicate row for {identifier}")

    if duplicates_removed > 0:
        LOG.info(f"Removed {duplicates_removed} duplicate student entries from CSV")

    # Write updated CSV with unique rows only
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(unique_rows)

    LOG.info(f"Updated moodle_grades.csv: {stats['updated']}/{stats['total_students']} students")
    if stats['missing_feedback'] > 0:
        LOG.info(f"  {stats['missing_feedback']} students without feedback")
    if stats['errors']:
        LOG.warning(f"  {len(stats['errors'])} errors occurred")

    return stats
