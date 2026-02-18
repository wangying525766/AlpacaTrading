
import dash_bootstrap_components as dbc
from dash import html

def create_login_layout():
    """Create the layout for the login page."""
    return dbc.Container(
        [
            dbc.Row(
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader(html.H4("Login", className="text-center")),
                            dbc.CardBody(
                                [
                                    dbc.Alert(
                                        "Invalid credentials. Please try again.",
                                        id="login-alert",
                                        is_open=False,
                                        duration=4000,
                                        color="danger",
                                    ),
                                    dbc.Input(
                                        id="username-input",
                                        type="text",
                                        placeholder="Username",
                                        className="mb-3",
                                    ),
                                    dbc.Input(
                                        id="password-input",
                                        type="password",
                                        placeholder="Password",
                                        className="mb-3",
                                    ),
                                    dbc.Button(
                                        "Login",
                                        id="login-button",
                                        color="primary",
                                        className="w-100",
                                        n_clicks=0,
                                    ),
                                ]
                            ),
                        ]
                    ),
                    width=10,
                    md=6,
                    lg=4,
                ),
                justify="center",
                className="align-items-center",
                style={"height": "80vh"},
            )
        ],
        fluid=True,
    )
