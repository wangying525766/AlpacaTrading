"""
webui/components/header.py - Header component for the web UI.
"""

import dash_bootstrap_components as dbc
from dash import html

def create_header():
    """Create the header component for the web UI."""
    return dbc.Card(
        dbc.CardBody([
            html.H1("📊InsightFlow: AI-Powered Market Intelligence", 
                    className="text-center mb-4")
        ]),
        className="mb-4"
    ) 