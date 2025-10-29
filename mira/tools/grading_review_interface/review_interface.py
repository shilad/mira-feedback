"""Core business logic for the grading review interface."""

import json
import yaml
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import asyncio

from mira.libs.llm import create_agent
from mira.libs.config_loader import load_all_configs

LOG = logging.getLogger(__name__)


class ReviewInterface:
    """Manages grading feedback review, editing, and de-anonymization."""

    def __init__(self, redacted_dir: Path, prep_dir: Path,
                 grading_results_path: Optional[Path] = None,
                 anonymization_mapping_path: Optional[Path] = None):
        """
        Initialize the review interface.

        Args:
            redacted_dir: Path to 2_redacted directory with anonymized submissions
            prep_dir: Path to 1_prep directory with original submissions
            grading_results_path: Optional path to grading_results.yaml
            anonymization_mapping_path: Optional path to anonymization_mapping.json
        """
        self.redacted_dir = Path(redacted_dir)
        self.prep_dir = Path(prep_dir)

        # Default paths if not provided
        if grading_results_path is None:
            grading_results_path = self.redacted_dir / "grading_results.yaml"
        if anonymization_mapping_path is None:
            anonymization_mapping_path = self.redacted_dir / "anonymization_mapping.json"

        self.grading_results_path = Path(grading_results_path)
        self.anonymization_mapping_path = Path(anonymization_mapping_path)

        # Load data
        self.anonymization_mapping = self._load_anonymization_mapping()
        self.reverse_mapping = {v: k for k, v in self.anonymization_mapping.items()}
        self.grading_data = self._load_grading_results()

        LOG.info(f"ReviewInterface initialized with {len(self.grading_data.get('submissions', []))} submissions")

    def _load_anonymization_mapping(self) -> Dict[str, str]:
        """Load anonymization mapping from JSON file."""
        if not self.anonymization_mapping_path.exists():
            LOG.warning(f"Anonymization mapping not found: {self.anonymization_mapping_path}")
            return {}

        with open(self.anonymization_mapping_path, 'r') as f:
            data = json.load(f)
            return data.get('mappings', {})

    def _load_grading_results(self) -> Dict[str, Any]:
        """Load grading results from YAML file."""
        if not self.grading_results_path.exists():
            LOG.warning(f"Grading results not found: {self.grading_results_path}")
            return {'grading_summary': {}, 'submissions': []}

        with open(self.grading_results_path, 'r') as f:
            return yaml.safe_load(f)

    def save_grading_results(self, backup: bool = True) -> None:
        """
        Save grading results back to YAML file.

        Args:
            backup: Whether to create a backup before saving
        """
        if backup and self.grading_results_path.exists():
            backup_path = self.grading_results_path.with_suffix(
                f'.{datetime.now().strftime("%Y%m%d_%H%M%S")}.yaml.bak'
            )
            shutil.copy(self.grading_results_path, backup_path)
            LOG.info(f"Created backup: {backup_path}")

        with open(self.grading_results_path, 'w') as f:
            yaml.dump(self.grading_data, f, default_flow_style=False, sort_keys=False)

        LOG.info(f"Saved grading results to {self.grading_results_path}")

    def deanonymize_text(self, text: str) -> str:
        """Replace anonymized tokens with original names in text."""
        result = text
        # Sort tokens by length (longest first) to avoid substring replacement issues
        # e.g., replace REDACTED_PERSON10 before REDACTED_PERSON1
        sorted_tokens = sorted(self.anonymization_mapping.items(),
                              key=lambda x: len(x[0]), reverse=True)
        for token, original in sorted_tokens:
            result = result.replace(token, original)
        return result

    def anonymize_text(self, text: str) -> str:
        """Replace original names with anonymized tokens in text."""
        result = text
        # Sort by length (longest first) to avoid substring replacement issues
        sorted_mappings = sorted(self.reverse_mapping.items(),
                                key=lambda x: len(x[0]), reverse=True)
        for original, token in sorted_mappings:
            result = result.replace(original, token)
        return result

    def get_submissions(self, deanonymize: bool = True) -> List[Dict[str, Any]]:
        """
        Get all submissions with optional de-anonymization.

        Args:
            deanonymize: Whether to de-anonymize student IDs and paths

        Returns:
            List of submission dictionaries
        """
        submissions = self.grading_data.get('submissions', [])

        if deanonymize:
            deanonymized = []
            for submission in submissions:
                sub_copy = submission.copy()
                sub_copy['student_id'] = self.deanonymize_text(sub_copy.get('student_id', ''))
                sub_copy['submission_dir'] = self.deanonymize_text(sub_copy.get('submission_dir', ''))
                deanonymized.append(sub_copy)
            return deanonymized

        return submissions

    def get_submission_by_id(self, student_id: str, deanonymize: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get a specific submission by student ID.

        Args:
            student_id: Student ID (can be anonymized or de-anonymized)
            deanonymize: Whether to de-anonymize the result

        Returns:
            Submission dictionary or None if not found
        """
        # Try both anonymized and de-anonymized versions
        anonymized_id = self.anonymize_text(student_id)

        for submission in self.grading_data.get('submissions', []):
            sub_id = submission.get('student_id', '')
            if sub_id == student_id or sub_id == anonymized_id:
                if deanonymize:
                    sub_copy = submission.copy()
                    sub_copy['student_id'] = self.deanonymize_text(sub_copy.get('student_id', ''))
                    sub_copy['submission_dir'] = self.deanonymize_text(sub_copy.get('submission_dir', ''))
                    return sub_copy
                return submission.copy()

        return None

    def update_submission(self, student_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update a submission's feedback.

        Args:
            student_id: Student ID (can be anonymized or de-anonymized)
            updates: Dictionary of fields to update

        Returns:
            True if successful, False if submission not found
        """
        anonymized_id = self.anonymize_text(student_id)

        for i, submission in enumerate(self.grading_data.get('submissions', [])):
            sub_id = submission.get('student_id', '')
            if sub_id == student_id or sub_id == anonymized_id:
                # Normalize comment fields that may come from the UI
                if 'overall_comment' in updates and 'comment' not in updates:
                    updates['comment'] = updates['overall_comment']

                # Update fields
                for key, value in updates.items():
                    if key in ['total_score', 'comment', 'components']:
                        submission[key] = value

                # Mark as edited
                submission['edited'] = True
                submission['edited_timestamp'] = datetime.now().isoformat()

                # Recalculate summary statistics
                self._update_summary_statistics()

                LOG.info(f"Updated submission: {student_id}")
                return True

        return False

    def _update_summary_statistics(self) -> None:
        """Recalculate summary statistics after edits."""
        submissions = self.grading_data.get('submissions', [])
        successful = [s for s in submissions if s.get('success', False)]
        failed = [s for s in submissions if not s.get('success', False)]

        if successful:
            avg_score = sum(s.get('total_score', 0) for s in successful) / len(successful)
        else:
            avg_score = 0

        summary = self.grading_data.get('grading_summary', {})
        summary.update({
            'total_submissions': len(submissions),
            'successful': len(successful),
            'failed': len(failed),
            'average_score': avg_score,
            'last_updated': datetime.now().isoformat()
        })

        self.grading_data['grading_summary'] = summary

    def get_summary_statistics(self) -> Dict[str, Any]:
        """Get summary statistics for all submissions."""
        return self.grading_data.get('grading_summary', {})

    def get_original_submission_path(self, student_id: str) -> Optional[Path]:
        """
        Get the path to the original (de-anonymized) submission directory.

        Args:
            student_id: Student ID (de-anonymized)

        Returns:
            Path to submission directory in 1_prep, or None if not found
        """
        # Search for matching directory in prep_dir
        for item in self.prep_dir.iterdir():
            if item.is_dir() and student_id in item.name:
                return item

        return None

    def list_submission_files(self, student_id: str) -> List[Dict[str, Any]]:
        """
        List all files in a student's original submission.

        Args:
            student_id: Student ID (de-anonymized)

        Returns:
            List of file info dictionaries with path, name, size, type
        """
        submission_path = self.get_original_submission_path(student_id)
        if not submission_path:
            return []

        files = []
        for file_path in submission_path.rglob('*'):
            if file_path.is_file() and not file_path.name.startswith('.'):
                relative_path = file_path.relative_to(submission_path)
                files.append({
                    'path': str(relative_path),
                    'full_path': str(file_path),
                    'name': file_path.name,
                    'size': file_path.stat().st_size,
                    'extension': file_path.suffix
                })

        # Sort by path
        files.sort(key=lambda f: f['path'])
        return files

    def read_submission_file(self, student_id: str, file_path: str) -> Optional[str]:
        """
        Read a file from a student's original submission.

        Args:
            student_id: Student ID (de-anonymized)
            file_path: Relative path to file within submission

        Returns:
            File contents as string, or None if not found/not readable
        """
        submission_path = self.get_original_submission_path(student_id)
        if not submission_path:
            return None

        full_path = submission_path / file_path
        if not full_path.exists() or not full_path.is_file():
            return None

        try:
            # Try to read as text
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.read()
        except (UnicodeDecodeError, IOError):
            return None

    def get_rubric_path(self) -> Optional[Path]:
        """Find the rubric file in the redacted directory or parent directory."""
        # First check for calibrated rubric in the redacted directory
        calibrated_path = self.redacted_dir / 'calibrated_rubric.md'
        if calibrated_path.exists():
            return calibrated_path

        # Then check for calibrated rubric in parent directory
        parent = self.redacted_dir.parent
        calibrated_path_parent = parent / 'calibrated_rubric.md'
        if calibrated_path_parent.exists():
            return calibrated_path_parent

        # Fall back to regular rubric patterns in redacted directory
        for pattern in ['rubric*.md', '*rubric*.md', 'RUBRIC*.md']:
            matches = list(self.redacted_dir.glob(pattern))
            if matches and 'calibrated' not in matches[0].name:
                return matches[0]

        # Finally check parent directory for regular rubric
        for pattern in ['rubric*.md', '*rubric*.md', 'RUBRIC*.md']:
            matches = list(parent.glob(pattern))
            if matches and 'calibrated' not in matches[0].name:
                return matches[0]

        return None

    def load_rubric(self) -> Optional[str]:
        """Load the rubric content."""
        rubric_path = self.get_rubric_path()
        if rubric_path and rubric_path.exists():
            with open(rubric_path, 'r') as f:
                return f.read()
        return None

    def regenerate_comment(self, student_id: str, components: Dict[str, Any]) -> str:
        """
        Regenerate the overall comment using LLM based on current component scores/adjustments.

        Args:
            student_id: Student identifier
            components: Dict of component name -> {score, max_score, adjustments}

        Returns:
            Generated overall comment string
        """
        # Build summary of components for LLM
        component_summary = []
        for name, comp in components.items():
            score = comp.get('score', 0)
            max_score = comp.get('max_score', 1)
            adjustments = comp.get('adjustments', [])

            status = "full credit" if score == max_score else f"{score}/{max_score}"
            component_summary.append(f"- {name}: {status}")

            if adjustments:
                for adj in adjustments:
                    desc = adj.get('description', '')
                    impact = adj.get('score_impact', 0)
                    if desc:
                        component_summary.append(f"  └─ {desc} ({impact:+.2f})")

        components_text = "\n".join(component_summary)

        prompt = f"""Based on this student's component scores and adjustments, write a brief (2-3 sentences) overall feedback comment.

Focus on:
1. What they did well
2. Key areas for improvement (from adjustments)
3. Encouraging, constructive tone

COMPONENT SCORES:
{components_text}

Write only the overall comment, nothing else:"""

        # Create LLM agent using same config as grader
        config = load_all_configs()
        agent = create_agent(
            configs=config,
            model=None,  # Use config default (same as grader)
            settings_dict=None,  # Use config default (same as grader)
            system_prompt="You are a helpful teaching assistant providing constructive feedback to students."
        )

        # Run synchronously
        result = asyncio.run(agent.run(prompt))

        # Extract response
        if hasattr(result, 'output'):
            comment = str(result.output).strip()
        elif hasattr(result, 'data'):
            comment = str(result.data).strip()
        else:
            comment = str(result).strip()

        return comment
