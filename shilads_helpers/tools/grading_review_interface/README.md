# Grading Review Interface

A human-in-the-loop web interface for reviewing and editing AI-generated grading feedback.

## Features

- **De-anonymized Display**: View real student names and data in the interface
- **Interactive Feedback Editing**: Edit scores and feedback with live updates
- **File Viewer**: Browse and view original submission files with syntax highlighting
- **Statistics Dashboard**: Track grading progress and score distribution
- **Rubric Display**: Always-accessible rubric reference
- **Auto-save**: Changes are tracked and can be saved with backups
- **Export**: Download edited grading results as YAML

## Usage

```bash
# Launch the review interface
grade-review --redacted-dir path/to/2_redacted --prep-dir path/to/1_prep

# Example with real data
grade-review --redacted-dir feedback/runs/fp1/2_redacted --prep-dir feedback/runs/fp1/1_prep

# Custom port
grade-review --redacted-dir hw/2_redacted --prep-dir hw/1_prep --port 8080

# Headless mode (no auto-browser)
grade-review --redacted-dir hw/2_redacted --prep-dir hw/1_prep --no-browser
```

## Interface Layout

### Left Sidebar
- List of all submissions
- Search and filter controls
- Score preview

### Main Editor
- **Feedback Tab**: Edit overall comments and component scores
- **Files Tab**: View original submission files
- **Rubric Tab**: Reference grading rubric

### Right Sidebar
- Summary statistics
- Quick actions
- Progress tracking

## Data Safety

- **Backup on Save**: Automatic backups created before saving changes
- **Anonymization Aware**: Displays de-anonymized data while preserving anonymized data structure
- **Tracks Edits**: Marks submissions as edited with timestamps

## Architecture

- **Backend**: Flask REST API (`app.py`)
- **Core Logic**: `ReviewInterface` class for data management
- **Frontend**: Single-page HTML/CSS/JS application
- **No Database**: Works directly with YAML and JSON files

## Files

- `review_interface.py` - Core business logic
- `app.py` - Flask web server
- `cli.py` - Command-line interface
- `templates/index.html` - Web interface
- `static/style.css` - Styling
- `static/app.js` - Frontend logic
