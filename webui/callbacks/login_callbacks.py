
from dash import dcc, html, Input, Output, State, callback, no_update
import dash_bootstrap_components as dbc
import datetime
import os
import json
from webui.layout import create_main_layout

# Load credentials from environment variable
credentials_json = os.environ.get("CREDENTIALS")
VALID_CREDENTIALS = json.loads(credentials_json) if credentials_json else {}

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
            if username in VALID_CREDENTIALS and VALID_CREDENTIALS[username] == password:
                session_data = {
                    'logged_in': True,
                    'login_time': datetime.datetime.utcnow().isoformat()
                }
                return session_data, False, ""
            else:
                return no_update, True, "Incorrect username or password."
        return no_update, False, ""

    @app.callback(
        Output('session', 'data', allow_duplicate=True),
        Input('logout-button', 'n_clicks'),
        prevent_initial_call=True
    )
    def handle_logout(n_clicks):
        if n_clicks:
            return {'logged_in': False}
        return no_update

    @app.callback(
        Output('session', 'data', allow_duplicate=True),
        Input('session-logout-interval', 'n_intervals'),
        State('session', 'data'),
        prevent_initial_call=True
    )
    def auto_logout(n_intervals, session_data):
        if session_data and session_data.get('logged_in'):
            login_time_str = session_data.get('login_time')
            if login_time_str:
                login_time = datetime.datetime.fromisoformat(login_time_str)
                if (datetime.datetime.utcnow() - login_time) > datetime.timedelta(days=1):
                    return {'logged_in': False}
        return no_update
