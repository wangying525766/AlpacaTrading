# -------------------------------- charts.py -----------------------

import random
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pandas as pd
import traceback
import pytz
import yfinance as yf
from typing import Union

def create_chart(ticker: str, period: str = "1y", end_date: Union[str, datetime] = None):
    """
    Create a Plotly candlestick+volume chart for a given ticker and period using Yahoo Finance.
    Falls back to demo data if API fails or no bars are returned.
    """
    # Yahoo Finance Period & Interval Mapping
    period_map = {
        "15m": {"period": "5d", "interval": "15m"},      # 5 days of 15m data
        "1d":  {"period": "1d", "interval": "5m"},       # 1 day of 5m data
        "1w":  {"period": "5d", "interval": "30m"},      # 5 days of 30m data
        "1mo": {"period": "1mo", "interval": "1h"},      # 1 month of 1h data
        "1y":  {"period": "1y", "interval": "1d"},       # 1 year of daily data
    }
    
    # Default to 1y if period not found
    yf_params = period_map.get(period, period_map["1y"])
    
    try:
        # Fetch data from Yahoo Finance
        # auto_adjust=True accounts for splits/dividends (simulating 'Adj Close' behavior for OHLC)
        df = yf.download(
            tickers=ticker, 
            period=yf_params["period"], 
            interval=yf_params["interval"], 
            progress=False,
            auto_adjust=True,
            multi_level_index=False 
        )
        
        # Yahoo Finance returns capitalized columns: Open, High, Low, Close, Volume
        # Rename to lowercase to match existing plotting logic
        df.rename(columns={
            "Open": "open", 
            "High": "high", 
            "Low": "low", 
            "Close": "close", 
            "Volume": "volume"
        }, inplace=True)
        
        # Ensure timestamp is a column (reset index)
        df.reset_index(inplace=True)
        
        # Rename Date/Datetime to timestamp
        if 'Date' in df.columns:
            df.rename(columns={'Date': 'timestamp'}, inplace=True)
        elif 'Datetime' in df.columns:
            df.rename(columns={'Datetime': 'timestamp'}, inplace=True)

    except Exception as e:
        print(f"Error fetching data from Yahoo Finance for {ticker}: {e}")
        df = pd.DataFrame()

    # if we got no data, make a demo chart
    if df.empty:
        return create_demo_chart(ticker, period, end_date, error_msg="No data returned from Yahoo Finance.")

    # build chart
    fig = go.Figure()
    # Add volume bars first with lower opacity
    fig.add_trace(go.Bar(
        x=df['timestamp'], y=df['volume'], name='Volume', yaxis='y2', opacity=0.3
    ))
    # Add candlestick trace on top
    fig.add_trace(go.Candlestick(
        x=df['timestamp'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name='Price'
    ))
    title = f"{ticker} - {period.upper()} Chart"
    if end_date:
        title += f" (as of {pd.to_datetime(end_date).date()})"
    
    # Improved layout with better gap handling - different rangebreaks for different timeframes
    rangebreaks = []
    if "/" not in ticker and period not in ["1y"]:  # Only apply to stocks, not crypto, and not daily charts
        # For intraday charts, hide non-trading hours
        rangebreaks = [
            dict(bounds=["sat", "mon"]),  # Hide weekends
            dict(bounds=[16, 9.5], pattern="hour"),  # Hide non-trading hours (4PM to 9:30AM) - approximate
        ]
    elif period in ["1y"]:
        # For daily charts, just hide weekends
        rangebreaks = [
            dict(bounds=["sat", "mon"]),
        ]
    
    fig.update_layout(
        title=title,
        template="plotly_white",
        xaxis_rangeslider_visible=False,
        xaxis=dict(
            type='date',
            rangeslider_visible=False,
            rangebreaks=rangebreaks
        ),
        yaxis_title='Price',
        yaxis2=dict(title='Volume', overlaying='y', side='right', showgrid=False),
        height=400,
        margin=dict(l=40, r=40, t=40, b=40),
        autosize=True
    )
    return fig


def create_demo_chart(ticker, period="1y", end_date=None, error_msg=None):
    """Create a demo chart with random walk data"""
    # Updated points mapping to reflect new timeframes
    points_map = {"15m":160, "1d":96, "1w":48, "1mo":90, "1y":252}  # Updated 1d to reflect 5Min data
    points = points_map.get(period, 252)
    title_map = {
        "15m": "15 Minutes", "1d": "1 Day",
        "1w": "1 Week", "1mo": "1 Month", "1y": "1 Year"
    }
    title = f"{ticker} - {title_map.get(period, period)} Chart (Demo)"
    if end_date:
        title += f" (as of {end_date})"
    # Dates and prices
    end_dt = pd.to_datetime(end_date) if end_date else datetime.now()
    dates = pd.date_range(end=end_dt, periods=points)
    prices = [100 + random.uniform(-20,20)]
    for _ in range(1, points):
        delta = random.uniform(-2,2) + random.uniform(-0.5,0.7)
        prices.append(max(5, prices[-1] + delta))
    opens, highs, lows, closes, vols = [], [], [], prices.copy(), []
    for i, close in enumerate(closes):
        opens.append(closes[i-1] if i>0 else close)
        high = max(opens[i], close) + random.uniform(0.1,1)
        low  = min(opens[i], close) - random.uniform(0.1,1)
        vols.append(random.randint(100000,10000000))
        highs.append(high); lows.append(low)
    fig = go.Figure()
    # Add volume bars first with lower opacity
    fig.add_trace(go.Bar(x=dates, y=vols, name='Volume', yaxis='y2', opacity=0.3))
    # Add candlestick trace on top
    fig.add_trace(go.Candlestick(x=dates, open=opens, high=highs, low=lows, close=closes, name='Price'))
    
    # Apply the same improved layout with gap handling - different rangebreaks for different timeframes
    rangebreaks = []
    if "/" not in ticker:  # Only apply to stocks, not crypto
        if period in ["15m", "1d"]:
            # For intraday charts, hide non-trading hours
            rangebreaks = [
                dict(bounds=["sat", "mon"]),  # Hide weekends
                dict(bounds=[20, 9.5], pattern="hour"),  # Hide non-trading hours (8PM to 9:30AM)
            ]
        elif period in ["1w", "1mo"]:
            # For weekly/monthly charts, only hide weekends
            rangebreaks = [
                dict(bounds=["sat", "mon"]),  # Hide weekends
            ]
        # For 1y charts, no rangebreaks to avoid issues with daily data
    
    fig.update_layout(
        title=title, 
        template="plotly_white", 
        xaxis_rangeslider_visible=False,
        xaxis=dict(
            type='date',
            rangeslider_visible=False,
            rangebreaks=rangebreaks
        ),
        yaxis_title='Price', 
        yaxis2=dict(title='Volume', overlaying='y', side='right'),
        height=400, 
        margin=dict(l=40,r=40,t=40,b=40), 
        autosize=True
    )
    if error_msg:
        fig.add_annotation(x=0.5,y=0.1,xref='paper',yref='paper',text=f"DEMO DATA: {error_msg}",
                           showarrow=False,font=dict(color='red',size=12),
                           bgcolor='rgba(255,255,255,0.7)',bordercolor='red',borderwidth=1)
    return fig


def create_welcome_chart():
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0,1,2,3], y=[1,3,2,4], mode='lines', name='Welcome'))
    fig.update_layout(
        title="Welcome to TradingAgents", template="plotly_white",
        annotations=[dict(x=1.5,y=2.5,xref='x',yref='y',text="Enter a ticker symbol and click 'Start Analysis'",
                         showarrow=True,arrowhead=1,ax=0,ay=-40)],
        height=400, margin=dict(l=40,r=40,t=40,b=40), autosize=True
    )
    return fig
