import os
import re
from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from db import (
    save_expense, get_monthly_transactions, get_daily_expense,
    delete_expense_by_id, update_expense_amount_by_id, update_category_by_id,
    set_spending_alert, check_spending_alert, add_new_category, clear_all_expenses,
    get_last_expense_id, get_monthly_total
)

import os
from openai import OpenAI


LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

user_last_expense_id = {}

app = Flask(__name__)

import openai
openai.api_key = os.getenv("OPENAI_API_KEY")

line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 讓 AI 來判斷用戶的意圖
import json

def interpret_user_intent(user_input):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {
                    "role": "system",
                    "content": """
你是一個專業的 LINE 記帳機器人，只負責將使用者的輸入「轉換為 JSON 格式」，請務必使用繁體中文，且不加入多餘回應。

僅支援以下 intent：
- "記帳"
- "修改分類"
- "修改金額"
- "查詢本月"
- "查詢本月總額"
- "查詢特定日期"
- "刪除"
- "清除所有記錄"
- "新增分類"
- "設定提醒"
- "查詢分類統計"

請確保格式為：
{
  "intent": "意圖（用繁體中文）",
  "params": {
    "item": "品項",
    "amount": 金額（數字）,
    "date": "YYYY-MM-DD",
    "category": "分類名稱"
    ...（視情況給其他參數）
  }
}
"""
                },
                {
                    "role": "user",
                    "content": f"請解析這句話：『{user_input}』"
                }
            ]
        )

        ai_output = response.choices[0].message.content.strip()
        print("🧠 GPT 回傳：")
        print(ai_output)

        parsed_response = json.loads(ai_output)
        return parsed_response.get("intent", "未知"), parsed_response.get("params", {})

    except Exception as e:
        print(f"❌ AI 解析失敗: {e}")
        return "未知", {}




# ✅ **處理 Line Webhook**
@app.route("/callback", methods=["POST"])
def callback():
    """ 📨 接收 Line 訊息 """
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return "Invalid signature", 400

    return "OK"

# ✅ **處理使用者輸入**
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    """ 🔥 接收用戶訊息，並根據 AI 判斷的意圖執行對應動作 """
    user_id = event.source.user_id
    text = event.message.text.strip()

    # ✅ 讓 AI 解析用戶輸入
    intent, params = interpret_user_intent(text)

    if intent == "記帳":
        item = params.get("item")
        amount = params.get("amount")

        if item and amount:
            category = save_expense(user_id, item, amount)
            last_id = get_last_expense_id(user_id)
            user_last_expense_id[user_id] = last_id
            reply = f"✅ 好的，已幫你記下「{item} {amount} 元」，分類為「{category}」"

        else:
            reply = "❌ 抱歉我沒聽懂你要記帳的項目與金額，可以再說一次嗎？例如：我今天喝珍奶花了55元"


    elif intent == "查詢本月":
        reply = get_monthly_transactions(user_id)

    elif intent == "查詢本月總額":
        reply = get_monthly_total(user_id)

    elif intent == "查詢特定日期":
        date = params.get("date")
        reply = get_daily_expense(user_id, date) if date else "❌ 請輸入正確日期"

    elif intent == "刪除":
        expense_id = params.get("expense_id") or get_last_expense_id(user_id)
        if expense_id:
            reply = delete_expense_by_id(user_id, expense_id)
        else:
            reply = "❌ 找不到可刪除的記錄"

    elif intent == "修改分類":
        expense_id = params.get("expense_id") or user_last_expense_id.get(user_id)
        new_category = params.get("new_category")
        if expense_id and new_category:
            reply = update_category_by_id(user_id, expense_id, new_category)
        else:
            reply = "❌ 請說明要修改的分類，例如「分類改成交通」"


    elif intent == "修改金額":
        expense_id = params.get("expense_id") or get_last_expense_id(user_id)
        new_amount = params.get("new_amount")
        if expense_id and new_amount:
            reply = update_expense_amount_by_id(user_id, expense_id, new_amount)
        else:
            reply = "❌ 修改金額格式錯誤，請輸入「修改金額 記錄ID 新金額」"

    elif intent == "清除所有記錄":
        reply = clear_all_expenses(user_id)

    elif intent == "設定提醒":
        category = params.get("category")
        limit = params.get("limit")
        if category and limit:
            reply = set_spending_alert(user_id, category, limit)
        else:
            reply = "❌ 設定提醒格式錯誤，請輸入「設定提醒 類別 上限金額」"

    elif intent == "新增分類":
        category_name = params.get("category_name")
        if category_name:
            reply = add_new_category(user_id, category_name)
        else:
            reply = "❌ 請輸入要新增的分類名稱"
    
    elif intent == "查詢分類統計":
        reply = get_monthly_category_summary(user_id)

    else:
        reply = "❌ 無法理解你的指令，請輸入有效指令"

    # ✅ 發送回應
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)




