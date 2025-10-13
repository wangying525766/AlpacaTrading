# webui/components/social_panel.py
from dash import html, dcc
import dash_bootstrap_components as dbc

def create_social_panel():
    return dbc.Card(
        dbc.CardBody([
            html.H4("🕸️ Social Signals (Twitter)", className="card-title mb-3"),

            # 存放爬虫状态/结果的隐藏存储
            dcc.Store(id="crawl-logfile", storage_type="memory"),
            dcc.Store(id="crawl-result-path", storage_type="memory"),
            dcc.Interval(id="crawl-poll", interval=2500, n_intervals=0, disabled=True),

            # 控件区
            dbc.Row([
                dbc.Col(dbc.Input(id="crawl-query", type="text",
                                  value="AI stocks OR semiconductors OR NVDA OR TSLA",
                                  placeholder="keywords / boolean query"), md=12)
            ], className="g-2 mb-2"),

            dbc.Row([
                dbc.Col([
                    dbc.Label("Lookback"),
                    dcc.Dropdown(
                        id="crawl-hours",
                        options=[
                            {"label": "3h", "value": 3},
                            {"label": "6h", "value": 6},
                            {"label": "12h", "value": 12},
                            {"label": "24h", "value": 24},
                            {"label": "48h", "value": 48},

                        ],
                        value=12,                # 仅默认值
                        clearable=False,
                        persistence=True,        # 避免刷新丢失
                        persistence_type="session", style={"color": "#000"}
                    )
                ], md=4),
                dbc.Col([
                    dbc.Label("Top N tickers"),
                    dbc.Input(id="crawl-topk", type="number", value=8, min=1, max=30)
                ], md=4),
                dbc.Col([
                    dbc.Label("Min mentions"),
                    dbc.Input(id="crawl-min-mentions", type="number", value=3, min=1, max=50)
                ], md=4),
            ], className="g-2 mb-2"),

            # 按钮
            dbc.Row([
                dbc.Col(dbc.Button("Run Crawl", id="btn-crawl", color="secondary", className="w-100"), md=6),
                dbc.Col(dbc.Button("Stop Polling", id="btn-crawl-stop", color="dark", outline=True, className="w-100"), md=6),
            ], className="g-2 mb-3"),

            # 汇总 + 推荐
            html.Div(id="crawl-summary", className="small",
                     style={"whiteSpace": "pre-wrap", "color": "#8fb3ff"}),

            html.Hr(),

            html.Div(id="crawl-recos", style={"whiteSpace": "pre-wrap"}),

            html.Hr(),

            html.Div(
                id="crawl-log",
                style={
                    "whiteSpace": "pre-wrap",
                    "fontFamily": "ui-monospace, SFMono-Regular, Menlo, monospace",
                    "background": "#0b1020",
                    "color": "#a7b3c9",
                    "borderRadius": "8px",
                    "padding": "10px",
                    "minHeight": "120px",
                    "maxHeight": "260px",
                    "overflowY": "auto",
                }
            ),
        ]),
        className="mb-4"
    )
