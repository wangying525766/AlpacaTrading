
from dash import dcc, html, Input, Output, State, callback, no_update
import dash_bootstrap_components as dbc
from webui.layout import create_main_layout

# This is a temporary, insecure password. We will replace this later.
VALID_USERNAME = "admin"
VALID_PASSWORD = "a9b1c8d0e7f6a5b4c3d2e1f0"

def create_login_layout():
    return dbc.Container([
        dbc.Row(
            dbc.Col(
                dbc.Card([
                    dbc.CardHeader(html.H4("InsightFlow Login", className="text-center")),
                    dbc.CardBody([
                        dbc.Input(id="username-input", type="text", placeholder="Username", className="mb-3"),
                        dbc.Input(id="password-input", type="password", placeholder="Password", className="mb-3"),
                        dbc.Button("Login", id="login-button", color="primary", className="w-100"),
                        dbc.Alert(
                            id="login-error",
                            color="danger",
                            is_open=False,
                            className="mt-3",
                        ),
                    ])
                ]),
                width={"size": 6, "offset": 3},
                md={"size": 4, "offset": 4}
            ),
            className="vh-100 d-flex align-items-center"
        )
    ], fluid=True, className="p-0")

def register_login_callbacks(app):
    @app.callback(
        Output('page-content', 'children'),
        Input('session', 'data')
    )
    def display_page(session_data):
        if session_data and session_data.get('logged_in'):
            return create_main_layout()
        return create_login_layout()

    @app.callback(
        [Output('session', 'data'),
         Output('login-error', 'is_open'),
         Output('login-error', 'children')],
        Input('login-button', 'n_clicks'),
        [State('username-input', 'value'),
         State('password-input', 'value')],
        prevent_initial_call=True
    )
    def handle_login(n_clicks, username, password):
        if n_clicks:
            if username == VALID_USERNAME and password == VALID_PASSWORD:
                return {'logged_in': True}, False, ""
            else:
                return no_update, True, "Incorrect username or password."
        return no_update, False, ""
