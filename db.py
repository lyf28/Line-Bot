import sqlite3
import openai
import os
from openai import OpenAI
from config import OPENAI_API_KEY
client = OpenAI(api_key=OPENAI_API_KEY)
#client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

#OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


DB_NAME = "expenses.db"
openai.api_key = OPENAI_API_KEY


def init_db():
    """ 初始化資料庫（如果沒有表就建立） """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 建立 expenses 表（如果不存在）
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

    # 建立 spending_alerts 表（如果不存在）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS spending_alerts (
            user_id TEXT,
            category TEXT,
            limit_amount INTEGER,
            PRIMARY KEY (user_id, category)
        )
    """)

    # 建立 custom_categories 表（如果不存在）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS custom_categories (
            user_id TEXT,
            category_name TEXT,
            PRIMARY KEY (user_id, category_name)
        )
    """)

    conn.commit()
    conn.close()
    print("✅ 資料庫初始化完成！")

def classify_with_ai(item_name):
    """ 使用 AI 自動分類消費品項 """
    prompt = f"""
使用者記了一筆消費：「{item_name}」

請幫我自動幫這筆消費分類。如果它屬於以下常見類別，請選其中一個：
「餐費、飲料、娛樂、交通、購物、醫療、其他」

如果不屬於這些，也可以依照品項的意思，自動創建一個簡短合理的新分類（例如「寵物」、「保險」、「繳稅」）。

請你只回傳分類名稱，不要加任何其他說明或語氣詞。
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "你是一個消費分類助手，只會輸出分類名稱，不會說明。"},
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content.strip()

def save_expense(user_id, item, amount):
    """ 儲存消費記錄 """
    category = classify_with_ai(item)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO expenses (user_id, item, category, amount)
        VALUES (?, ?, ?, ?)
    """, (user_id, item, category, amount))
    conn.commit()
    conn.close()
    return category

def get_monthly_transactions(user_id):
    """ 查詢當月所有消費記錄 """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, item, category, amount, date FROM expenses
        WHERE user_id = ? AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now')
        ORDER BY date DESC
    """, (user_id,))
    transactions = cursor.fetchall()
    conn.close()

    if not transactions:
        return "📅 這個月沒有消費紀錄"

    result = "📋 本月消費紀錄：\n"
    for t in transactions:
        result += f"ID:{t[0]} | {t[4][:10]} - {t[1]} {t[3]} 元（{t[2]}）\n"

    return result

def get_daily_expense(user_id, date):
    """ 查詢指定日期的總支出 """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT SUM(amount) FROM expenses WHERE user_id = ? AND date(date) = ?
    """, (user_id, date))

    total_spent = cursor.fetchone()[0]
    conn.close()

    if total_spent is None:
        return f"📅 {date} 沒有消費紀錄"
    
    return f"📅 {date} 總支出：{total_spent} 元"

def delete_expense_by_id(user_id, expense_id):
    """ 刪除某筆消費記錄 """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM expenses WHERE id = ? AND user_id = ?
    """, (expense_id, user_id))

    conn.commit()
    conn.close()
    return f"🗑️ 已刪除 ID {expense_id} 的消費記錄"

def update_category_by_id(user_id, expense_id, new_category):
    """ 修改某筆消費記錄的分類 """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE expenses SET category = ? WHERE id = ? AND user_id = ?
    """, (new_category, expense_id, user_id))

    conn.commit()
    conn.close()
    return f"✅ 消費記錄 ID:{expense_id} 已更新分類為 {new_category}"

def update_expense_amount_by_id(user_id, expense_id, new_amount):
    """ 修改某筆消費的金額 """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE expenses SET amount = ? WHERE id = ? AND user_id = ?
    """, (new_amount, expense_id, user_id))

    conn.commit()
    conn.close()
    return f"✅ 消費記錄 ID:{expense_id} 金額已更新為 {new_amount} 元"

def set_spending_alert(user_id, category, limit):
    """ 設定消費超支提醒 """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS spending_alerts (
            user_id TEXT,
            category TEXT,
            limit_amount INTEGER,
            PRIMARY KEY (user_id, category)
        )
    """)
    cursor.execute("""
        INSERT INTO spending_alerts (user_id, category, limit_amount)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, category) DO UPDATE SET limit_amount = excluded.limit_amount
    """, (user_id, category, limit))
    conn.commit()
    conn.close()
    return f"🔔 已設定 {category} 的超支提醒為 {limit} 元"

def check_spending_alert(user_id):
    """ 檢查用戶是否超過消費上限 """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT category, limit_amount FROM spending_alerts WHERE user_id = ?
    """, (user_id,))
    alerts = cursor.fetchall()

    if not alerts:
        return None

    warning_messages = []
    for category, limit in alerts:
        cursor.execute("""
            SELECT SUM(amount) FROM expenses WHERE user_id = ? AND category = ? AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now')
        """, (user_id, category))
        total_spent = cursor.fetchone()[0] or 0

        if total_spent > limit:
            warning_messages.append(f"⚠️ {category} 本月已花 {total_spent} 元，超過設定的 {limit} 元")

    conn.close()
    return "\n".join(warning_messages) if warning_messages else None

def add_new_category(user_id, category_name):
    """ 讓用戶新增自訂分類 """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS custom_categories (
            user_id TEXT,
            category_name TEXT,
            PRIMARY KEY (user_id, category_name)
        )
    """)
    cursor.execute("""
        INSERT INTO custom_categories (user_id, category_name)
        VALUES (?, ?)
        ON CONFLICT(user_id, category_name) DO NOTHING
    """, (user_id, category_name))
    
    conn.commit()
    conn.close()
    return f"✅ 新增分類成功：{category_name}"

def get_last_expense_id(user_id):
    """ 查詢用戶最新一筆記錄的 ID """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id FROM expenses WHERE user_id = ? ORDER BY date DESC LIMIT 1
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    return row[0] if row else None

def clear_all_expenses(user_id):
    """ 🔥 清除用戶所有記帳記錄 """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM expenses WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return "✅ 已清除你的所有記帳資料！"

def get_monthly_total(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT SUM(amount) FROM expenses
        WHERE user_id = ? AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now')
    """, (user_id,))
    total = cursor.fetchone()[0] or 0
    conn.close()
    return f"📊 本月總花費：{total} 元"

def get_monthly_category_summary(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT category, SUM(amount) FROM expenses
        WHERE user_id = ? AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now')
        GROUP BY category
    """, (user_id,))
    data = cursor.fetchall()
    conn.close()

    if not data:
        return "📊 本月還沒有任何消費紀錄喔！"

    result = "📊 本月各分類花費如下：\n"
    for category, total in data:
        result += f"• {category}：{total} 元\n"
    return result



