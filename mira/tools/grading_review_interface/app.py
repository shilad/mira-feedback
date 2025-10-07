"""Flask web application for grading review interface."""

import logging
from flask import Flask, render_template, jsonify, request, send_file
from flask_cors import CORS

from .review_interface import ReviewInterface

LOG = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Global review interface instance
review_interface = None


def create_app(interface: ReviewInterface):
    """
    Create and configure the Flask app.

    Args:
        interface: ReviewInterface instance
    """
    global review_interface
    review_interface = interface

    LOG.info("Flask app created and configured")
    return app


@app.route('/')
def index():
    """Serve the main review interface page."""
    return render_template('index.html')


@app.route('/api/submissions', methods=['GET'])
def get_submissions():
    """Get all submissions with de-anonymized data."""
    submissions = review_interface.get_submissions(deanonymize=True)
    return jsonify({
        'success': True,
        'submissions': submissions
    })


@app.route('/api/submissions/<path:student_id>', methods=['GET'])
def get_submission(student_id: str):
    """Get a specific submission by student ID."""
    submission = review_interface.get_submission_by_id(student_id, deanonymize=True)
    if submission:
        return jsonify({
            'success': True,
            'submission': submission
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Submission not found'
        }), 404


@app.route('/api/submissions/<path:student_id>', methods=['PUT'])
def update_submission(student_id: str):
    """Update a submission's feedback."""
    updates = request.json
    success = review_interface.update_submission(student_id, updates)

    if success:
        return jsonify({
            'success': True,
            'message': 'Submission updated successfully'
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Submission not found'
        }), 404


@app.route('/api/save', methods=['POST'])
def save_results():
    """Save all grading results to file."""
    backup = request.json.get('backup', True) if request.json else True
    review_interface.save_grading_results(backup=backup)

    return jsonify({
        'success': True,
        'message': 'Results saved successfully'
    })


@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    """Get summary statistics."""
    stats = review_interface.get_summary_statistics()

    # Add additional computed statistics
    submissions = review_interface.get_submissions(deanonymize=False)
    successful = [s for s in submissions if s.get('success', False)]

    if successful:
        scores = [s.get('total_score', 0) for s in successful]
        max_score = successful[0].get('max_score', 0) if successful else 0

        stats['score_distribution'] = {
            'min': min(scores) if scores else 0,
            'max': max(scores) if scores else 0,
            'median': sorted(scores)[len(scores) // 2] if scores else 0,
            'max_possible': max_score
        }

        # Count edited submissions
        edited_count = sum(1 for s in submissions if s.get('edited', False))
        stats['edited_count'] = edited_count

    return jsonify({
        'success': True,
        'statistics': stats
    })


@app.route('/api/submissions/<path:student_id>/files', methods=['GET'])
def get_submission_files(student_id: str):
    """Get list of files in a submission."""
    files = review_interface.list_submission_files(student_id)
    return jsonify({
        'success': True,
        'files': files
    })


@app.route('/api/submissions/<path:student_id>/files/<path:file_path>', methods=['GET'])
def get_submission_file_content(student_id: str, file_path: str):
    """Get content of a specific file."""
    content = review_interface.read_submission_file(student_id, file_path)
    if content is not None:
        return jsonify({
            'success': True,
            'content': content,
            'path': file_path
        })
    else:
        return jsonify({
            'success': False,
            'error': 'File not found or not readable'
        }), 404


@app.route('/api/rubric', methods=['GET'])
def get_rubric():
    """Get the grading rubric content."""
    rubric = review_interface.load_rubric()
    if rubric:
        return jsonify({
            'success': True,
            'rubric': rubric
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Rubric not found'
        }), 404


@app.route('/api/export', methods=['GET'])
def export_results():
    """Export current grading results as downloadable YAML."""
    # Save to ensure latest changes
    review_interface.save_grading_results(backup=False)

    return send_file(
        review_interface.grading_results_path,
        mimetype='application/x-yaml',
        as_attachment=True,
        download_name='grading_results_edited.yaml'
    )


def run_server(host='127.0.0.1', port=5000, debug=False):
    """
    Run the Flask development server.

    Args:
        host: Host to bind to
        port: Port to bind to
        debug: Whether to run in debug mode
    """
    app.run(host=host, port=port, debug=debug)
