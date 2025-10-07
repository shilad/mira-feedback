"""Flask application for grading review interface."""

from flask import Flask, render_template, request, jsonify, send_file, Response
from pathlib import Path
import yaml
import mimetypes
import os
from typing import Optional

from .models import GradingData


app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key-change-in-production'

# Global state
grading_data: Optional[GradingData] = None
submissions_dir: Optional[Path] = None


def init_app(yaml_path: str, subs_dir: str):
    """Initialize the app with data paths."""
    global grading_data, submissions_dir
    grading_data = GradingData(Path(yaml_path))
    submissions_dir = Path(subs_dir)


@app.route('/')
def dashboard():
    """Main dashboard showing all submissions."""
    if grading_data is None:
        return "Application not initialized", 500

    stats = grading_data.get_summary_stats()
    return render_template('dashboard.html',
                         submissions=grading_data.submissions,
                         stats=stats)


@app.route('/update/<student_id>', methods=['POST'])
def update_submission(student_id):
    """Update submission grade/feedback via AJAX."""
    if grading_data is None:
        return jsonify({"error": "Application not initialized"}), 500

    data = request.json
    success = grading_data.update_submission(student_id, data)

    if success:
        return jsonify({"status": "success"})
    else:
        return jsonify({"error": "Submission not found"}), 404


@app.route('/submission/<student_id>')
def view_submission(student_id):
    """View files for a specific submission."""
    if grading_data is None or submissions_dir is None:
        return "Application not initialized", 500

    # Find submission
    submission = None
    for sub in grading_data.submissions:
        if sub.student_id == student_id:
            submission = sub
            break

    if not submission:
        return "Submission not found", 404

    # Get list of files
    sub_path = submissions_dir / submission.directory.name
    if not sub_path.exists():
        return f"Submission directory not found: {sub_path}", 404

    files = []
    for file_path in sub_path.iterdir():
        if file_path.is_file() and not file_path.name.startswith('.'):
            files.append({
                'name': file_path.name,
                'size': file_path.stat().st_size,
                'extension': file_path.suffix.lower()
            })

    return render_template('viewer.html',
                         submission=submission,
                         files=files)


@app.route('/submission/<student_id>/file/<filename>')
def get_file(student_id, filename):
    """Serve a specific file from submission."""
    if submissions_dir is None:
        return "Application not initialized", 500

    # Find submission directory
    submission = None
    for sub in grading_data.submissions:
        if sub.student_id == student_id:
            submission = sub
            break

    if not submission:
        return "Submission not found", 404

    # Get file path
    file_path = submissions_dir / submission.directory.name / filename
    if not file_path.exists():
        return "File not found", 404

    # Determine MIME type
    mime_type, _ = mimetypes.guess_type(str(file_path))
    if mime_type is None:
        mime_type = 'text/plain'

    # Read file content
    try:
        if mime_type.startswith('text') or mime_type in ['application/javascript', 'application/json']:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            return Response(content, mimetype=mime_type)
        else:
            # Binary files (PDFs, images, etc.)
            return send_file(file_path, mimetype=mime_type)
    except Exception as e:
        return f"Error reading file: {e}", 500


@app.route('/export_csv', methods=['POST'])
def export_csv():
    """Export grades to CSV format."""
    if grading_data is None:
        return jsonify({"error": "Application not initialized"}), 500

    output_path = Path("moodle_grades_export.csv")
    grading_data.export_to_csv(output_path)

    return send_file(output_path,
                    mimetype='text/csv',
                    as_attachment=True,
                    download_name='moodle_grades.csv')


@app.route('/mark_reviewed/<student_id>', methods=['POST'])
def mark_reviewed(student_id):
    """Mark a submission as reviewed."""
    if grading_data is None:
        return jsonify({"error": "Application not initialized"}), 500

    data = request.json
    data['is_reviewed'] = True
    success = grading_data.update_submission(student_id, data)

    if success:
        return jsonify({"status": "success"})
    else:
        return jsonify({"error": "Submission not found"}), 404