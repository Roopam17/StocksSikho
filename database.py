import mysql.connector
import os

def get_connection():
    conn = mysql.connector.connect(
        host=os.environ.get('MYSQLHOST', 'localhost'),
        port=int(os.environ.get('MYSQLPORT', 3306)),
        user=os.environ.get('MYSQLUSER', 'root'),
        password=os.environ.get('MYSQLPASSWORD', ''),
        database=os.environ.get('MYSQLDATABASE', 'stocksikho')
    )
    return conn