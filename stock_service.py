import yfinance as yf
import time
from database import get_connection

TICKER_MAP = {
    'TCS': 'TCS.NS',
    'INFY': 'INFY.NS',
    'RELIANCE': 'RELIANCE.NS',
    'HDFCBANK': 'HDFCBANK.NS',
    'WIPRO': 'WIPRO.NS',
    'ICICIBANK': 'ICICIBANK.NS',
    'ITC': 'ITC.NS',
    'ASIANPAINT': 'ASIANPAINT.NS',
    'TITAN': 'TITAN.NS',
    'M&M': 'M&M.NS',
    'ETERNAL': 'ETERNAL.NS',
    'BAJFINANCE': 'BAJFINANCE.NS',
}

def get_nse_ticker(ticker):
    return TICKER_MAP.get(ticker, ticker + '.NS')

def fetch_and_update_prices():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT ticker FROM STOCKS")
    stocks = cursor.fetchall()

    for stock in stocks:
        ticker = stock['ticker']
        nse_ticker = get_nse_ticker(ticker)
        try:
            data = yf.Ticker(nse_ticker)
            hist = data.history(period="5d")

            if hist is None or hist.empty:
                print(f"No data for {ticker}")
                continue

            hist_clean = hist.dropna(subset=['Close'])

            if hist_clean.empty:
                print(f"No clean data for {ticker}")
                continue

            current_price = round(float(hist_clean['Close'].iloc[-1]), 2)

            hist_year = data.history(period="1y")
            if hist_year is not None and not hist_year.empty:
                hist_year_clean = hist_year.dropna(subset=['High', 'Low'])
                week_52_high = round(float(hist_year_clean['High'].max()), 2)
                week_52_low = round(float(hist_year_clean['Low'].min()), 2)
            else:
                week_52_high = current_price
                week_52_low = current_price

            cursor.execute("""
                UPDATE STOCKS
                SET current_price = %s,
                    week_52_high = %s,
                    week_52_low = %s
                WHERE ticker = %s
            """, (current_price, week_52_high, week_52_low, ticker))

            print(f"Updated {ticker}: ₹{current_price}")
            time.sleep(0.5)

        except Exception as e:
            print(f"Could not fetch {ticker}: {e}")
            time.sleep(1)

    conn.commit()
    cursor.close()
    conn.close()

def get_live_price(ticker):
    try:
        nse_ticker = get_nse_ticker(ticker)
        data = yf.Ticker(nse_ticker)
        hist = data.history(period="5d")
        if hist is not None and not hist.empty:
            hist_clean = hist.dropna(subset=['Close'])
            if not hist_clean.empty:
                return round(float(hist_clean['Close'].iloc[-1]), 2)
    except Exception as e:
        print(f"Live price error for {ticker}: {e}")
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT current_price FROM STOCKS WHERE ticker = %s", (ticker,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return float(result['current_price']) if result else 0.0