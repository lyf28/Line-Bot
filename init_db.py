import sqlite3
DB_NAME = "expenses.db"

conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        item TEXT,
        category TEXT,
        amount INTEGER,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
conn.commit()
conn.close()

print("✅ 資料庫初始化完成")

