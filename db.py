# db.py
import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = Path("data.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # --- Llegadas (contenedores) ---
    cur.execute("""
    CREATE TABLE IF NOT EXISTS arrivals(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bl   TEXT UNIQUE,
        date TEXT,       -- YYYY-MM-DD
        port TEXT,
        notes TEXT
    );
    """)

    # --- Ítems de cada llegada ---
    cur.execute("""
    CREATE TABLE IF NOT EXISTS items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        arrival_bl  TEXT,
        code        TEXT,
        description TEXT,
        meters      REAL,
        rolls       INTEGER,
        FOREIGN KEY(arrival_bl) REFERENCES arrivals(bl)
    );
    """)

    # --- Usuarios (admin/vendor) ---
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username      TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role          TEXT NOT NULL CHECK(role IN ('admin','vendor'))
    );
    """)

    conn.commit()
    conn.close()

# ---------------- Usuarios ----------------
def create_user(username: str, password: str, role: str = "vendor"):
    if role not in ("admin", "vendor"):
        raise ValueError("Rol inválido")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO users(username, password_hash, role) VALUES(?,?,?)",
                (username.strip(), generate_password_hash(password.strip()), role))
    conn.commit()
    conn.close()

def get_user(username: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ?", (username.strip(),))
    row = cur.fetchone()
    conn.close()
    return row

def verify_password(password_hash: str, password_plain: str) -> bool:
    return check_password_hash(password_hash, password_plain)

# ---------------- Llegadas / Calendario ----------------
def upsert_arrival(bl, date, port=None, notes=None, items=None):
    conn = get_conn()
    cur = conn.cursor()

    # inserta o actualiza cabecera
    cur.execute(
        "INSERT OR REPLACE INTO arrivals(bl, date, port, notes) VALUES(?, ?, ?, ?)",
        (bl, date, port, notes)
    )

    # borra items del BL y re-inserta
    cur.execute("DELETE FROM items WHERE arrival_bl = ?", (bl,))
    if items:
        cur.executemany(
            """INSERT INTO items(arrival_bl, code, description, meters, rolls)
               VALUES(?,?,?,?,?)""",
            [(bl,
              it.get("code", ""),
              it.get("description", ""),
              float(it.get("meters", 0)),
              int(it.get("rolls", 0)))
             for it in items]
        )

    conn.commit()
    conn.close()


def list_events():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT bl, date FROM arrivals ORDER BY date")
    rows = cur.fetchall()
    conn.close()
    return [
        {"id": r["bl"], "title": f"Llegada: {r['bl']}", "start": r["date"], "allDay": True}
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
