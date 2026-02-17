from dash import Input, Output, State, callback_context, html
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import glob
import os
import datetime
import yfinance as yf

def register_backtest_callbacks(app):
    @app.callback(
        [Output("backtest-chart", "figure"),
         Output("backtest-stats", "children"),
         Output("backtest-results-container", "style")],
        [Input("run-backtest-btn", "n_clicks"),
         Input("backtest-ticker-input", "value")],
        prevent_initial_call=True
    )
    def run_backtest(n_clicks, ticker):
        if not ticker:
            return {}, "", {"display": "none"}
            
        ticker = ticker.upper().strip()
        
        # Define Date Range (Last 60 days to cover the requested periods)
        today = datetime.date.today()
        start_date = today - datetime.timedelta(days=60)
        end_date = today 

        # --- Step 1: Fetch Price Data First ---
        price_start = start_date.strftime("%Y-%m-%d")
        price_end = (end_date + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        
        hist = pd.DataFrame()
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(start=price_start, end=price_end)
            # Fallback for recent data
            if not hist.empty and hist.index[-1].date() < today:
                print("yfinance data might be stale, attempting to fetch more recent data...")
                more_hist = stock.history(period="5d") # Fetch last 5 days
                if not more_hist.empty:
                    # Combine and remove duplicates, keeping the last entry for each day
                    hist = pd.concat([hist, more_hist])
                    hist = hist[~hist.index.duplicated(keep='last')].sort_index()

        except Exception as e:
            print(f"Error fetching price data for {ticker}: {e}")

        # Ensure the index is unique and sorted before proceeding
        if not hist.empty:
            hist = hist[~hist.index.duplicated(keep='last')].sort_index()

        if hist.empty:
            return {}, html.Div(f"Could not fetch price data for {ticker} from yfinance. Check ticker symbol or network.", className="text-danger"), {"display": "block"}

        # --- Step 2: Create Figure and Add Price Chart ---
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # Add a prominent line for the close price
        fig.add_trace(
            go.Scatter(
                x=hist.index, 
                y=hist['Close'], 
                name='Close Price', 
                line=dict(color='cyan', width=2),
                hovertemplate='<b>Date</b>: %{x|%Y-%m-%d}<br>' +
                              '<b>Close</b>: %{y:$.2f}<br>' +
                              '<b>Open</b>: %{customdata[0]:$.2f}<br>' +
                              '<b>High</b>: %{customdata[1]:$.2f}<br>' +
                              '<b>Low</b>: %{customdata[2]:$.2f}<extra></extra>',
                customdata=hist[['Open', 'High', 'Low']]
            ),
            secondary_y=False,
        )

        price_source = "yfinance"
        
        # --- Step 3: Load and Process Key Levels Data ---
        key_levels_files = glob.glob("data/key_levels/key_levels_*.csv")
        all_levels_data = []
        for f in key_levels_files:
            try:
                df = pd.read_csv(f)
                if 'ticker' in df.columns:
                    df_ticker = df[df['ticker'].str.upper() == ticker].copy()
                    if not df_ticker.empty:
                        all_levels_data.append(df_ticker)
            except Exception as e:
                print(f"Error processing {f}: {e}")
                continue

        if all_levels_data:
            levels_df = pd.concat(all_levels_data, ignore_index=True)
            levels_df.drop_duplicates(subset=['level'], inplace=True)

            # Add a scatter trace for the legend
            fig.add_trace(go.Scatter(
                x=[None],
                y=[None],
                mode='lines',
                line=dict(color="MediumPurple", width=1, dash="dashdot"),
                name='Key Levels'
            ))

            for index, row in levels_df.iterrows():
                level_price = row['level']
                fig.add_shape(
                    type="line",
                    x0=hist.index[0],
                    y0=level_price,
                    x1=hist.index[-1],
                    y1=level_price,
                    line=dict(
                        color="MediumPurple",
                        width=1,
                        dash="dashdot",
                    ),
                    name=f"Level ${level_price:.2f}",
                )
                fig.add_annotation(
                    x=hist.index[-1],
                    y=level_price,
                    text=f"${level_price:.2f}",
                    showarrow=False,
                    xanchor="left",
                    yanchor="middle",
                    font=dict(color="MediumPurple", size=10)
                )

        # --- Step 4: Load and Process BigFlow Data (if available) ---
        bigflow_files = glob.glob("data/bigflow/bigflow_*.csv")
        all_flow_data = []
        
        for f in bigflow_files:
            try:
                # Extract date from filename: bigflow_YYYY-MM-DD.csv or bigflow_YYYYMMDD.csv
                basename = os.path.basename(f)
                date_str = basename.replace("bigflow_", "").replace(".csv", "")
                
                # Try parsing with hyphens first
                try:
                    file_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                except ValueError:
                    # Try without hyphens
                    try:
                        file_date = datetime.datetime.strptime(date_str, "%Y%m%d").date()
                    except ValueError:
                        print(f"Skipping file with unknown date format: {basename}")
                        continue
                
                if start_date <= file_date <= end_date:
                    df = pd.read_csv(f)
                    # Filter by ticker
                    if 'ticker' in df.columns:
                        df_ticker = df[df['ticker'] == ticker].copy()
                        if not df_ticker.empty:
                            df_ticker['date'] = file_date
                            all_flow_data.append(df_ticker)
            except Exception as e:
                print(f"Error processing {f}: {e}")
                continue
        
        # --- Step 4: Plot Flow Data and Calculate Stats if it exists ---
        stats_html = html.Div(f"No BigFlow data found for {ticker} in the last 60 days.", className="text-warning")
        stats_style = {"display": "block"}

        if all_flow_data:
            bigflow_df = pd.concat(all_flow_data, ignore_index=True)
            
            # Convert premium to numeric
            bigflow_df['premium'] = pd.to_numeric(bigflow_df['premium'], errors='coerce')
            
            # Aggregate by date and type (CALLS/PUTS)
            daily_flow = bigflow_df.groupby(['date', 'cp'])['premium'].sum().unstack(fill_value=0).reset_index()
            if 'CALLS' not in daily_flow.columns: daily_flow['CALLS'] = 0
            if 'PUTS' not in daily_flow.columns: daily_flow['PUTS'] = 0
            
            daily_flow['NetFlow'] = daily_flow['CALLS'] - daily_flow['PUTS']
            
            # Bar for Net Flow
            daily_flow['date'] = pd.to_datetime(daily_flow['date'])
            daily_flow['DateStr'] = daily_flow['date'].dt.strftime('%Y-%m-%d')
            
            hist['DateStr'] = hist.index.strftime('%Y-%m-%d')
            merged = pd.merge(hist.reset_index(), daily_flow, left_on='DateStr', right_on='DateStr', how='left').fillna(0)
            x_axis = merged['Date']
            y_axis = merged['NetFlow']
            calls_data = merged['CALLS']
            puts_data = merged['PUTS']
            price_data = merged['Close']
            
            colors = ['green' if x >= 0 else 'red' for x in y_axis]
            
            import numpy as np
            custom_data = np.stack((calls_data, puts_data, price_data), axis=-1)

            fig.add_trace(
                go.Bar(x=x_axis, y=y_axis, name="Net BigFlow (Calls-Puts)",
                       marker_color=colors, opacity=0.5,
                       customdata=custom_data,
                       hovertemplate="<br>".join([
                           "Date: %{x|%Y-%m-%d}",
                           "Net Flow: $%{y:,.0f}",
                           "Calls: $%{customdata[0]:,.0f}",
                           "Puts: $%{customdata[1]:,.0f}",
                           "Price: $%{customdata[2]:.2f}",
                           "<extra></extra>"
                       ])),
                secondary_y=True
            )
            
            # Calculate Stats
            total_calls = bigflow_df[bigflow_df['cp'] == 'CALLS']['premium'].sum()
            total_puts = bigflow_df[bigflow_df['cp'] == 'PUTS']['premium'].sum()
            sentiment = "BULLISH" if total_calls > total_puts else "BEARISH"
            
            # Split stats into "Past 60-30 days" and "Past 30 days"
            cutoff_date = pd.Timestamp(today - datetime.timedelta(days=30))
            
            # We need to filter bigflow_df by date
            bigflow_df['date'] = pd.to_datetime(bigflow_df['date'])
            
            recent_df = bigflow_df[bigflow_df['date'] >= cutoff_date]
            older_df = bigflow_df[bigflow_df['date'] < cutoff_date]
            
            recent_net = recent_df[recent_df['cp']=='CALLS']['premium'].sum() - recent_df[recent_df['cp']=='PUTS']['premium'].sum()
            older_net = older_df[older_df['cp']=='CALLS']['premium'].sum() - older_df[older_df['cp']=='PUTS']['premium'].sum()
            
            # Calculate Validation (Signal vs Price Movement in Recent Window)
            validation_ui = html.Div()
            
            # Unify price data for stats
            price_df = hist.reset_index().rename(columns={'Close': 'price'})[['Date', 'price']]
            price_df.columns = ['date', 'price']

            if not price_df.empty:
                 price_df['date'] = pd.to_datetime(price_df['date']).dt.date
                 price_df.drop_duplicates(subset=['date'], inplace=True)
                 price_df = price_df.sort_values('date')
                 recent_prices = price_df[price_df['date'] >= cutoff_date.date()].copy()
                 
                 if len(recent_prices) > 1:
                     start_price = recent_prices.iloc[0]['price']
                     end_price = recent_prices.iloc[-1]['price']
                     price_change_pct = ((end_price - start_price) / start_price) * 100
                     
                     signal_bullish = older_net > 0
                     price_bullish = price_change_pct > 0
                     
                     is_correct = (signal_bullish and price_bullish) or (not signal_bullish and not price_bullish)
                     
                     val_color = "green" if is_correct else "red"
                     val_icon = "✅" if is_correct else "❌"
                     val_text = "Signal Validated" if is_correct else "Signal Failed"
                     
                     validation_ui = html.Div([
                         html.Hr(),
                         html.H5("Validation Result (Last 30 Days)"),
                         html.P(f"Signal (60-30d ago): {'BULLISH' if signal_bullish else 'BEARISH'}"),
                         html.P(f"Price Change (Last 30d): {price_change_pct:.2f}% ({start_price:.2f} -> {end_price:.2f})"),
                         html.H4(f"{val_icon} {val_text}", style={'color': val_color})
                     ])

            stats_html = html.Div([
                dbc.Row([
                    dbc.Col([
                        html.H5("Overall (60 Days)"),
                        html.P(f"Total Call Premium: ${total_calls:,.0f}"),
                        html.P(f"Total Put Premium: ${total_puts:,.0f}"),
                        html.H6(f"Sentiment: {sentiment}", style={'color': 'green' if sentiment == 'BULLISH' else 'red'})
                    ], md=4),
                    dbc.Col([
                        html.H5("Previous Window (60-30 Days Ago)"),
                        html.P(f"Net Flow: ${older_net:,.0f}"),
                        html.P("Used for Signal Generation", className="text-muted small")
                    ], md=4),
                    dbc.Col([
                        html.H5("Recent Window (Last 30 Days)"),
                        html.P(f"Net Flow: ${recent_net:,.0f}"),
                        html.P("Used for Validation", className="text-muted small")
                    ], md=4)
                ]),
                validation_ui
            ])
            stats_style = {"display": "block"}
        
        fig.update_layout(
            title=f"Backtest Analysis: {ticker} (Last 60 Days) - Price Source: {price_source}",
            xaxis_title="Date",
            yaxis_title="Price",
            yaxis2_title="Net Option Premium Flow" if all_flow_data else "",
            template="plotly_dark",
            height=600,
            xaxis_rangeslider_visible=False
        )
        
        return fig, stats_html, stats_style
