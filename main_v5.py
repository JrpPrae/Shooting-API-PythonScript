# ส่วนที่ 1: Import ไลบรารีที่จำเป็นทั้งหมด
import requests
import json
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
import aiohttp
import asyncio
import time
from tqdm.asyncio import tqdm_asyncio
from tqdm import tqdm
import csv
import os
from dotenv import load_dotenv

load_dotenv()

api_chat = os.getenv("API_CHAT")
api_val = os.getenv("API_VAL")
bot_key = os.getenv("BOT_KEY")

# ==============================================================================
# ⚙️ ส่วนควบคุมการทำงาน (Control Panel)
# ==============================================================================
RUN_PART_1_GENERATE_ANSWERS = True
RUN_PART_2_EVALUATE_ANSWERS = True

# -- ตั้งค่าไฟล์ --
INPUT_FILE = "TOR_ques3.csv"
INTERMEDIATE_FILE = "TOR_v23_questions_with_answers.csv"  # ไฟล์สำหรับเก็บผลลัพธ์จากส่วนที่ 1
FINAL_OUTPUT_FILE = "TOR_v23_questions_with_answers_and_evaluation.csv"  # ✅ เปลี่ยนเป็น CSV

# -- จำนวน worker สำหรับการยิง API พร้อมกัน --
MAX_WORKERS = 5

# ==============================================================================
# 🎯 ส่วนที่ 1: ฟังก์ชันสร้างคำตอบจาก AI
# ==============================================================================
def run_part1_generate_answers():
    print("🎯 เริ่มส่วนที่ 1: กำลังสร้างคำตอบจาก AI...")
    chat_api_url = api_chat
    chat_api_headers = {
        "Content-Type": "application/json",
        "apiKey": bot_key
    }

    try:
        df = pd.read_csv(INPUT_FILE)
        df['Question'] = df['Question'].astype(str)
    except FileNotFoundError:
        print(f"❌ Error: ไม่พบไฟล์ '{INPUT_FILE}'")
        return None

    # เตรียมคอลัมน์
    for col in ["AnswerAi", "Status", "Reasoning"]:
        if col not in df.columns:
            df[col] = ""

    def ask_api(question):
        payload = {"message": [{"role": "user", "content": question}], "stream": False}
        last_error = None
        for attempt in range(3):  # retry 3 ครั้ง
            try:
                response = requests.post(chat_api_url, headers=chat_api_headers, data=json.dumps(payload), timeout=25)
                response.raise_for_status()
                result = response.json()
                return result.get("data", {}).get("choices", [{}])[0].get("message", {}).get("content", "❌Error: No content")
            except Exception as e:  
                last_error = e 
                time.sleep(1)
        return f"❌Error after retries: {last_error}" 

    part1_start_time = time.time()
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_index = {executor.submit(ask_api, row["Question"]): i for i, row in df.iterrows()}
        for future in as_completed(future_to_index):
            i = future_to_index[future]
            answer = future.result()
            df.at[i, "AnswerAi"] = answer
            q_short = df.at[i, 'Question'][:50] + ("..." if len(df.at[i, 'Question']) > 50 else "")
            a_short = answer[:100] + ("..." if len(answer) > 100 else "")
            print(f"  - Q{i+1}: {q_short}\n -> A: {a_short}\n{'-'*50}")

    part1_duration = time.time() - part1_start_time
    print(f"\n✅ ส่วนที่ 1 เสร็จสิ้น (ใช้เวลาไป {part1_duration:.2f} วินาที)")
    
    # ✅ บันทึกเป็น CSV
    df.to_csv(INTERMEDIATE_FILE, index=False, encoding='utf-8-sig',sep=",",quoting=csv.QUOTE_ALL)
    print(f"💾 ผลลัพธ์จากส่วนที่ 1 ถูกบันทึกในไฟล์: {INTERMEDIATE_FILE}")
    
    return df

# ==============================================================================
# ⚖️ ส่วนที่ 2: ฟังก์ชันประเมินความถูกต้องของคำตอบ (ThreadPoolExecutor)
# ==============================================================================
def run_part2_evaluate_answers(df_input):
    print("\n⚖️ เริ่มส่วนที่ 2: กำลังประเมินความถูกต้องของคำตอบ...")
    judge_api_url = api_val
    judge_api_headers = {"accept": "application/json", "Content-Type": "application/json"}

    def judge_api(row, retries=3, timeout=30):
        """ส่ง request ไปยัง judge API พร้อม retry"""
        payload = {
            "question": row["Question"],
            "reference_answer": str(row.get("AnswerHuman", "")),
            "candidate_answer": str(row.get("AnswerAi", ""))
        }
        last_error = None
        for attempt in range(retries):
            try:
                response = requests.post(judge_api_url, headers=judge_api_headers, json=payload, timeout=timeout)
                result = response.json()
                data = result.get("data", {})
                status = bool(data.get("is_correct"))
                reasoning = data.get("reasoning", "")
                return status, reasoning
            except Exception as e:
                last_error = e
                time.sleep(2)  # wait before retry
        return "Error❌", f"❌ {last_error}"

    all_results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor: 
        futures = {executor.submit(judge_api, row): i for i, row in df_input.iterrows()}
        for future in tqdm(as_completed(futures), total=len(futures), desc="Evaluating Answers"):
            i = futures[future]
            try:
                status, reasoning = future.result()
            except Exception as e:
                status, reasoning = "Error❌", f"❌ {e}"

            df_input.at[i, "Status"] = status
            df_input.at[i, "Reasoning"] = reasoning
            all_results.append((status, reasoning))

    # ✅ บันทึกเป็น CSV แบบ portable
    df_input.to_csv(
        FINAL_OUTPUT_FILE,
        index=False,
        encoding='utf-8-sig',
        sep=",",
        quoting=csv.QUOTE_ALL,
        columns=["Question", "AnswerHuman", "AnswerAi", "Status", "Reasoning"]
    )
    print(f"\n✅ ส่วนที่ 2 เสร็จสิ้น! ผลลัพธ์ทั้งหมดถูกบันทึกในไฟล์: {FINAL_OUTPUT_FILE}")


# ==============================================================================
# 🚀 ส่วนควบคุมหลัก (Main Execution Block)
# ==============================================================================
def main():
    df_for_evaluation = None

    if RUN_PART_1_GENERATE_ANSWERS:
        df_for_evaluation = run_part1_generate_answers()
    else:
        print("⏭️ ข้ามการทำงานส่วนที่ 1 (Generate Answers)")
        try:
            df_for_evaluation = pd.read_csv(INTERMEDIATE_FILE)
            print(f"📖 โหลดข้อมูลจากไฟล์ '{INTERMEDIATE_FILE}' เพื่อใช้ในส่วนที่ 2")
        except FileNotFoundError:
            print(f"❌ Error: ไม่สามารถรันส่วนที่ 2 ได้ เพราะไม่พบไฟล์ '{INTERMEDIATE_FILE}'")
            print("➡️ กรุณาตั้งค่า RUN_PART_1_GENERATE_ANSWERS = True เพื่อสร้างไฟล์นี้ก่อน")
            
    if RUN_PART_2_EVALUATE_ANSWERS:
        if df_for_evaluation is not None:
            run_part2_evaluate_answers(df_for_evaluation)

        else:
            print("⏹️ ไม่สามารถทำงานส่วนที่ 2 ได้ เนื่องจากไม่มีข้อมูล (DataFrame is None)")
    else:
        print("⏭️ ข้ามการทำงานส่วนที่ 2 (Evaluate Answers)")

if __name__ == "__main__":
    main()
