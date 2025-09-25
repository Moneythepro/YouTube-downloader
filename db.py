# db.py
import os
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error

load_dotenv()

_cfg = {
    'host': os.getenv('MYSQL_HOST','localhost'),
    'user': os.getenv('MYSQL_USER','root'),
    'password': os.getenv('MYSQL_PASS',''),
    'database': os.getenv('MYSQL_DB','youtube_downloader'),
    'autocommit': True
}

def get_conn():
    return mysql.connector.connect(**_cfg)

def ensure_table():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS downloads (
        id INT AUTO_INCREMENT PRIMARY KEY,
        title VARCHAR(255),
        url TEXT,
        format VARCHAR(10),
        size VARCHAR(50),
        path TEXT,
        download_time DATETIME
    )""")
    cursor.close()
    conn.close()

def insert_download(title, url, fmt, size, path, download_time):
    conn = get_conn()
    cursor = conn.cursor()
    sql = "INSERT INTO downloads (title, url, format, size, path, download_time) VALUES (%s,%s,%s,%s,%s,%s)"
    cursor.execute(sql, (title, url, fmt, size, path, download_time))
    last_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return last_id

def fetch_history(limit=100):
    conn = get_conn()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM downloads ORDER BY download_time DESC LIMIT %s", (limit,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows