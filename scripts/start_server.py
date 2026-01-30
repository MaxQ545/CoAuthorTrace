#!/usr/bin/env python3
"""
Start the API server.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.models import init_database
from src.api.main import run_server


def main():
    """Start server."""
    # Parse arguments
    host = "0.0.0.0"
    port = 8000

    for arg in sys.argv[1:]:
        if arg.startswith("--host="):
            host = arg.split("=")[1]
        elif arg.startswith("--port="):
            port = int(arg.split("=")[1])

    # Initialize database
    init_database()

    # Start server
    print(f"Starting server at http://{host}:{port}")
    run_server(host=host, port=port)


if __name__ == "__main__":
    main()
