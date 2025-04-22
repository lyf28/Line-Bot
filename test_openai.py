import openai
import os

# 確保你在環境變數或程式裡有設定 API 金鑰
openai.api_key = os.getenv("OPENAI_API_KEY")

def test_openai():
    try:
        print("🔍 測試中...")
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "你是一個記帳機器人"},
                {"role": "user", "content": "我吃了拉麵花了150元"}
            ]
        )

        result = response.choices[0].message.content.strip()
        print("✅ GPT 回應：")
        print(result)

    except Exception as e:
        print("❌ 發生錯誤：", e)

if __name__ == "__main__":
    test_openai()
