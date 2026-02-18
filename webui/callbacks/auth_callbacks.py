
from dash import Input, Output, State, callback, no_update
from webui.components.login_layout import create_login_layout
from webui.layout import create_app_layout

# --- User Accounts ---
VALID_USERNAME_PASSWORD_PAIRS = {
    'admin': 'admin123',
    'viewer': 'view'
}

def register_auth_callbacks(app):
    @app.callback(
        Output("page-content", "children"),
        Input("url", "pathname"),
        Input("session-store", "data"),
    )
    def display_page(pathname, session_data):
        if session_data and session_data.get("logged_in"):
            return create_app_layout()
        else:
            return create_login_layout()

    @app.callback(
        Output("session-store", "data"),
        Output("login-alert", "is_open"),
        Input("login-button", "n_clicks"),
        State("username-input", "value"),
        State("password-input", "value"),
    )
    def on_login_button_click(n_clicks, username, password):
        if n_clicks > 0:
            if username in VALID_USERNAME_PASSWORD_PAIRS and VALID_USERNAME_PASSWORD_PAIRS[username] == password:
                return {"logged_in": True}, False
            else:
                return no_update, True
        return no_update, False

    @app.callback(
        Output("session-store", "clear_data"),
        Input("logout-button", "n_clicks"),
        prevent_initial_call=True
    )
    def on_logout_button_click(n_clicks):
        if n_clicks is not None and n_clicks > 0:
            return True
        return False
