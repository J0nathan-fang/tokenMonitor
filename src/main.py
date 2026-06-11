"""
TokenMonitor — AI Token Usage Monitor & Cost Analyzer.

Entry point for the application.
Usage: python -m src.main
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure src is on path when running from project root
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


def main() -> int:
    """Application entry point.

    Returns:
        Exit code: 0 for success, non-zero for errors.
    """
    from src.core.app import Application

    app = Application()

    try:
        app.initialize()
    except Exception as e:
        import logging
        logging.getLogger("token_monitor").critical(
            "Failed to initialize application: %s", e, exc_info=True
        )
        return 1

    return app.run()


if __name__ == "__main__":
    sys.exit(main())
