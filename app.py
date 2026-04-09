from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from database import get_connection
import yfinance as yf

app = Flask(__name__)
app.secret_key = 'stocksikho_secret_key_2026'

@app.context_processor
def inject_ticker_stocks():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT ticker, current_price FROM STOCKS ORDER BY ticker LIMIT 10")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        ticker_stocks = [{'ticker': r['ticker'], 'current_price': float(r['current_price'])} for r in rows]
        return dict(ticker_stocks=ticker_stocks)
    except Exception as e:
        print(f"Ticker error: {e}")
        return dict(ticker_stocks=[])

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM USERS WHERE email=%s AND password=%s", (email, password))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if user:
            session['user_id'] = user['user_id']
            session['user_name'] = user['name']
            return redirect(url_for('dashboard'))
        else:
            error = "Invalid email or password"
    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    success = None
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        age = request.form['age']
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO USERS (name, email, password, age, virtual_balance) VALUES (%s,%s,%s,%s,100000.00)",
                (name, email, password, age)
            )
            conn.commit()
            cursor.close()
            conn.close()
            success = "Account created! Please login."
        except Exception as e:
            error = str(e)
    return render_template('login.html', error=error, success=success)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM USERS WHERE user_id = %s", (session['user_id'],))
    user = cursor.fetchone()
    cursor.execute("""
        SELECT S.company_name, S.ticker, S.sector,
               S.current_price, S.week_52_high, S.week_52_low,
               SUM(CASE WHEN T.transaction_type='BUY' THEN T.quantity ELSE -T.quantity END) AS net_quantity,
               AVG(CASE WHEN T.transaction_type='BUY' THEN T.price_at_transaction END) AS avg_buy_price
        FROM TRANSACTIONS T
        JOIN STOCKS S ON T.ticker = S.ticker
        WHERE T.user_id = %s
        GROUP BY S.company_name, S.ticker, S.sector,
                 S.current_price, S.week_52_high, S.week_52_low
        HAVING net_quantity > 0
    """, (session['user_id'],))
    holdings = cursor.fetchall()
    cursor.execute("""
        SELECT S.company_name, T.ticker, T.transaction_type,
               T.quantity, T.price_at_transaction, T.timestamp
        FROM TRANSACTIONS T
        JOIN STOCKS S ON T.ticker = S.ticker
        WHERE T.user_id = %s
        ORDER BY T.timestamp DESC LIMIT 5
    """, (session['user_id'],))
    recent = cursor.fetchall()
    cursor.close()
    conn.close()
    for h in holdings:
        h['pnl'] = round((float(h['current_price']) - float(h['avg_buy_price'])) * float(h['net_quantity']), 2)
        h['pnl_pct'] = round(((float(h['current_price']) - float(h['avg_buy_price'])) / float(h['avg_buy_price'])) * 100, 2)
        h['current_value'] = round(float(h['current_price']) * float(h['net_quantity']), 2)
    total_pnl = round(sum(h['pnl'] for h in holdings), 2)
    total_invested = round(sum(float(h['avg_buy_price']) * float(h['net_quantity']) for h in holdings), 2)
    portfolio_value = round(float(user['virtual_balance']) + sum(h['current_value'] for h in holdings), 2)
    return render_template('dashboard.html',
        user=user, holdings=holdings, recent=recent,
        total_pnl=total_pnl, total_invested=total_invested,
        portfolio_value=portfolio_value)

@app.route('/trade', methods=['GET', 'POST'])
def trade():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT virtual_balance FROM USERS WHERE user_id = %s", (session['user_id'],))
    user = cursor.fetchone()
    cursor.execute("SELECT * FROM STOCKS ORDER BY ticker")
    stocks = cursor.fetchall()
    cursor.close()
    conn.close()
    message = None
    error = None
    if request.method == 'POST':
        ticker = request.form['ticker'].upper().strip()
        order_type = request.form['order_type']
        quantity = int(request.form['quantity'])
        note = request.form.get('note', '')
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM STOCKS WHERE ticker = %s", (ticker,))
        stock = cursor.fetchone()
        if stock and not error:
            price = float(stock['current_price'])
            total = price * quantity
            if order_type == 'BUY':
                if float(user['virtual_balance']) < total:
                    error = f"Insufficient balance! Need ₹{total:,.2f}"
                else:
                    cursor.execute("""
                        INSERT INTO TRANSACTIONS
                        (user_id, ticker, transaction_type, quantity, price_at_transaction)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (session['user_id'], ticker, order_type, quantity, price))
                    txn_id = cursor.lastrowid
                    if note.strip():
                        cursor.execute("""
                            INSERT INTO JOURNAL (user_id, ticker, transaction_id, note_text)
                            VALUES (%s, %s, %s, %s)
                        """, (session['user_id'], ticker, txn_id, note))
                    conn.commit()
                    message = f"Successfully bought {quantity} shares of {ticker}!"
            else:
                cursor.execute("""
                    SELECT COALESCE(SUM(CASE
                        WHEN transaction_type='BUY' THEN quantity
                        ELSE -quantity
                    END), 0) AS net_qty
                    FROM TRANSACTIONS
                    WHERE user_id = %s AND ticker = %s
                """, (session['user_id'], ticker))
                result = cursor.fetchone()
                net_qty = int(result['net_qty']) if result['net_qty'] else 0
                if net_qty <= 0:
                    error = f"You do not own any shares of {ticker}!"
                elif quantity > net_qty:
                    error = f"You only own {net_qty} shares of {ticker}!"
                else:
                    cursor.execute("""
                        INSERT INTO TRANSACTIONS
                        (user_id, ticker, transaction_type, quantity, price_at_transaction)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (session['user_id'], ticker, order_type, quantity, price))
                    txn_id = cursor.lastrowid
                    if note.strip():
                        cursor.execute("""
                            INSERT INTO JOURNAL (user_id, ticker, transaction_id, note_text)
                            VALUES (%s, %s, %s, %s)
                        """, (session['user_id'], ticker, txn_id, note))
                    conn.commit()
                    message = f"Successfully sold {quantity} shares of {ticker}!"
        cursor.close()
        conn.close()
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT virtual_balance FROM USERS WHERE user_id = %s", (session['user_id'],))
        user = cursor.fetchone()
        cursor.execute("SELECT * FROM STOCKS ORDER BY ticker")
        stocks = cursor.fetchall()
        cursor.close()
        conn.close()
    return render_template('trade.html', user=user, stocks=stocks, message=message, error=error)

@app.route('/fetch_stock')
def fetch_stock():
    if 'user_id' not in session:
        return jsonify({'success': False})
    ticker = request.args.get('ticker', '').upper().strip()
    if not ticker:
        return jsonify({'success': False})
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM STOCKS WHERE ticker = %s", (ticker,))
        existing = cursor.fetchone()
        if existing:
            cursor.close()
            conn.close()
            return jsonify({'success': True, 'stock': {
                'ticker': existing['ticker'],
                'company_name': existing['company_name'],
                'sector': existing['sector'],
                'current_price': float(existing['current_price'])
            }})
        cursor.close()
        conn.close()
        nse_ticker = ticker + ".NS"
        data = yf.Ticker(nse_ticker)
        hist = data.history(period="5d")
        hist_clean = hist.dropna(subset=['Close'])
        if hist_clean.empty:
            return jsonify({'success': False})
        current_price = round(float(hist_clean['Close'].iloc[-1]), 2)
        week_52_high = round(float(hist_clean['High'].max()), 2)
        week_52_low = round(float(hist_clean['Low'].min()), 2)
        try:
            company_name = data.info.get('longName', ticker)
            sector = data.info.get('sector', 'Others')
        except:
            company_name = ticker
            sector = 'Others'
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            INSERT IGNORE INTO STOCKS
            (ticker, company_name, sector, current_price, week_52_high, week_52_low)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (ticker, company_name, sector, current_price, week_52_high, week_52_low))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'stock': {
            'ticker': ticker,
            'company_name': company_name,
            'sector': sector,
            'current_price': current_price
        }})
    except Exception as e:
        print(f"Fetch error: {e}")
        return jsonify({'success': False})

@app.route('/search_stock')
def search_stock():
    query = request.args.get('q', '').upper().strip()
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM STOCKS WHERE ticker LIKE %s OR company_name LIKE %s",
                   (f'%{query}%', f'%{query}%'))
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify({'stocks': [dict(s) for s in results]})

@app.route('/watchlist', methods=['GET', 'POST'])
def watchlist():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    if request.method == 'POST':
        ticker = request.form['ticker']
        target_price = request.form['target_price']
        cursor.execute("""
            INSERT INTO WATCHLIST (user_id, ticker, target_price, alert_status)
            VALUES (%s, %s, %s, 'PENDING')
        """, (session['user_id'], ticker, target_price))
        conn.commit()
    cursor.execute("""
        SELECT W.watchlist_id, W.ticker, S.company_name,
               S.current_price, W.target_price, W.alert_status, W.added_at,
               ROUND((S.current_price / W.target_price) * 100, 1) AS progress
        FROM WATCHLIST W
        JOIN STOCKS S ON W.ticker = S.ticker
        WHERE W.user_id = %s ORDER BY W.added_at DESC
    """, (session['user_id'],))
    watchlist_items = cursor.fetchall()
    cursor.execute("SELECT * FROM STOCKS ORDER BY ticker")
    stocks = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('watchlist.html', watchlist=watchlist_items, stocks=stocks)

@app.route('/remove_watchlist/<int:watchlist_id>')
def remove_watchlist(watchlist_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM WATCHLIST WHERE watchlist_id = %s AND user_id = %s",
                   (watchlist_id, session['user_id']))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('watchlist'))

@app.route('/journal', methods=['GET', 'POST'])
def journal():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    if request.method == 'POST':
        transaction_id = request.form['transaction_id']
        note_text = request.form['note_text']
        cursor.execute("SELECT ticker FROM TRANSACTIONS WHERE transaction_id = %s", (transaction_id,))
        txn = cursor.fetchone()
        if txn:
            cursor.execute("""
                INSERT INTO JOURNAL (user_id, ticker, transaction_id, note_text)
                VALUES (%s, %s, %s, %s)
            """, (session['user_id'], txn['ticker'], transaction_id, note_text))
            conn.commit()
    cursor.execute("""
        SELECT J.journal_id, J.note_text, J.created_at, J.ticker,
               S.company_name, T.transaction_type, T.quantity, T.price_at_transaction
        FROM JOURNAL J
        JOIN STOCKS S ON J.ticker = S.ticker
        JOIN TRANSACTIONS T ON J.transaction_id = T.transaction_id
        WHERE J.user_id = %s ORDER BY J.created_at DESC
    """, (session['user_id'],))
    entries = cursor.fetchall()
    cursor.execute("""
        SELECT T.transaction_id, T.ticker, T.transaction_type,
               T.quantity, T.price_at_transaction, S.company_name
        FROM TRANSACTIONS T
        JOIN STOCKS S ON T.ticker = S.ticker
        WHERE T.user_id = %s ORDER BY T.timestamp DESC
    """, (session['user_id'],))
    transactions = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('journal.html', entries=entries, transactions=transactions)

@app.route('/leaderboard')
def leaderboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
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
    leaderboard_data = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('leaderboard.html',
                           leaderboard=leaderboard_data,
                           current_user_id=session['user_id'])

if __name__ == '__main__':
    app.run(debug=True, port=5000)
    