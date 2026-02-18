"""
webui/components/header.py - Header component for the web UI.
"""

import dash_bootstrap_components as dbc
from dash import html

def create_header():
    """Create the header component for the web UI."""
    return dbc.Card(
        dbc.CardBody([
            dbc.Row([
                dbc.Col(html.H1("📊InsightFlow: AI-Powered Market Intelligence", className="mb-0"), width='auto'),
                dbc.Col(dbc.Button("Logout", id="logout-button", color="secondary"), width="auto")
            ], justify="between", align="center")
        ]),
        className="mb-4"
    ) 