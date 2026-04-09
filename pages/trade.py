import streamlit as st
import yfinance as yf
from database import get_connection
from stock_service import fetch_and_update_prices

def load_css():
    with open("style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
load_css()
if st.session_state.user_id is None:
    st.switch_page("app.py")

@st.cache_data(ttl=300)
def refresh_prices():
    fetch_and_update_prices()
    return True

refresh_prices()

def search_and_add_stock(query):
    query = query.upper().strip()
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM STOCKS WHERE ticker = %s OR company_name LIKE %s",
        (query, f'%{query}%')
    )
    existing = cursor.fetchall()
    if existing:
        cursor.close()
        conn.close()
        return existing
    nse_ticker = query + ".NS"
    try:
        data = yf.Ticker(nse_ticker)
        hist = data.history(period="1y")
        info = data.info
        if hist.empty:
            cursor.close()
            conn.close()
            return []
        current_price = round(float(hist['Close'].iloc[-1]), 2)
        week_52_high = round(float(hist['High'].max()), 2)
        week_52_low = round(float(hist['Low'].min()), 2)
        company_name = info.get('longName', query)
        sector = info.get('sector', 'Others')
        cursor.execute("""
            INSERT IGNORE INTO STOCKS
            (ticker, company_name, sector, current_price, week_52_high, week_52_low)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (query, company_name, sector, current_price, week_52_high, week_52_low))
        conn.commit()
        cursor.execute("SELECT * FROM STOCKS WHERE ticker = %s", (query,))
        new_stock = cursor.fetchall()
        cursor.close()
        conn.close()
        return new_stock
    except Exception as e:
        cursor.close()
        conn.close()
        return []

conn = get_connection()
cursor = conn.cursor(dictionary=True)
cursor.execute(
    "SELECT virtual_balance FROM USERS WHERE user_id = %s",
    (st.session_state.user_id,)
)
user = cursor.fetchone()
cursor.execute("SELECT * FROM STOCKS ORDER BY ticker")
all_stocks = cursor.fetchall()
cursor.close()
conn.close()

st.title("Trade")
st.metric("Available Balance", f"₹{float(user['virtual_balance']):,.2f}")
st.divider()

col1, col2 = st.columns([1.2, 1])

with col1:
    st.subheader("Search Stocks")
    st.caption("Search any NSE stock by ticker — e.g. ZOMATO, ADANIENT, BAJFINANCE")
    search = st.text_input("Search by ticker or company name",
                           placeholder="e.g. TCS, ZOMATO, INFY")
    if search:
        with st.spinner(f"Searching for {search.upper()}..."):
            results = search_and_add_stock(search)
        if results:
            stocks_to_show = results
        else:
            st.warning(f"No stock found for '{search}'. Try the exact NSE ticker.")
            stocks_to_show = []
    else:
        stocks_to_show = all_stocks

    for s in stocks_to_show:
        with st.container():
            c1, c2, c3 = st.columns([3, 2, 1])
            c1.markdown(f"**{s['ticker']}**  \n{s['company_name']}")
            c2.markdown(f"₹{float(s['current_price']):,.2f}  \n*{s['sector']}*")
            if c3.button("Trade", key=f"trade_{s['ticker']}"):
                st.session_state.selected_stock = s['ticker']
                st.session_state.selected_price = float(s['current_price'])
                st.session_state.selected_name = s['company_name']
            st.divider()

with col2:
    st.subheader("Place Order")

    if 'selected_stock' not in st.session_state:
        st.info("Select a stock from the left to trade")
    else:
        ticker = st.session_state.selected_stock
        price = st.session_state.selected_price
        name = st.session_state.get('selected_name', ticker)

        st.markdown(f"### {ticker}")
        st.markdown(f"{name}")
        st.markdown(f"Current price: **₹{price:,.2f}**")
        st.divider()

        order_type = st.radio("Order type", ["BUY", "SELL"], horizontal=True)
        quantity = st.number_input("Quantity", min_value=1, value=1)
        total = round(quantity * price, 2)
        st.markdown(f"**Total: ₹{total:,.2f}**")

        if order_type == 'BUY':
            remaining = round(float(user['virtual_balance']) - total, 2)
            if remaining < 0:
                st.error(f"Insufficient balance! Need ₹{total:,.2f}, have ₹{float(user['virtual_balance']):,.2f}")
            else:
                st.caption(f"Balance after trade: ₹{remaining:,.2f}")

        note = st.text_area("Journal note (why this trade?)",
                            placeholder="e.g. Buying TCS because Q3 results were strong...")

        if st.button("Confirm Order", use_container_width=True, type="primary"):
            try:
                conn = get_connection()
                cursor = conn.cursor()

                if order_type == 'BUY':
                    if float(user['virtual_balance']) < total:
                        st.error("Insufficient balance!")
                    else:
                        cursor.execute("""
                            INSERT INTO TRANSACTIONS
                            (user_id, ticker, transaction_type, quantity, price_at_transaction)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (st.session_state.user_id, ticker, order_type, quantity, price))
                        txn_id = cursor.lastrowid
                        if note.strip():
                            cursor.execute("""
                                INSERT INTO JOURNAL (user_id, ticker, transaction_id, note_text)
                                VALUES (%s, %s, %s, %s)
                            """, (st.session_state.user_id, ticker, txn_id, note))
                        conn.commit()
                        st.success(f"Successfully bought {quantity} shares of {ticker}!")
                        st.rerun()

                else:
                    cursor.execute("""
                        SELECT COALESCE(SUM(CASE
                            WHEN transaction_type='BUY' THEN quantity
                            ELSE -quantity
                        END), 0) AS net_qty
                        FROM TRANSACTIONS
                        WHERE user_id = %s AND ticker = %s
                    """, (st.session_state.user_id, ticker))
                    result = cursor.fetchone()
                    net_qty = int(result[0]) if result[0] else 0

                    if net_qty <= 0:
                        st.error(f"You do not own any shares of {ticker}!")
                    elif quantity > net_qty:
                        st.error(f"You only own {net_qty} shares of {ticker}!")
                    else:
                        cursor.execute("""
                            INSERT INTO TRANSACTIONS
                            (user_id, ticker, transaction_type, quantity, price_at_transaction)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (st.session_state.user_id, ticker, order_type, quantity, price))
                        txn_id = cursor.lastrowid
                        if note.strip():
                            cursor.execute("""
                                INSERT INTO JOURNAL (user_id, ticker, transaction_id, note_text)
                                VALUES (%s, %s, %s, %s)
                            """, (st.session_state.user_id, ticker, txn_id, note))
                        conn.commit()
                        st.success(f"Successfully sold {quantity} shares of {ticker}!")
                        st.rerun()

                cursor.close()
                conn.close()

            except Exception as e:
                st.error(f"Error: {e}")