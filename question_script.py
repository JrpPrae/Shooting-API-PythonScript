import requests
import pandas as pd
import os
from dotenv import load_dotenv

load_dotenv()

api_ans = os.getenv("API_CHAT")
bot_key = os.getenv("BOT_KEY")

# โหลดไฟล์ Excel
# file_path = "questions.xlsx"
# df = pd.read_excel(file_path)

# ฟังก์ชันเรียก API
def get_answer_from_api(question):
    url = api_ans  # เปลี่ยนเป็น endpoint ของคุณ
    headers = {
        "Content-Type": "application/json",
        "Cookie": "Path=/",
        "apiKey": bot_key
    }
    payload = {
        "message": [
            {"role": "user", "content": question}
        ],
        "stream": False
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        # ดึง content ตามโครงสร้าง JSON ที่คุณให้มา
        answer_text = data["data"]["choices"][0]["message"]["content"]
        return answer_text
    except Exception as e:
        print(f"❌ Error for question '{question}': {e}")
        return ""

# วนลูป question column แล้วเก็บลง answer column
# df["answer"] = df["question"].apply(get_answer_from_api)

# # บันทึกออกเป็น Excel
# df.to_excel("questions_with_answers.xlsx", index=False)
# print("✅ Done! Saved to questions_with_answers.xlsx")

result = get_answer_from_api("ระเบียบใหม่นี้มีชื่อเต็มว่าอะไร?")
print(result)



'''
curl -L 'https://agi.manageai.co.th/api/v1/chat' -H 'Content-Type: application/json' -H 'Cookie: Path=/' -H 'apiKey: 0d04698a-3a42-45d1-835d-09b998593a14' -d '{
    "message": [
        {
            "role": "user",
            "content": "How many '\''r'\''s in Strawberry?"
        }
    ],
    "stream" : false
}'
'''
