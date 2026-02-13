
import glob
import os
import datetime
import pandas as pd
import sys

def test_backtest_logic(ticker):
    print(f"Testing backtest for {ticker}...")
    
    # Define Date Range (Last 60 days)
    # Using the environment date: 2026-02-12
    today = datetime.date(2026, 2, 12)
    start_date = today - datetime.timedelta(days=60)
    end_date = today
    
    print(f"Date range: {start_date} to {end_date}")
    
    # Load BigFlow Data
    bigflow_files = glob.glob("data/bigflow/bigflow_*.csv")
    print(f"Found {len(bigflow_files)} files in data/bigflow/")
    
    all_flow_data = []
    
    for f in bigflow_files:
        try:
            basename = os.path.basename(f)
            # expected format: bigflow_YYYY-MM-DD.csv
            date_str = basename.replace("bigflow_", "").replace(".csv", "")
            file_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            
            if start_date <= file_date <= end_date:
                df = pd.read_csv(f)
                # Filter by ticker
                if 'ticker' in df.columns:
                    # Case insensitive check
                    df_ticker = df[df['ticker'] == ticker].copy()
                    if not df_ticker.empty:
                        print(f"Found {len(df_ticker)} records in {basename}")
                        df_ticker['date'] = file_date
                        all_flow_data.append(df_ticker)
        except Exception as e:
            print(f"Error processing {f}: {e}")
            continue
            
    if not all_flow_data:
        print(f"No BigFlow data found for {ticker} in the last 60 days.")
        return
        
    bigflow_df = pd.concat(all_flow_data, ignore_index=True)
    print(f"Total records found: {len(bigflow_df)}")
    
    # Check premium column
    print("Premium column sample:", bigflow_df['premium'].head())
    
    if 'spot' in bigflow_df.columns:
        print("Spot column sample:", bigflow_df['spot'].head())
    else:
        print("Spot column missing!")

    bigflow_df['premium'] = pd.to_numeric(bigflow_df['premium'], errors='coerce')
    print("Numeric premium sum:", bigflow_df['premium'].sum())

if __name__ == "__main__":
    test_backtest_logic("NVDA")
    test_backtest_logic("TSM")
