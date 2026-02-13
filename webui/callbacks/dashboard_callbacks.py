"""
webui/callbacks/dashboard_callbacks.py
Callbacks for the Dashboard Panel
"""

from dash import Input, Output, State, callback_context, MATCH, ALL
from dash.exceptions import PreventUpdate
import datetime
import json

from webui.components.dashboard_panel import get_market_data, render_email_content
import email_ticker_ingest

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
        if not ctx.triggered:
            raise PreventUpdate
            
        trigger_id_str = ctx.triggered[0]["prop_id"].split(".")[0]
        try:
            trigger_id = json.loads(trigger_id_str)
        except:
            raise PreventUpdate
            
        btn_type = trigger_id.get("type")
        btn_index = trigger_id.get("index")
        
        # Extract ticker from index (format: TICKER-INDEX)
        if not btn_index or "-" not in btn_index:
            raise PreventUpdate
            
        ticker = btn_index.split("-")[0]
        
        if "analysis-btn" in btn_type:
            # Go to Analysis tab
            return ticker, current_strategy_ticker, current_backtest_ticker, "main-tab-analysis"
        elif "backtest-btn" in btn_type:
            # Go to Backtest tab
            return current_analysis_ticker, current_strategy_ticker, ticker, "main-tab-backtest"
            
        raise PreventUpdate

    @app.callback(
        [Output("pre-market-content", "children"),
         Output("post-market-content", "children"),
         Output("dashboard-refresh-status", "children")],
        [Input("refresh-dashboard-btn", "n_clicks")],
        prevent_initial_call=True
    )
    def refresh_dashboard_data(n_clicks):
        if not n_clicks:
            raise PreventUpdate
            
        try:
            # Call the ingestion script to update data
            # This is a synchronous call and might take a few seconds
            # ideally this should be async or background task, but for now this is fine
            result = email_ticker_ingest.update_market_data()
            
            pre_market_data = result.get("pre_market")
            post_market_data = result.get("post_market")
            
            pre_content = render_email_content(pre_market_data, "Pre-Market (OpenOutCrier)")
            post_content = render_email_content(post_market_data, "Post-Market (FlowAlgo)", is_post_market=True)
            
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            status_msg = f"Last updated: {timestamp}"
            
            return pre_content, post_content, status_msg
            
        except Exception as e:
            error_msg = f"Error updating data: {str(e)}"
            # Return current content (or error message) and status
            # For simplicity returning error in status
            return dash.no_update, dash.no_update, error_msg
