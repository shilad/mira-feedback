"""Data models for grading review system."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from pathlib import Path
import yaml


@dataclass
class ComponentScore:
    """Individual rubric component score."""
    score: float
    max_score: float
    feedback: str


@dataclass
class Submission:
    """Student submission with grading data."""
    student_id: str
    student_name: str
    directory: Path
    total_score: float
    max_score: float
    components: Dict[str, ComponentScore]
    comment: str
    files: List[str] = field(default_factory=list)
    is_reviewed: bool = False

    @property
    def percentage(self) -> float:
        """Calculate percentage score."""
        if self.max_score == 0:
            return 0
        return (self.total_score / self.max_score) * 100

    @property
    def grade_color(self) -> str:
        """Get Bootstrap color class based on score."""
        pct = self.percentage
        if pct >= 90:
            return "success"
        elif pct >= 70:
            return "warning"
        else:
            return "danger"


class GradingData:
    """Manager for grading data persistence."""

    def __init__(self, yaml_path: Path):
        self.yaml_path = yaml_path
        self.data = self._load_yaml()
        self.submissions = self._parse_submissions()

    def _load_yaml(self) -> Dict:
        """Load grading results from YAML."""
        if self.yaml_path.exists():
            with open(self.yaml_path, 'r') as f:
                return yaml.safe_load(f)
        return {"submissions": [], "grading_summary": {}}

    def _parse_submissions(self) -> List[Submission]:
        """Parse YAML data into Submission objects."""
        submissions = []
        for sub_data in self.data.get("submissions", []):
            components = {}
            for name, comp_data in sub_data.get("components", {}).items():
                components[name] = ComponentScore(
                    score=comp_data["score"],
                    max_score=comp_data["max_score"],
                    feedback=comp_data["feedback"]
                )

            # Extract student name from directory
            student_id = sub_data["student_id"]
            student_name = student_id.replace("_assignsubmission_file", "")
            # Remove ID number if present
            if "_" in student_name:
                parts = student_name.rsplit("_", 1)
                if parts[1].isdigit():
                    student_name = parts[0]

            submission = Submission(
                student_id=student_id,
                student_name=student_name,
                directory=Path(sub_data["submission_dir"]),
                total_score=sub_data["total_score"],
                max_score=sub_data["max_score"],
                components=components,
                comment=sub_data.get("comment", ""),
                is_reviewed=sub_data.get("is_reviewed", False)
            )
            submissions.append(submission)

        return submissions

    def update_submission(self, student_id: str, updates: Dict[str, Any]) -> bool:
        """Update a submission's data."""
        for i, sub_data in enumerate(self.data["submissions"]):
            if sub_data["student_id"] == student_id:
                # Update fields
                if "total_score" in updates:
                    sub_data["total_score"] = float(updates["total_score"])
                if "comment" in updates:
                    sub_data["comment"] = updates["comment"]
                if "is_reviewed" in updates:
                    sub_data["is_reviewed"] = updates["is_reviewed"]

                # Update component feedback if provided
                if "component_feedback" in updates:
                    component_name = updates["component_name"]
                    if component_name in sub_data["components"]:
                        sub_data["components"][component_name]["feedback"] = updates["component_feedback"]

                # Save to YAML
                self._save_yaml()

                # Update in-memory submission
                self.submissions[i] = self._parse_single_submission(sub_data)
                return True
        return False

    def _parse_single_submission(self, sub_data: Dict) -> Submission:
        """Parse a single submission from YAML data."""
        components = {}
        for name, comp_data in sub_data.get("components", {}).items():
            components[name] = ComponentScore(
                score=comp_data["score"],
                max_score=comp_data["max_score"],
                feedback=comp_data["feedback"]
            )

        student_id = sub_data["student_id"]
        student_name = student_id.replace("_assignsubmission_file", "")
        if "_" in student_name:
            parts = student_name.rsplit("_", 1)
            if parts[1].isdigit():
                student_name = parts[0]

        return Submission(
            student_id=student_id,
            student_name=student_name,
            directory=Path(sub_data["submission_dir"]),
            total_score=sub_data["total_score"],
            max_score=sub_data["max_score"],
            components=components,
            comment=sub_data.get("comment", ""),
            is_reviewed=sub_data.get("is_reviewed", False)
        )

    def _save_yaml(self):
        """Save data back to YAML file."""
        with open(self.yaml_path, 'w') as f:
            yaml.safe_dump(self.data, f, default_flow_style=False, sort_keys=False)

    def get_summary_stats(self) -> Dict[str, Any]:
        """Get grading summary statistics."""
        if not self.submissions:
            return {"average": 0, "min": 0, "max": 0, "reviewed": 0, "total": 0}

        scores = [s.total_score for s in self.submissions]
        reviewed = sum(1 for s in self.submissions if s.is_reviewed)

        return {
            "average": sum(scores) / len(scores),
            "min": min(scores),
            "max": max(scores),
            "reviewed": reviewed,
            "total": len(self.submissions),
            "percentage_reviewed": (reviewed / len(self.submissions)) * 100
        }

    def export_to_csv(self, output_path: Path):
        """Export grades to Moodle CSV format."""
        import csv

        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Student", "Grade", "Feedback"])

            for submission in self.submissions:
                # Round grade to nearest 0.5
                grade = round(submission.total_score * 2) / 2
                writer.writerow([
                    submission.student_name,
                    grade,
                    submission.comment
                ])

        return output_path