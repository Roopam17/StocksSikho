import streamlit as st
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

conn = get_connection()
cursor = conn.cursor(dictionary=True)

cursor.execute("SELECT * FROM USERS WHERE user_id = %s", (st.session_state.user_id,))
user = cursor.fetchone()

cursor.execute("""
    SELECT 
        S.company_name, 
        S.ticker, 
        S.sector, 
        S.current_price,
        S.week_52_high,
        S.week_52_low,
        SUM(CASE WHEN T.transaction_type='BUY' THEN T.quantity ELSE -T.quantity END) AS net_quantity,
        AVG(CASE WHEN T.transaction_type='BUY' THEN T.price_at_transaction END) AS avg_buy_price
    FROM TRANSACTIONS T
    JOIN STOCKS S ON T.ticker = S.ticker
    WHERE T.user_id = %s
    GROUP BY S.company_name, S.ticker, S.sector, S.current_price, S.week_52_high, S.week_52_low
    HAVING net_quantity > 0
""", (st.session_state.user_id,))
holdings = cursor.fetchall()

cursor.execute("""
    SELECT S.company_name, T.ticker, T.transaction_type,
           T.quantity, T.price_at_transaction, T.timestamp
    FROM TRANSACTIONS T
    JOIN STOCKS S ON T.ticker = S.ticker
    WHERE T.user_id = %s
    ORDER BY T.timestamp DESC LIMIT 5
""", (st.session_state.user_id,))
recent = cursor.fetchall()
cursor.close()
conn.close()

total_current_value = sum(
    float(h['net_quantity']) * float(h['current_price']) 
    for h in holdings
)
total_invested = sum(
    float(h['net_quantity']) * float(h['avg_buy_price']) 
    for h in holdings
)
total_pnl = round(total_current_value - total_invested, 2)
total_pnl_pct = round((total_pnl / total_invested * 100), 2) if total_invested > 0 else 0
portfolio_value = round(float(user['virtual_balance']) + total_current_value, 2)

st.title("Dashboard")
st.caption("Prices refresh every 5 minutes from NSE")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Portfolio Value", f"₹{portfolio_value:,.2f}")
col2.metric(
    "Total P&L", 
    f"₹{total_pnl:,.2f}",
    delta=f"{total_pnl_pct}%"
)
col3.metric("Cash Balance", f"₹{float(user['virtual_balance']):,.2f}")
col4.metric("Holdings", len(holdings))

st.divider()

col1, col2 = st.columns(2)

with col1:
    st.subheader("Your Holdings")
    if holdings:
        for h in holdings:
            current = float(h['current_price'])
            avg_buy = float(h['avg_buy_price'])
            qty = float(h['net_quantity'])
            pnl = round((current - avg_buy) * qty, 2)
            pnl_pct = round(((current - avg_buy) / avg_buy) * 100, 2)
            current_value = round(current * qty, 2)
            color = "green" if pnl >= 0 else "red"
            arrow = "▲" if pnl >= 0 else "▼"

            st.markdown(f"""
            <div style='padding:14px;border-radius:10px;border:0.5px solid #ddd;margin-bottom:10px'>
                <div style='display:flex;justify-content:space-between;align-items:center'>
                    <div>
                        <strong style='font-size:15px'>{h['ticker']}</strong>
                        <span style='color:gray;font-size:12px'> · {h['company_name']}</span>
                    </div>
                    <span style='color:{color};font-weight:500'>{arrow} ₹{pnl:,.2f} ({pnl_pct}%)</span>
                </div>
                <div style='color:gray;font-size:13px;margin-top:6px'>
                    {int(qty)} shares · Avg buy ₹{avg_buy:,.2f} · Now ₹{current:,.2f}
                </div>
                <div style='font-size:13px;margin-top:4px'>
                    Current value: <strong>₹{current_value:,.2f}</strong> · Sector: {h['sector']}
                </div>
                <div style='font-size:12px;color:gray;margin-top:4px'>
                    52W High: ₹{float(h['week_52_high']):,.2f} · 52W Low: ₹{float(h['week_52_low']):,.2f}
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No holdings yet. Go to Trade to buy your first stock!")

with col2:
    st.subheader("Recent Transactions")
    if recent:
        for r in recent:
            badge_color = "#00b386" if r['transaction_type'] == 'BUY' else "#e74c3c"
            badge_text = "BUY" if r['transaction_type'] == 'BUY' else "SELL"
            st.markdown(f"""
            <div style='padding:12px;border-radius:10px;border:0.5px solid #ddd;margin-bottom:8px'>
                <div style='display:flex;justify-content:space-between;align-items:center'>
                    <div>
                        <strong>{r['ticker']}</strong>
                        <span style='background:{badge_color};color:white;font-size:11px;
                              padding:2px 8px;border-radius:20px;margin-left:8px'>{badge_text}</span>
                    </div>
                    <span style='font-size:13px;color:gray'>{str(r['timestamp'])[:10]}</span>
                </div>
                <div style='color:gray;font-size:13px;margin-top:4px'>
                    {r['quantity']} shares @ ₹{float(r['price_at_transaction']):,.2f}
                </div>
                <div style='font-size:13px'>{r['company_name']}</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No transactions yet.")

    st.divider()
    st.subheader("Portfolio summary")
    st.markdown(f"""
    <div style='padding:14px;border-radius:10px;background:#f9f9f9;border:0.5px solid #ddd'>
        <div style='display:flex;justify-content:space-between;margin-bottom:8px'>
            <span style='color:gray;font-size:13px'>Total invested</span>
            <span style='font-size:13px;font-weight:500'>₹{total_invested:,.2f}</span>
        </div>
        <div style='display:flex;justify-content:space-between;margin-bottom:8px'>
            <span style='color:gray;font-size:13px'>Current value</span>
            <span style='font-size:13px;font-weight:500'>₹{total_current_value:,.2f}</span>
        </div>
        <div style='display:flex;justify-content:space-between;margin-bottom:8px'>
            <span style='color:gray;font-size:13px'>Total P&L</span>
            <span style='font-size:13px;font-weight:500;color:{"green" if total_pnl >= 0 else "red"}'>
                ₹{total_pnl:,.2f} ({total_pnl_pct}%)
            </span>
        </div>
        <div style='display:flex;justify-content:space-between'>
            <span style='color:gray;font-size:13px'>Cash remaining</span>
            <span style='font-size:13px;font-weight:500'>₹{float(user['virtual_balance']):,.2f}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)