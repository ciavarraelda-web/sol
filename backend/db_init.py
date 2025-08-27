# db_init.py
import sqlite3
conn = sqlite3.connect("mining.db")
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS mining_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet TEXT NOT NULL,
    amount REAL NOT NULL,
    tx TEXT,
    created_at TIMESTAMP NOT NULL
)
""")
conn.commit()
conn.close()
print("DB creato")
