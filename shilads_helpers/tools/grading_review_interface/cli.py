"""CLI for launching the grading review interface."""

import argparse
import logging
import webbrowser
from pathlib import Path
from threading import Timer

from .app import create_app, run_server
from .review_interface import ReviewInterface

LOG = logging.getLogger(__name__)


def open_browser(url, delay=1.5):
    """Open browser after a delay."""
    def _open():
        webbrowser.open(url)
    Timer(delay, _open).start()


def main():
    """Main CLI entry point for grading review interface."""
    parser = argparse.ArgumentParser(
        description='Launch web interface for reviewing and editing AI-generated grading feedback',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  # Launch review interface
  grade-review --workdir ./fp1/

  # Opens browser to http://localhost:5000
  # Shows submissions from ./fp1/2_redacted/
  # Allows editing feedback and scores
        """
    )

    parser.add_argument(
        '--workdir',
        type=Path,
        required=True,
        help='Working directory containing 1_prep and 2_redacted subdirectories'
    )

    parser.add_argument(
        '--host',
        default='127.0.0.1',
        help='Host to bind to (default: 127.0.0.1)'
    )

    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help='Port to bind to (default: 5000)'
    )

    parser.add_argument(
        '--no-browser',
        action='store_true',
        help='Do not automatically open browser'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Run in debug mode'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    # Set up logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Validate workdir
    workdir = args.workdir.resolve()
    if not workdir.exists():
        parser.error(f"Working directory not found: {workdir}")

    prep_dir = workdir / '1_prep'
    redacted_dir = workdir / '2_redacted'

    if not prep_dir.exists():
        parser.error(f"Prep directory not found: {prep_dir}")
    if not redacted_dir.exists():
        parser.error(f"Redacted directory not found: {redacted_dir}")

    # Create review interface
    LOG.info("Initializing grading review interface...")
    interface = ReviewInterface(
        redacted_dir=redacted_dir,
        prep_dir=prep_dir
    )

    # Create Flask app
    app = create_app(interface)

    # Open browser
    url = f"http://{args.host}:{args.port}"
    if not args.no_browser:
        LOG.info(f"Opening browser at {url}")
        open_browser(url)
    else:
        LOG.info(f"Server will be available at {url}")

    # Run server
    LOG.info(f"Starting server on {args.host}:{args.port}")
    print("\n" + "="*70)
    print("  GRADING REVIEW INTERFACE")
    print("="*70)
    print(f"\n  URL: {url}")
    print(f"  Working directory: {workdir}")
    print("\n  Features:")
    print("    - View and edit AI-generated feedback")
    print("    - Browse original submission files")
    print("    - Track statistics and progress")
    print("    - Export edited results")
    print("\n  Press Ctrl+C to stop the server")
    print("="*70 + "\n")

    try:
        run_server(host=args.host, port=args.port, debug=args.debug)
    except KeyboardInterrupt:
        print("\n\nShutting down server...")
        LOG.info("Server stopped")


if __name__ == '__main__':
    main()
