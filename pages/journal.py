import streamlit as st
from database import get_connection

def load_css():
    with open("style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
load_css()
if st.session_state.user_id is None:
    st.switch_page("app.py")

conn = get_connection()
cursor = conn.cursor(dictionary=True)

cursor.execute("""
    SELECT J.journal_id, J.note_text, J.created_at,
           J.ticker, S.company_name,
           T.transaction_type, T.quantity, T.price_at_transaction
    FROM JOURNAL J
    JOIN STOCKS S ON J.ticker = S.ticker
    JOIN TRANSACTIONS T ON J.transaction_id = T.transaction_id
    WHERE J.user_id = %s
    ORDER BY J.created_at DESC
""", (st.session_state.user_id,))
entries = cursor.fetchall()

cursor.execute("""
    SELECT T.transaction_id, T.ticker, T.transaction_type,
           T.quantity, T.price_at_transaction, S.company_name
    FROM TRANSACTIONS T
    JOIN STOCKS S ON T.ticker = S.ticker
    WHERE T.user_id = %s
    ORDER BY T.timestamp DESC
""", (st.session_state.user_id,))
transactions = cursor.fetchall()
cursor.close()
conn.close()

st.title("Trading Journal")
st.divider()

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("My journal entries")
    if entries:
        for e in entries:
            border = "#00b386" if e['transaction_type'] == 'BUY' else "#e74c3c"
            badge = "🟢 BUY" if e['transaction_type'] == 'BUY' else "🔴 SELL"
            st.markdown(f"""
            <div style='padding:14px;border-radius:8px;border-left:3px solid {border};
                        background:#f9f9f9;margin-bottom:12px'>
                <div style='display:flex;justify-content:space-between;margin-bottom:6px'>
                    <strong>{e['company_name']} ({e['ticker']})</strong>
                    <span style='font-size:12px;color:gray'>{e['created_at']}</span>
                </div>
                <div style='font-size:13px;color:gray;margin-bottom:8px'>
                    {badge} · {e['quantity']} shares @ ₹{e['price_at_transaction']}
                </div>
                <div style='font-size:14px;line-height:1.6'>{e['note_text']}</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No journal entries yet. Write your first note when you make a trade!")

with col2:
    st.subheader("Write a note")
    if transactions:
        txn_options = [
            f"{t['transaction_type']} {t['quantity']} {t['ticker']} @ ₹{t['price_at_transaction']}"
            for t in transactions
        ]
        selected_txn = st.selectbox("Link to trade", txn_options)
        txn_index = txn_options.index(selected_txn)
        txn_id = transactions[txn_index]['transaction_id']
        txn_ticker = transactions[txn_index]['ticker']

        note = st.text_area("Your note", height=200,
                            placeholder="What was your reasoning? What did you learn?")

        if st.button("Save note", use_container_width=True, type="primary"):
            if note.strip():
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO JOURNAL (user_id, ticker, transaction_id, note_text)
                        VALUES (%s, %s, %s, %s)
                    """, (st.session_state.user_id, txn_ticker, txn_id, note))
                    conn.commit()
                    cursor.close()
                    conn.close()
                    st.success("Note saved!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.warning("Please write something before saving.")
    else:
        st.info("Make a trade first to write journal notes.")