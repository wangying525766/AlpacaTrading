"""
webui/components/dashboard_panel.py
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
import json
import os
from pathlib import Path
import pandas as pd

def get_market_data(filename):
    filepath = Path("out") / filename
    if filepath.exists():
        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except Exception as e:
            return {"error": str(e)}
    return None

def normalize_flowalgo_data(data_records):
    """
    Normalize raw data records to match the specific dashboard columns:
    TIME, TICKER, C/P, EXPIRY, STRIKE, SPOT, TYPE, PREMIUM, ACTIONS
    """
    normalized = []
    
    for row in data_records:
        # Helper to get value case-insensitive
        def get_val(keys, default=""):
            for k in keys:
                for row_k in row.keys():
                    if row_k.lower() == k.lower():
                        return row[row_k]
            return default

        # Map fields
        item = {
            "TIME": get_val(["time", "timestamp"], "N/A"),
            "TICKER": get_val(["ticker", "symbol", "sym"], "N/A"),
            "C/P": get_val(["c/p", "put/call", "cp"], "N/A").upper(),
            "EXPIRY": get_val(["expiry", "exp", "expiration"], "N/A"),
            "STRIKE": get_val(["strike", "str"], "N/A"),
            "SPOT": get_val(["spot", "ref", "reference"], "N/A"),
            "TYPE": get_val(["type", "flow type", "flow_type", "order_type", "details"], "BLOCK").upper(),
            "PREMIUM": get_val(["premium_raw", "premium", "prem", "val", "value"], "N/A"),
        }
        
        # Clean up C/P if it contains full words
        if "CALL" in item["C/P"]: item["C/P"] = "CALLS"
        elif "PUT" in item["C/P"]: item["C/P"] = "PUTS"
        
        # Clean up TYPE (remove extra info if needed, screenshot shows BLOCK, SPLIT, SWEEP)
        # If the type column is missing, we might need to infer or leave blank. 
        # But let's assume 'Type' exists or 'Details' contains it.
        
        normalized.append(item)
        
    return normalized

def render_flowalgo_table(data_records):
    if not data_records:
        return html.P("No data available.", className="text-muted")

    normalized_data = normalize_flowalgo_data(data_records)
    
    # Table Header
    header = html.Thead(
        html.Tr([
            html.Th("TIME", style={"color": "#888", "fontWeight": "600", "fontSize": "0.8rem"}),
            html.Th("TICKER", style={"color": "#888", "fontWeight": "600", "fontSize": "0.8rem"}),
            html.Th("C/P", style={"color": "#888", "fontWeight": "600", "fontSize": "0.8rem"}),
            html.Th("EXPIRY", style={"color": "#888", "fontWeight": "600", "fontSize": "0.8rem"}),
            html.Th("STRIKE", style={"color": "#888", "fontWeight": "600", "fontSize": "0.8rem"}),
            html.Th("SPOT", style={"color": "#888", "fontWeight": "600", "fontSize": "0.8rem"}),
            html.Th("TYPE", style={"color": "#888", "fontWeight": "600", "fontSize": "0.8rem"}),
            html.Th("PREMIUM", style={"color": "#888", "fontWeight": "600", "fontSize": "0.8rem"}),
            html.Th("ACTIONS", style={"color": "#888", "fontWeight": "600", "fontSize": "0.8rem", "textAlign": "right"}),
        ])
    )
    
    # Table Body
    rows = []
    for i, row in enumerate(normalized_data):
        # C/P Color
        cp_style = {"fontWeight": "bold"}
        if "CALL" in row["C/P"]:
            cp_style["color"] = "#00FF00" # Green
        elif "PUT" in row["C/P"]:
            cp_style["color"] = "#FF4444" # Red
            
        rows.append(html.Tr([
            html.Td(row["TIME"], className="align-middle"),
            html.Td(html.Strong(row["TICKER"]), className="align-middle"),
            html.Td(row["C/P"], style=cp_style, className="align-middle"),
            html.Td(row["EXPIRY"], className="align-middle"),
            html.Td(row["STRIKE"], className="align-middle"),
            html.Td(row["SPOT"], className="align-middle"),
            html.Td(row["TYPE"], className="align-middle"),
            html.Td(html.Strong(row["PREMIUM"]), className="align-middle"),
            html.Td([
                html.A("Analysis", id={"type": "flow-analysis-btn", "index": f"{row['TICKER']}-{i}"}, href="#", className="text-info me-3", style={"textDecoration": "none", "fontSize": "0.9rem"}),
                html.A("Backtest", id={"type": "flow-backtest-btn", "index": f"{row['TICKER']}-{i}"}, href="#", className="text-warning", style={"textDecoration": "none", "fontSize": "0.9rem"}),
            ], className="align-middle text-end"),
        ], style={"borderBottom": "1px solid #333", "fontSize": "0.9rem"}))
        
    body = html.Tbody(rows)
    
    return dbc.Table([header, body], hover=True, borderless=True, responsive=True, className="table-dark", style={"backgroundColor": "transparent"})

def render_pre_market_table(data_list, is_gainer=True):
    if not data_list:
        return html.P("No data available.", className="text-muted")
        
    # Table Header
    header = html.Thead(
        html.Tr([
            html.Th("TICKER", style={"color": "#888", "fontWeight": "600", "fontSize": "0.8rem", "width": "15%"}),
            html.Th("CHANGE", style={"color": "#888", "fontWeight": "600", "fontSize": "0.8rem", "width": "15%"}),
            html.Th("HEADLINE", style={"color": "#888", "fontWeight": "600", "fontSize": "0.8rem"}),
            html.Th("ACTIONS", style={"color": "#888", "fontWeight": "600", "fontSize": "0.8rem", "textAlign": "right", "width": "20%"}),
        ])
    )
    
    # Table Body
    rows = []
    for i, row in enumerate(data_list):
        # Change Color
        change_style = {"fontWeight": "bold"}
        if is_gainer:
            change_style["color"] = "#00FF00" # Green
        else:
            change_style["color"] = "#FF4444" # Red
            
        rows.append(html.Tr([
            html.Td(html.Strong(row.get("TICKER", "")), className="align-middle"),
            html.Td(row.get("CHANGE", ""), style=change_style, className="align-middle"),
            html.Td(row.get("HEADLINE", ""), className="align-middle", style={"fontSize": "0.85rem", "whiteSpace": "normal", "minWidth": "200px"}),
            html.Td([
                html.A("Analysis", id={"type": "pre-analysis-btn", "index": f"{row.get('TICKER', '')}-{i}"}, href="#", className="text-info me-2 d-block d-md-inline", style={"textDecoration": "none", "fontSize": "0.9rem"}),
                html.A("Backtest", id={"type": "pre-backtest-btn", "index": f"{row.get('TICKER', '')}-{i}"}, href="#", className="text-warning d-block d-md-inline", style={"textDecoration": "none", "fontSize": "0.9rem"}),
            ], className="align-middle text-end"),
        ], style={"borderBottom": "1px solid #333", "fontSize": "0.9rem"}))
        
    body = html.Tbody(rows)
    
    return dbc.Table([header, body], hover=True, borderless=True, responsive=True, className="table-dark", style={"backgroundColor": "transparent"})

def render_email_content(data, title, is_post_market=False):
    if not data:
        return html.Div([
            html.H5(title, className="card-title text-muted"),
            html.P("No data available. Click Refresh to fetch.", className="text-muted")
        ])
        
    if "error" in data:
            return html.Div([
            html.H5(title, className="card-title text-danger"),
            html.P(f"Error: {data['error']}", className="text-danger")
        ])

    # Check for parsed pre-market data (Gainers/Losers)
    if not is_post_market and "parsed_data" in data and data["parsed_data"]:
        parsed = data["parsed_data"]
        return html.Div([
            html.Div([
                html.Strong("Subject: "), html.Span(data.get("subject", "N/A")),
                html.Span(" | ", className="mx-2 text-muted"),
                html.Strong("Date: "), html.Span(data.get("date", "N/A")),
            ], className="mb-3 small text-muted"),
            
            dbc.Row([
                dbc.Col([
                    html.H6("Gainers", className="text-success mb-3", style={"fontWeight": "bold"}),
                    render_pre_market_table(parsed.get("gainers", []), is_gainer=True)
                ], xs=12, md=6, className="mb-4 mb-md-0"),
                dbc.Col([
                    html.H6("Losers", className="text-danger mb-3", style={"fontWeight": "bold"}),
                    render_pre_market_table(parsed.get("losers", []), is_gainer=False)
                ], xs=12, md=6)
            ])
        ])
    
    # Check for attachments with data
    attachments_content = []
    has_parsed_data = False
    
    if "attachments" in data and data["attachments"]:
        for att in data["attachments"]:
            if att.get("data"):
                has_parsed_data = True
                if is_post_market:
                    # Special rendering for FlowAlgo data
                    title = att.get("filename", "Data")
                    # Clean up filename for display
                    if "bigflow" in title.lower(): title = "Big Flow"
                    elif "unusual" in title.lower(): title = "Unusual Activity"
                    elif "levels" in title.lower(): 
                        # Skip Key Levels as requested by user (mostly N/A)
                        continue
                    
                    attachments_content.append(html.Div([
                        html.H6(title, className="mt-3 mb-2 text-info", style={"fontWeight": "bold"}),
                        render_flowalgo_table(att["data"])
                    ]))
                else:
                    # Generic table for other attachments
                    try:
                        df = pd.DataFrame(att["data"])
                        table = dbc.Table.from_dataframe(df, striped=True, bordered=True, hover=True, responsive=True, style={"fontSize": "0.85rem"})
                        attachments_content.append(html.Div([
                            html.H6(f"Attachment: {att['filename']}", className="mt-3 text-success"),
                            table
                        ]))
                    except:
                        pass
    
    # If it's Post-Market (FlowAlgo) and we have parsed data, we primarily show the table
    # The screenshot only shows the table, no email body or subject header (except the tab title)
    if is_post_market and has_parsed_data:
        return html.Div([
            html.P("Institutional block trades and sweeps > $1M premium", className="text-muted mb-3", style={"fontSize": "0.9rem"}),
            *attachments_content
        ])

    # Default view (Pre-market or fallback)
    return html.Div([
        html.H5(title, className="card-title text-primary"),
        html.Div([
            html.Strong("Subject: "), html.Span(data.get("subject", "N/A")),
            html.Br(),
            html.Strong("Date: "), html.Span(data.get("date", "N/A")),
            html.Hr(),
            # Content
            html.Div([
                 html.Pre(data.get("content", "No content"), style={"whiteSpace": "pre-wrap", "maxHeight": "200px", "overflowY": "auto"})
            ]),
            # Attachments
            *attachments_content
        ])
    ])

def create_dashboard_panel():
    """Create the main dashboard panel with Pre/Post market data"""
    
    pre_market_data = get_market_data("pre_market.json")
    post_market_data = get_market_data("post_market.json")
    
    return dbc.Card(
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    html.H4("Market Dashboard", className="mb-0"),
                ], width=8),
                dbc.Col([
                    dbc.Button([
                        html.I(className="fas fa-sync-alt me-2"),
                        "Refresh Data"
                    ], id="refresh-dashboard-btn", color="primary", size="sm", className="float-end")
                ], width=4)
            ], className="mb-4 align-items-center"),
            
            dbc.Tabs([
                dbc.Tab(
                    dbc.Card(dbc.CardBody(id="pre-market-content", children=render_email_content(pre_market_data, "Pre-Market (OpenOutCrier)")), className="mt-3 border-0"),
                    label="Pre-Market",
                    tab_id="tab-pre-market",
                    label_style={"color": "#ccc"},
                    active_label_style={"color": "#fff", "fontWeight": "bold", "borderBottom": "2px solid #0d6efd"}
                ),
                dbc.Tab(
                    dbc.Card(dbc.CardBody(id="post-market-content", children=render_email_content(post_market_data, "Post-Market (Big Flow)", is_post_market=True)), className="mt-3 border-0"),
                    label="Post-Market (Big Flow)",
                    tab_id="tab-post-market",
                    label_style={"color": "#ccc"},
                    active_label_style={"color": "#fff", "fontWeight": "bold", "borderBottom": "2px solid #0d6efd"}
                )
            ], id="dashboard-tabs", active_tab="tab-pre-market"),
            
            html.Div(id="dashboard-refresh-status", className="mt-2 text-muted small")
        ]),
        className="mb-4 shadow-sm",
        style={"backgroundColor": "#1e1e1e", "border": "1px solid #333"} # Dark theme card
    )
