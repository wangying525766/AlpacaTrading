"""
webui/callbacks/dashboard_callbacks.py
Callbacks for the Dashboard Panel
"""

from dash import Input, Output, State, callback_context, MATCH, ALL
from dash.exceptions import PreventUpdate
import datetime
import json
import glob
import os
from pathlib import Path

from webui.components.dashboard_panel import get_market_data, render_email_content
import email_ticker_ingest

def get_latest_market_data(data_type: str):
    """
    Gets the latest market data from the generic JSON file.
    """
    file_path = Path("out") / f"{data_type}.json"
    if file_path.exists():
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            print(f"Error reading file {file_path}: {e}")
    return {"message": f"No {data_type.replace('_', ' ')} data file found."}


def register_dashboard_callbacks(app):
    
    @app.callback(
        [Output("ticker-input", "value", allow_duplicate=True),
         Output("stg-symbol", "value"),
         Output("backtest-ticker-input", "value"),
         Output("main-content-tabs", "active_tab")],
        [Input({"type": "flow-analysis-btn", "index": ALL}, "n_clicks"),
         Input({"type": "flow-backtest-btn", "index": ALL}, "n_clicks"),
         Input({"type": "pre-analysis-btn", "index": ALL}, "n_clicks"),
         Input({"type": "pre-backtest-btn", "index": ALL}, "n_clicks")],
        [State("ticker-input", "value"),
         State("stg-symbol", "value"),
         State("backtest-ticker-input", "value"),
         State("main-content-tabs", "active_tab")],
        prevent_initial_call=True
    )
    def handle_dashboard_actions(flow_analysis, flow_backtest, pre_analysis, pre_backtest, 
                               current_analysis_ticker, current_strategy_ticker, current_backtest_ticker, current_tab):
        ctx = callback_context
        if not ctx.triggered or ctx.triggered[0]['value'] is None:
            raise PreventUpdate
            
        trigger_id_str = ctx.triggered[0]["prop_id"].split(".")[0]
        try:
            trigger_id = json.loads(trigger_id_str)
        except:
            raise PreventUpdate
            
        btn_type = trigger_id.get("type")
        btn_index = trigger_id.get("index")
        
        if not btn_index or "-" not in btn_index:
            raise PreventUpdate
            
        ticker = btn_index.split("-")[0]
        
        if "analysis-btn" in btn_type:
            return ticker, current_strategy_ticker, current_backtest_ticker, "main-tab-analysis"
        elif "backtest-btn" in btn_type:
            return current_analysis_ticker, current_strategy_ticker, ticker, "main-tab-backtest"
            
        raise PreventUpdate

    @app.callback(
        [Output("pre-market-content", "children"),
         Output("post-market-content", "children"),
         Output("dashboard-refresh-status", "children")],
        [Input("refresh-dashboard-btn", "n_clicks"),
         Input("dashboard-load-interval", "n_intervals")],
    )
    def refresh_dashboard_data(n_clicks, n_intervals):
        ctx = callback_context
        if not ctx.triggered:
            raise PreventUpdate

        # Always update data on load or refresh click
        email_ticker_ingest.update_market_data()

        pre_market_data = get_latest_market_data("pre_market")
        post_market_data = get_latest_market_data("post_market")

        pre_content = render_email_content(pre_market_data, "Pre-Market (OpenOutCrier)")
        post_content = render_email_content(post_market_data, "Post-Market (FlowAlgo)", is_post_market=True)

        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        status_msg = f"Last updated: {timestamp}"
        
        return pre_content, post_content, status_msg
