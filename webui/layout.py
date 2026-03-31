"""
Layout module for TradingAgents WebUI
Organizes the main application layout and component assembly
"""

from dash import dcc, html
import dash_bootstrap_components as dbc
from webui.components.strategy_panel import create_strategy_panel
from webui.components.header import create_header
from webui.components.config_panel import create_config_panel
from webui.components.status_panel import create_status_panel
from webui.components.chart_panel import create_chart_panel
from webui.components.decision_panel import create_decision_panel
from webui.components.reports_panel import create_reports_panel
from webui.components.dashboard_panel import create_dashboard_panel
from webui.components.backtest_panel import create_backtest_panel
from webui.config.constants import COLORS, REFRESH_INTERVALS


def create_intervals():
    """Create interval components for auto-refresh"""
    return [
        # Fast refresh for critical updates during analysis
        dcc.Interval(
            id='refresh-interval',
            interval=REFRESH_INTERVALS["fast"],
            n_intervals=0,
            disabled=True  # Start disabled, only enable when analysis is running
        ),
        
        # Medium refresh for reports and non-critical updates
        dcc.Interval(
            id='medium-refresh-interval',
            interval=REFRESH_INTERVALS["medium"],
            n_intervals=0,
            disabled=True
        ),
        
        # Slow refresh for account data
        dcc.Interval(
            id='slow-refresh-interval', 
            interval=REFRESH_INTERVALS["slow"],
            n_intervals=0,
            disabled=False  # Always enabled for account data
        )
    ]


def create_stores():
    """Create store components for state management"""
    from webui.utils.storage import create_storage_store_component
    return [
        dcc.Location(id='url', refresh=False),
        dcc.Store(id='app-store'),
        dcc.Store(id='chart-store', data={'last_symbol': None, 'selected_period': '1d'}),
        create_storage_store_component()
    ]


def create_main_layout():
    """Create the main application layout"""
    
    # Create UI components
    header = create_header()
    config_card = create_config_panel()
    status_card = create_status_panel()
    chart_card = create_chart_panel()
    decision_card = create_decision_panel()
    reports_card = create_reports_panel()
    
    # Create Dashboard card (replaces Alpaca account card)
    dashboard_card = create_dashboard_panel()
    
    # Strategy card (moved to tab)
    strategy_card = create_strategy_panel()
    
    # Backtest card
    backtest_card = create_backtest_panel()
    
    # Deep Analysis Layout
    deep_analysis_content = html.Div([
        dbc.Row([
            dbc.Col(config_card, md=6),
            dbc.Col([
                chart_card,
                html.Div(className="mb-3"),
                status_card,
                html.Div(className="mb-3"),
                decision_card,
            ], md=6)
        ]),
        html.Div(className="mt-4"),
        reports_card
    ])
    
    # Main Tabs Layout
    main_tabs = dbc.Tabs([
        dbc.Tab(dashboard_card, label="Dashboard", tab_id="main-tab-dashboard", label_style={"fontWeight": "bold"}),
        dbc.Tab(deep_analysis_content, label="Deep Analysis", tab_id="main-tab-analysis", label_style={"fontWeight": "bold"}),
        dbc.Tab(backtest_card, label="Backtest", tab_id="main-tab-backtest", label_style={"fontWeight": "bold"}),
    ], id="main-content-tabs", active_tab="main-tab-dashboard", className="mb-4")

    # Assemble the layout
    layout = dbc.Container(
        [
            dcc.Interval(
                id='dashboard-load-interval',
                interval=1*1000, # in milliseconds
                n_intervals=0,
                max_intervals=1 # Run only once
            ),
            # Intervals and stores
            *create_intervals(),
            *create_stores(),
            dcc.Interval(
                id='session-logout-interval',
                interval=60*1000,  # Check every minute
                n_intervals=0
            ),
            
            # Client-side script to handle iframe messages for prompt modal
            html.Script("""
                window.addEventListener('message', function(event) {
                    if (event.data && event.data.type === 'showPrompt') {
                        // Find and trigger the appropriate show prompt button
                        const buttons = document.querySelectorAll('[id*="show-prompt-"]');
                        const reportType = event.data.reportType;
                        
                        // Find the button that matches this report type
                        let targetButton = null;
                        for (let button of buttons) {
                            const buttonId = button.getAttribute('id');
                            if (buttonId && buttonId.includes(reportType)) {
                                targetButton = button;
                                break;
                            }
                        }
                        
                        // If no direct match, try pattern matching
                        if (!targetButton) {
                            for (let button of buttons) {
                                const buttonData = button.getAttribute('data-dash-props');
                                if (buttonData && buttonData.includes(reportType)) {
                                    targetButton = button;
                                    break;
                                }
                            }
                        }
                        
                        // Trigger the button click if found
                        if (targetButton) {
                            targetButton.click();
                        } else {
                            console.log('Could not find button for:', reportType);
                            // Fallback: trigger any show prompt button and set content manually
                            const anyPromptBtn = document.querySelector('[id*="show-prompt-"]');
                            if (anyPromptBtn) {
                                anyPromptBtn.click();
                                // Try to set the modal content directly after a short delay
                                setTimeout(() => {
                                    const modalTitle = document.querySelector('#prompt-modal-title');
                                    const modalContent = document.querySelector('#prompt-modal-content');
                                    if (modalTitle) modalTitle.textContent = event.data.title;
                                    if (modalContent) {
                                        // This will be filled by the callback, but we can try to trigger it
                                        console.log('Showing prompt for:', reportType);
                                    }
                                }, 100);
                            }
                        }
                    }
                });
            """),
            
            # Main content
            header,
            main_tabs,
            html.Div(strategy_card, style={"display": "none"}),
            html.Div(className="mt-4"),
        ],
        fluid=True,
        className="p-4",
        style={"backgroundColor": COLORS["background"]}
    )
    
    return layout 
