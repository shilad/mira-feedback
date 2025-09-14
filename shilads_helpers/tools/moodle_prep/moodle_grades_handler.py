"""Specialized handler for anonymizing moodle_grades.csv files."""

import csv
import logging
from pathlib import Path
from typing import Dict, Tuple, Any
from io import StringIO

LOG = logging.getLogger(__name__)


class MoodleGradesHandler:
    """Handle anonymization of moodle_grades.csv files using column-based approach."""
    
    def __init__(self):
        """Initialize the handler with counters for consistent anonymization."""
        self.person_counter = 0
        self.email_counter = 0
        self.name_to_token = {}  # Map names to their assigned tokens
        self.email_to_token = {}  # Map emails to their assigned tokens
    
    def anonymize_moodle_grades(self, file_path: Path) -> Tuple[str, Dict[str, Any]]:
        """Anonymize a moodle_grades.csv file.
        
        Args:
            file_path: Path to the moodle_grades.csv file
            
        Returns:
            Tuple of (anonymized CSV content as string, mappings dictionary)
        """
        mappings = {}
        
        try:
            # Read the CSV file
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                rows = list(reader)
            
            # Process each row
            anonymized_rows = []
            for row in rows:
                new_row = row.copy()
                
                # Anonymize "Full name" column if it exists
                if "Full name" in row and row["Full name"]:
                    original_name = row["Full name"]
                    if original_name not in self.name_to_token:
                        self.person_counter += 1
                        self.name_to_token[original_name] = f"REDACTED_PERSON{self.person_counter}"
                    
                    new_row["Full name"] = self.name_to_token[original_name]
                    mappings[original_name] = self.name_to_token[original_name]
                
                # Anonymize "Email address" column if it exists
                if "Email address" in row and row["Email address"]:
                    original_email = row["Email address"]
                    if original_email not in self.email_to_token:
                        self.email_counter += 1
                        self.email_to_token[original_email] = f"REDACTED_EMAIL{self.email_counter}"
                    
                    new_row["Email address"] = self.email_to_token[original_email]
                    mappings[original_email] = self.email_to_token[original_email]
                
                anonymized_rows.append(new_row)
            
            # Write to string buffer
            output = StringIO()
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(anonymized_rows)
            
            anonymized_content = output.getvalue()
            
            LOG.info(f"Anonymized moodle_grades.csv: {self.person_counter} names, {self.email_counter} emails")
            
            return anonymized_content, mappings
            
        except Exception as e:
            LOG.error(f"Failed to anonymize moodle_grades.csv: {e}")
            raise
    
    def reset(self):
        """Reset the handler's state for a new anonymization session."""
        self.person_counter = 0
        self.email_counter = 0
        self.name_to_token.clear()
        self.email_to_token.clear()