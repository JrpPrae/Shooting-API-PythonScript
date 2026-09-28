import pandas as pd
import aiohttp
import asyncio
import time
from tqdm.asyncio import tqdm_asyncio
import os
from dotenv import load_dotenv

load_dotenv()

api_val = os.getenv("API_VAL")


file_path = "questions_with_answers.csv"
df = pd.read_csv(file_path)

url = api_val
headers = {
    "accept": "application/json",
    "Content-Type": "application/json"
}

# ฟังก์ชันยิง API แบบ async
async def fetch(session, row):
    payload = {
        "question": row["Question"],
        "reference_answer": row["AnswerHuman"],
        "candidate_answer": row["AnswerAi"]
    }
    start_time = time.perf_counter()
    try:
        async with session.post(url, headers=headers, json=payload, timeout=300) as resp:
            data = await resp.json()
            reasoning = data["data"].get("reasoning", "")
            is_correct = data["data"].get("is_correct", "")
    except Exception as e:
        print(f"❌ Error for question '{row['Question']}': {e}")
        reasoning, is_correct = "", "error"
    end_time = time.perf_counter()
    elapsed = round(end_time - start_time, 2)  # เวลา (วินาที)
    return is_correct, reasoning

async def main():
    async with aiohttp.ClientSession() as session:
        tasks = [fetch(session, row) for _, row in df.iterrows()]
        results = await tqdm_asyncio.gather(*tasks)

    # แยกผลลัพธ์
    df["Status"] = [res[0] for res in results]
    df["Reasoning"] = [res[1] for res in results]

    # บันทึกไฟล์ใหม่
    df.to_csv("questions_with_evaluation_sample.csv", index=False)

    print("✅ Done! Saved to questions_with_evaluation.csv")

# Run async
asyncio.run(main())