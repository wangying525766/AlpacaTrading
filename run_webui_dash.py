#!/usr/bin/env python
"""
run_webui_dash.py - Run the Dash-based web UI for TradingAgents

Cloud-friendly:
- Uses $PORT if provided (Render/Heroku/Cloud Run)
- Binds to 0.0.0.0 by default (container networking)
- Does NOT auto-select a different port (platform routers require the provided port)
"""

import argparse
import os
import sys

from webui.app_dash import run_app


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="TradingAgents Dash Web UI")

    parser.add_argument(
        "--port",
        type=int,
        default=7860,
        help="Port to run the server on (local default). Cloud platforms override via $PORT.",
    )

    parser.add_argument(
        "--server-name",
        type=str,
        default="0.0.0.0",
        help="Server host to bind to (use 0.0.0.0 in containers).",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Run in debug mode.",
    )

    parser.add_argument(
        "--max-threads",
        type=int,
        default=40,
        help="Maximum number of threads (kept for compatibility; Dash dev server may ignore).",
    )

    # Keep for compatibility, but not recommended for hosted deployment
    parser.add_argument(
        "--share",
        action="store_true",
        help="(Ignored for hosted deployment) Share the app publicly.",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    # Render (and other PaaS) provide PORT and expect the app to listen on it.
    port = int(os.environ.get("PORT", str(args.port)))

    # Bind to 0.0.0.0 inside containers for external access
    server_name = os.environ.get("SERVER_NAME", args.server_name) or "0.0.0.0"

    print(f"Starting TradingAgents Dash Web UI on {server_name}:{port} ...")

    # IMPORTANT: Do NOT try alternative ports in hosted environments.
    return run_app(
        port=port,
        share=False,  # safer default in hosted env
        server_name=server_name,
        debug=args.debug,
        max_threads=args.max_threads,
    )


if __name__ == "__main__":
    sys.exit(main())
