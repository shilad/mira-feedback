"""Utilities for Moodle submission processing."""

import csv
import json
import re
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