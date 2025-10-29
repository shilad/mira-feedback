"""Parser for extracting grading criteria from markdown rubric files."""

import re
from pathlib import Path
from typing import List, Optional
from .models import RubricCriterion


class RubricParser:
    """Parse markdown rubrics to extract grading criteria."""

    def parse_file(self, rubric_path: Path) -> List[RubricCriterion]:
        """Parse a rubric markdown file."""
        try:
            content = rubric_path.read_text(encoding='utf-8')
            return self.parse(content)
        except Exception as e:
            raise ValueError(f"Could not read rubric file: {e}")

    def parse(self, content: str) -> List[RubricCriterion]:
        """
        Parse markdown content to extract rubric criteria.

        Supports multiple formats:
        1. Tables with | Component | Points | Criteria/Description |
        2. Bullet lists with - Component (X points): Description
        3. Headers with ## Component (X points) followed by description
        """
        criteria = []

        # Try table format first
        table_criteria = self._parse_table_format(content)
        if table_criteria:
            return table_criteria

        # Try bullet list format
        list_criteria = self._parse_list_format(content)
        if list_criteria:
            return list_criteria

        # Try header format
        header_criteria = self._parse_header_format(content)
        if header_criteria:
            return header_criteria

        raise ValueError(
            "Could not parse rubric. Ensure it contains a table with Component|Points|Criteria "
            "or a bullet list with '- Component (X points): Description' format"
        )

    def _parse_table_format(self, content: str) -> List[RubricCriterion]:
        """Parse table format rubrics."""
        criteria = []
        lines = content.split('\n')
        in_table = False
        header_indices = {}

        for line in lines:
            line = line.strip()

            # Stop parsing if we hit the Situational Adjustments section
            if 'situational adjustment' in line.lower():
                break

            # Skip empty lines and separators
            if not line or line.startswith('|-') or all(c in '|-' for c in line):
                continue

            # Check if this is a table row
            if '|' in line:
                parts = [p.strip() for p in line.split('|')]
                parts = [p for p in parts if p]  # Remove empty parts

                # Detect header row
                if not in_table:
                    for i, part in enumerate(parts):
                        part_lower = part.lower()
                        if any(keyword in part_lower for keyword in ['component', 'criterion', 'element', 'category']):
                            header_indices['name'] = i
                        elif any(keyword in part_lower for keyword in ['point', 'score', 'max']):
                            header_indices['points'] = i
                        elif any(keyword in part_lower for keyword in ['criteria', 'description', 'requirement']):
                            header_indices['criteria'] = i

                    if 'name' in header_indices and 'points' in header_indices:
                        in_table = True
                    continue

                # Parse data row
                if in_table and len(parts) > max(header_indices.values()):
                    # Try to extract points
                    points_text = parts[header_indices['points']]
                    points_match = re.search(r'(\d+(?:\.\d+)?)', points_text)

                    if points_match:
                        name = parts[header_indices['name']].replace('**', '').replace('*', '').strip()

                        # Skip total rows
                        if name.lower() in ['total', 'sum', 'max', 'maximum']:
                            continue

                        points = float(points_match.group(1))

                        # Get criteria if available
                        if 'criteria' in header_indices and header_indices['criteria'] < len(parts):
                            criteria_text = parts[header_indices['criteria']]
                        else:
                            criteria_text = f"Evaluation of {name}"

                        criteria.append(RubricCriterion(
                            name=name,
                            max_points=points,
                            criteria=criteria_text
                        ))

        return criteria

    def _parse_list_format(self, content: str) -> List[RubricCriterion]:
        """Parse bullet list format rubrics."""
        criteria = []

        # Pattern for bullet points with points
        # Matches: - Component (X points): Description
        # Or: - Component [X points]: Description
        # Or: - Component - X points - Description
        pattern = r'[-*]\s+([^(\[]+?)\s*[\(\[]?(\d+(?:\.\d+)?)\s*points?[\)\]]?\s*[:|-]\s*(.+)'

        for match in re.finditer(pattern, content, re.MULTILINE):
            name = match.group(1).strip()
            points = float(match.group(2))
            criteria_text = match.group(3).strip()

            criteria.append(RubricCriterion(
                name=name,
                max_points=points,
                criteria=criteria_text
            ))

        return criteria

    def _parse_header_format(self, content: str) -> List[RubricCriterion]:
        """Parse header-based format rubrics."""
        criteria = []

        # Pattern for headers with points
        # Matches: ## Component (X points)
        # Or: ### Component [X points]
        pattern = r'^#{2,3}\s+([^(\[]+?)\s*[\(\[]?(\d+(?:\.\d+)?)\s*points?[\)\]]?\s*$'

        lines = content.split('\n')
        for i, line in enumerate(lines):
            # Stop parsing if we hit the Situational Adjustments section
            if 'situational adjustment' in line.lower():
                break

            match = re.match(pattern, line.strip())
            if match:
                name = match.group(1).strip()
                points = float(match.group(2))

                # Look for description in the next non-empty lines
                criteria_text = ""
                for j in range(i + 1, min(i + 5, len(lines))):
                    next_line = lines[j].strip()
                    if next_line and not next_line.startswith('#'):
                        criteria_text += next_line + " "
                    elif next_line.startswith('#'):
                        break

                if not criteria_text:
                    criteria_text = f"Evaluation of {name}"

                criteria.append(RubricCriterion(
                    name=name,
                    max_points=points,
                    criteria=criteria_text.strip()
                ))

        return criteria