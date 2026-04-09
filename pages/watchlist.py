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

cursor.execute("""
    SELECT W.watchlist_id, W.ticker, S.company_name, S.current_price,
           W.target_price, W.alert_status, W.added_at,
           ROUND((S.current_price / W.target_price) * 100, 1) AS progress
    FROM WATCHLIST W
    JOIN STOCKS S ON W.ticker = S.ticker
    WHERE W.user_id = %s
    ORDER BY W.added_at DESC
""", (st.session_state.user_id,))
watchlist = cursor.fetchall()

cursor.execute("SELECT * FROM STOCKS ORDER BY company_name")
stocks = cursor.fetchall()
cursor.close()
conn.close()

st.title("Watchlist")

triggered = [w for w in watchlist if w['alert_status'] == 'TRIGGERED']
if triggered:
    st.success(f"Target reached for {len(triggered)} stock(s)!")
    for t in triggered:
        st.markdown(f"""
        <div style='padding:12px;border-radius:8px;background:#e6f7f2;
                    border:1px solid #00b386;margin-bottom:8px'>
            <div style='display:flex;justify-content:space-between;align-items:center'>
                <div>
                    <strong style='color:#00856a;font-size:15px'>
                        Target hit — {t['ticker']}
                    </strong>
                    <div style='color:#00856a;font-size:13px'>{t['company_name']}</div>
                </div>
                <div style='text-align:right'>
                    <div style='color:#00856a;font-weight:500'>
                        Current: ₹{float(t['current_price']):,.2f}
                    </div>
                    <div style='color:#00856a;font-size:13px'>
                        Target was: ₹{float(t['target_price']):,.2f}
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

st.divider()

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Your watchlist")

    pending = [w for w in watchlist if w['alert_status'] == 'PENDING']
    
    if not watchlist:
        st.info("No stocks in your watchlist yet.")
    
    if triggered:
        st.markdown("#### Targets reached")
        for w in triggered:
            st.markdown(f"""
            <div style='padding:14px;border-radius:10px;border:1px solid #00b386;
                        background:#f0fff8;margin-bottom:10px'>
                <div style='display:flex;justify-content:space-between;align-items:center'>
                    <div>
                        <strong>{w['company_name']} ({w['ticker']})</strong>
                        <span style='background:#00b386;color:white;font-size:11px;
                              padding:2px 8px;border-radius:20px;margin-left:8px'>
                              Target Hit
                        </span>
                    </div>
                    <div style='text-align:right'>
                        <div style='font-weight:500;color:#00856a'>
                            ₹{float(w['current_price']):,.2f}
                        </div>
                        <div style='font-size:12px;color:gray'>
                            Target: ₹{float(w['target_price']):,.2f}
                        </div>
                    </div>
                </div>
                <div style='background:#eee;border-radius:4px;height:6px;margin-top:10px'>
                    <div style='background:#00b386;width:100%;height:6px;border-radius:4px'></div>
                </div>
                <div style='font-size:12px;color:#00856a;margin-top:4px'>
                    100% — Target reached!
                </div>
            </div>
            """, unsafe_allow_html=True)

    if pending:
        st.markdown("#### Watching")
        for w in pending:
            progress = min(float(w['progress']), 100)
            remaining = round(float(w['target_price']) - float(w['current_price']), 2)
            st.markdown(f"""
            <div style='padding:14px;border-radius:10px;border:0.5px solid #ddd;
                        margin-bottom:10px'>
                <div style='display:flex;justify-content:space-between;align-items:center'>
                    <div>
                        <strong>{w['company_name']} ({w['ticker']})</strong>
                    </div>
                    <div style='text-align:right'>
                        <div style='font-weight:500'>₹{float(w['current_price']):,.2f}</div>
                        <div style='font-size:12px;color:gray'>
                            Target: ₹{float(w['target_price']):,.2f}
                        </div>
                    </div>
                </div>
                <div style='background:#eee;border-radius:4px;height:6px;margin-top:10px'>
                    <div style='background:#00b386;width:{progress}%;
                                height:6px;border-radius:4px'></div>
                </div>
                <div style='display:flex;justify-content:space-between;
                            font-size:12px;color:gray;margin-top:4px'>
                    <span>{progress}% of target</span>
                    <span>₹{remaining:,.2f} away</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

with col2:
    st.subheader("Add to watchlist")
    
    search_watch = st.text_input("Search stock", placeholder="e.g. ZOMATO, TCS")
    
    if search_watch:
        filtered = [s for s in stocks if 
                   search_watch.upper() in s['ticker'] or 
                   search_watch.lower() in s['company_name'].lower()]
    else:
        filtered = stocks
    
    ticker_options = [f"{s['ticker']} — {s['company_name']}" for s in filtered]
    
    if ticker_options:
        selected = st.selectbox("Select stock", ticker_options)
        ticker = selected.split(' — ')[0]
        
        selected_stock = next(s for s in stocks if s['ticker'] == ticker)
        st.caption(f"Current price: ₹{float(selected_stock['current_price']):,.2f}")
        
        target = st.number_input("Target price (₹)", 
                                  min_value=1.0, 
                                  value=float(selected_stock['current_price']) * 1.1,
                                  step=10.0)
        
        upside = round(((target - float(selected_stock['current_price'])) / 
                        float(selected_stock['current_price'])) * 100, 1)
        st.caption(f"Expected upside: {upside}%")
        
        if st.button("Add to watchlist", use_container_width=True, type="primary"):
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO WATCHLIST (user_id, ticker, target_price, alert_status)
                    VALUES (%s, %s, %s, 'PENDING')
                """, (st.session_state.user_id, ticker, target))
                conn.commit()
                cursor.close()
                conn.close()
                st.success(f"{ticker} added to watchlist!")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        st.warning("No stocks found. Try a different search.")

    st.divider()
    st.subheader("Remove")
    
    if watchlist:
        remove_options = [f"{w['ticker']} — target ₹{float(w['target_price']):,.2f}" 
                         for w in watchlist]
        to_remove = st.selectbox("Select to remove", remove_options)
        remove_ticker = to_remove.split(' — ')[0]
        
        if st.button("Remove from watchlist", use_container_width=True):
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM WATCHLIST 
                WHERE user_id = %s AND ticker = %s
            """, (st.session_state.user_id, remove_ticker))
            conn.commit()
            cursor.close()
            conn.close()
            st.success(f"{remove_ticker} removed!")
            st.rerun()
    else:
        st.caption("Nothing to remove yet.")