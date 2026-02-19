"""
app_dash.py - Simplified Dash-based web UI for TradingAgents

Refactored version with organized modules for maintainability.

RECENT FIX: Multiple Symbol Page Refresh Issue
- Stores symbols list in browser storage and restores all symbol pages correctly
- Added safeguards to prevent index out of range errors during pagination
"""

import logging
import os

import dash
from dash import dcc, html
import dash_bootstrap_components as dbc
from flask import Flask

from webui.config.constants import APP_CONFIG
from webui.callbacks import register_all_callbacks


def apply_sequential_mode_fix():
    """Apply fix for sequential execution mode report mapping bug"""
    try:
        from webui.utils.state import AppState

        # Check if fix is already applied
        if hasattr(AppState, "_mapping_fix_applied"):
            return True

        original_process_chunk_updates = AppState.process_chunk_updates

        def fixed_process_chunk_updates(self, chunk):
            """Fixed version that correctly maps social analyst reports"""
            current_symbol = getattr(self, "current_symbol", "")
            if current_symbol:
                state = self.get_state(current_symbol)
                if state:
                    social_status = state["agent_statuses"].get("Social Analyst")
                    if social_status == "in_progress":
                        # Detect bug: Social Analyst writing to market_report
                        if "market_report" in chunk and "sentiment_report" not in chunk:
                            chunk["sentiment_report"] = chunk["market_report"]
                            del chunk["market_report"]
            return original_process_chunk_updates(self, chunk)

        AppState.process_chunk_updates = fixed_process_chunk_updates
        AppState._mapping_fix_applied = True
        return True

    except Exception as e:
        print(f"⚠️ Could not apply sequential mode fix: {e}")
        return False


def create_app() -> dash.Dash:
    """Create and configure the Dash application"""

    # Apply the sequential mode fix first
    apply_sequential_mode_fix()

    # Initialize Flask server
    flask_server = Flask(__name__)

    # Initialize Dash app with Bootstrap
    app = dash.Dash(
        __name__,
        server=flask_server,
        external_stylesheets=[
            dbc.themes.DARKLY,
            *APP_CONFIG["external_stylesheets"],
        ],
        suppress_callback_exceptions=APP_CONFIG["suppress_callback_exceptions"],
        update_title=APP_CONFIG["update_title"],
    )

    app.title = APP_CONFIG["title"]

    # Keep your current router shell layout
    app.layout = html.Div(
        [
            dcc.Location(id="url", refresh=False),
            dcc.Store(id="session", storage_type="session"),
            html.Div(id="page-content"),
        ]
    )

    # Register all callbacks (IMPORTANT: should be called once per app instance)
    register_all_callbacks(app)

    return app


def run_app(
    port: int = 7860,
    share: bool = False,
    server_name: str = "0.0.0.0",
    debug: bool = False,
    max_threads: int = 1,
) -> int:
    """Run the TradingAgents Dash Web UI"""

    # Double-safety: hosted platforms provide PORT; always respect it if present.
    port = int(os.environ.get("PORT", str(port)))
    server_name = os.environ.get("SERVER_NAME", server_name) or "0.0.0.0"

    app = create_app()

    if debug:
        print(f"Starting TradingAgents Dash Web UI on {server_name}:{port} ...")
    else:
        print("Starting TradingAgents Web UI...")

    # Suppress verbose HTTP request logs from Werkzeug
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("dash.callback").setLevel(logging.ERROR)

    # Dash dev server; fine for internal beta. (Later you can switch to gunicorn.)
    app.run(
        host=server_name,
        port=port,
        debug=debug,
        dev_tools_hot_reload=debug,
    )

    return 0


# For WSGI servers (gunicorn) usage:
# gunicorn "webui.app_dash:server" --bind 0.0.0.0:$PORT
# IMPORTANT: We do NOT create the Dash app at import time to avoid side effects.
_app_for_server = create_app()
server = _app_for_server.server


if __name__ == "__main__":
    run_app(debug=True)
