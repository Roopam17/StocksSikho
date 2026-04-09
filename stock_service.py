import yfinance as yf
from database import get_connection

NSE_SUFFIX = ".NS"

def fetch_and_update_prices():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT ticker FROM STOCKS")
    stocks = cursor.fetchall()
    
    for stock in stocks:
        ticker = stock['ticker']
        nse_ticker = ticker + NSE_SUFFIX
        
        try:
            data = yf.Ticker(nse_ticker)
            info = data.fast_info
            
            current_price = round(float(info.last_price), 2)
            week_52_high = round(float(info.fifty_two_week_high), 2)
            week_52_low = round(float(info.fifty_two_week_low), 2)
            
            cursor.execute("""
                UPDATE STOCKS 
                SET current_price = %s,
                    week_52_high = %s,
                    week_52_low = %s
                WHERE ticker = %s
            """, (current_price, week_52_high, week_52_low, ticker))
            
            print(f"Updated {ticker}: ₹{current_price}")
            
        except Exception as e:
            print(f"Could not fetch {ticker}: {e}")