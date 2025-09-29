import sqlite3
from pathlib import Path

DB_PATH = Path("data.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS arrivals(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bl TEXT UNIQUE,
        date TEXT,       -- YYYY-MM-DD
        port TEXT,
        notes TEXT
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        arrival_bl TEXT,
        code TEXT,
        description TEXT,
        meters REAL,
        rolls INTEGER,
        FOREIGN KEY(arrival_bl) REFERENCES arrivals(bl)
    );
    """)
    conn.commit()
    conn.close()

def upsert_arrival(bl, date, port=None, notes=None, items=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO arrivals(bl, date, port, notes) VALUES(?, ?, ?, ?)",
                (bl, date, port, notes))
    if items:
        cur.execute("DELETE FROM items WHERE arrival_bl = ?", (bl,))
        cur.executemany("""INSERT INTO items(arrival_bl, code, description, meters, rolls)
                           VALUES(?,?,?,?,?)""",
                        [(bl, it["code"], it["description"], float(it["meters"]), int(it["rolls"])) for it in items])
    conn.commit()
    conn.close()

def list_events():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT bl, date FROM arrivals ORDER BY date")
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "id": r["bl"],
            "title": f"Llegada: {r['bl']}",
            "start": r["date"],   # <= FullCalendar usa 'start'
            "allDay": True
        }
        for r in rows
    ]

def get_arrival(bl):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM arrivals WHERE bl = ?", (bl,))
    arr = cur.fetchone()
    cur.execute("SELECT code, description, meters, rolls FROM items WHERE arrival_bl = ? ORDER BY id", (bl,))
    its = cur.fetchall()
    conn.close()
    return arr, its
