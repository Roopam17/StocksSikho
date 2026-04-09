import streamlit as st
from database import get_connection

if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'user_name' not in st.session_state:
    st.session_state.user_name = None

def load_css():
    with open("style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
load_css()

if st.session_state.user_id is None:
    st.switch_page("app.py")

conn = get_connection()
cursor = conn.cursor(dictionary=True)

cursor.execute("""
    SELECT U.user_id, U.name, U.virtual_balance,
           ROUND(SUM(T.quantity * S.current_price), 2) AS holdings_value,
           ROUND(SUM(T.quantity * T.price_at_transaction), 2) AS amount_invested,
           ROUND(SUM(T.quantity * S.current_price) - 
                 SUM(T.quantity * T.price_at_transaction), 2) AS total_pnl,
           ROUND(((SUM(T.quantity * S.current_price) - 
                   SUM(T.quantity * T.price_at_transaction)) / 100000) * 100, 2) AS return_pct,
           COUNT(T.transaction_id) AS total_trades
    FROM USERS U
    JOIN TRANSACTIONS T ON U.user_id = T.user_id
    JOIN STOCKS S ON T.ticker = S.ticker
    WHERE T.transaction_type = 'BUY'
    GROUP BY U.user_id, U.name, U.virtual_balance
    ORDER BY total_pnl DESC
""")
leaderboard = cursor.fetchall()
cursor.close()
conn.close()

st.title("Leaderboard")
st.markdown("Rankings based on total profit/loss across all users.")
st.divider()

medals = ["🥇", "🥈", "🥉"]

for i, row in enumerate(leaderboard):
    is_me = row['user_id'] == st.session_state.user_id
    border = "2px solid #00b386" if is_me else "0.5px solid #ddd"
    medal = medals[i] if i < 3 else f"#{i+1}"
    pnl_color = "green" if row['total_pnl'] >= 0 else "red"
    pnl_sign = "+" if row['total_pnl'] >= 0 else ""
    you = " (You)" if is_me else ""

    st.markdown(f"""
    <div style='padding:16px;border-radius:10px;border:{border};
                margin-bottom:10px;background:{"#f0fff8" if is_me else "white"}'>
        <div style='display:flex;justify-content:space-between;align-items:center'>
            <div style='display:flex;align-items:center;gap:14px'>
                <span style='font-size:22px'>{medal}</span>
                <div>
                    <div style='font-size:15px;font-weight:500'>{row['name']}{you}</div>
                    <div style='font-size:12px;color:gray'>{row['total_trades']} trades</div>
                </div>
            </div>
            <div style='text-align:right'>
                <div style='font-size:16px;font-weight:500;color:{pnl_color}'>
                    {pnl_sign}₹{row['total_pnl']:,.2f}
                </div>
                <div style='font-size:12px;color:{pnl_color}'>
                    {pnl_sign}{row['return_pct']}% return
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

st.divider()
st.subheader("Your stats")
my_row = next((r for r in leaderboard if r['user_id'] == st.session_state.user_id), None)
if my_row:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Your rank", f"#{leaderboard.index(my_row)+1} of {len(leaderboard)}")
    col2.metric("Total P&L", f"₹{my_row['total_pnl']:,.2f}")
    col3.metric("Return", f"{my_row['return_pct']}%")
    col4.metric("Total trades", my_row['total_trades'])
else:
    st.info("Make some trades to appear on the leaderboard!")