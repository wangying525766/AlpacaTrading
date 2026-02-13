from dash import html, dcc
import dash_bootstrap_components as dbc

def create_backtest_panel():
    """Create the backtest panel component"""
    return dbc.Card(
        [
            dbc.CardHeader(
                dbc.Row(
                    [
                        dbc.Col(html.H4("BigFlow Backtest", className="mb-0"), width="auto"),
                        dbc.Col(
                            dbc.InputGroup(
                                [
                                    dbc.InputGroupText("Ticker"),
                                    dbc.Input(id="backtest-ticker-input", placeholder="e.g. NVDA", type="text", debounce=True),
                                    dbc.Button("Run Backtest", id="run-backtest-btn", color="primary"),
                                ]
                            ),
                            width=6,
                        ),
                    ],
                    align="center",
                    justify="between",
                )
            ),
            dbc.CardBody(
                [
                    dcc.Loading(
                        id="backtest-loading",
                        children=[
                            html.Div(id="backtest-results-container", children=[
                                dcc.Graph(id="backtest-chart"),
                                html.Div(id="backtest-stats", className="mt-3")
                            ])
                        ]
                    )
                ]
            ),
        ],
        className="mb-3",
        style={"height": "calc(100vh - 120px)"}
    )
