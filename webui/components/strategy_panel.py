# webui/components/strategy_panel.py
from dash import html, dcc
import dash_bootstrap_components as dbc


def create_strategy_panel():
    return dbc.Card(
        dbc.CardBody([
            html.H4("📈 Strategy Simulator", className="card-title mb-3"),
            dcc.Store(id="stg-logfile", storage_type="memory"),

            # 定时器：每2秒拉一次日志
            dcc.Interval(id="stg-log-poll", interval=2000, n_intervals=0, disabled=True),

            # 日志显示容器（和 stg-output 分开，避免混杂）
            html.Div(
                id="stg-live-log",
                style={
                    "whiteSpace": "pre-wrap",
                    "fontFamily": "ui-monospace, SFMono-Regular, Menlo, monospace",
                    "background": "#0b1020",
                    "color": "#d6e2ff",
                    "borderRadius": "8px",
                    "padding": "10px",
                    "minHeight": "160px",
                    "maxHeight": "360px",
                    "overflowY": "auto",
                    "marginTop": "8px",
                }
            ),


            # === Top row: Symbol / Strategy / Interval (same line, bottom-aligned) ===
            dbc.Row([
                dbc.Col([
                    dbc.Label("Symbol", className="small fw-bold"),
                    dbc.Input(
                        id="stg-symbol",
                        type="text",
                        value="AAPL",
                        placeholder="Symbol",
                        className="w-100",
                    ),
                ], xs=12, sm=6, lg=3),

                dbc.Col([
                    dbc.Label("Strategy", className="small fw-bold"),
                    dcc.Dropdown(
                        id="stg-strategy",
                        options=[
                            {"label": "SMA Cross", "value": "sma"},
                            {"label": "VWAP (Intraday)", "value": "vwap"},
                        ],
                        value="sma",
                        clearable=False,
                        className="w-100",         # 让下拉在列内铺满
                        style={"color": "#000"},   # 保留你原来的黑字
                    ),
                ], xs=12, sm=6, lg=3),

                dbc.Col([
                    dbc.Label("Interval", className="small fw-bold"),
                    dcc.Dropdown(
                        id="stg-interval",
                        options=[
                            {"label": "1 Day", "value": "1d"},
                            {"label": "5 Minutes", "value": "5m"},
                            {"label": "1 Minute", "value": "1m"},
                        ],
                        value="1d",
                        clearable=False,
                        className="w-100",
                        style={"color": "#000"},
                    ),
                ], xs=12, sm=6, lg=3),
            ], className="g-2 mb-2 align-items-end"),

            # === SMA / VWAP parameters ===
            dbc.Row([
                dbc.Col(dbc.Input(id="stg-fast", type="number", value=10, placeholder="Fast SMA"), md=2),
                dbc.Col(dbc.Input(id="stg-slow", type="number", value=50, placeholder="Slow SMA"), md=2),
                dbc.Col(dbc.Input(id="stg-start", type="text", value="2025-01-01", placeholder="Start YYYY-MM-DD"), md=3),
                dbc.Col(dbc.Input(id="stg-end", type="text", value="2025-06-01", placeholder="End YYYY-MM-DD (opt)"), md=3),
            ], className="g-2 mb-2"),

            # === Advanced parameters ===
            dbc.Row([
                dbc.Col(dbc.Input(id="stg-hys", type="number", value=0.001, step=0.0005, placeholder="hysteresis"), md=2),
                dbc.Col(dbc.Input(id="stg-cool", type="number", value=3, placeholder="cooldown bars"), md=2),
                dbc.Col(dbc.Input(id="stg-confirm", type="number", value=2, placeholder="confirm bars"), md=2),
                dbc.Col(dbc.Checklist(
                    options=[{"label": " Plot result", "value": "plot"}],
                    value=[],
                    id="stg-plot",
                    switch=True
                ), md=3),
            ], className="g-2 mb-3"),

            # === Buttons ===
            dbc.Row([
                dbc.Col(dbc.Button("Run Backtest", id="btn-stg-backtest", color="primary", className="w-100"), md=3),
                dbc.Col(dbc.Button("Start Live (detached)", id="btn-stg-live", color="success", className="w-100"), md=3),
            ], className="g-2 mb-3"),

            # === Output area ===
            html.Div(
                id="stg-output",
                style={
                    "whiteSpace": "pre-wrap",
                    "fontFamily": "ui-monospace, SFMono-Regular, Menlo, monospace",
                    "background": "#0b1020",
                    "color": "#d6e2ff",
                    "borderRadius": "8px",
                    "padding": "10px",
                    "minHeight": "120px",
                },
            ),
        ]),
        className="mb-4",
    )
