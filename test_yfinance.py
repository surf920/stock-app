
import yfinance as yf
import pandas as pd

try:
    tickers = {
        'BIZD': 'BDC指数 (信用)',
        'HYG': 'ハイイールド債',
        'DX-Y.NYB': 'ドル指数 (DXY)',
        'IGV': 'SaaS ETF',
        '^GSPC': 'S&P 500',
        'BTC-USD': 'Bitcoin',
        'INTU': 'Intuit',
        'CRM': 'Salesforce',
        'ADBE': 'Adobe'
    }
    
    print("Fetching data...")
    data = yf.download(list(tickers.keys()), period="1y", interval="1d")
    print("Data fetched successfully.")
    print(data.head())
    
    if isinstance(data.columns, pd.MultiIndex):
        try:
            data = data['Close'] # Closeのみ取得
            print("Successfully extracted Close prices.")
        except KeyError:
            # Adj Closeの場合などの保険
            data = data.xs('Close', level=0, axis=1, drop_level=True)
            print("Extracted using xs.")

    print(data.tail())

except Exception as e:
    print(f"Error: {e}")
