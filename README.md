# Shooting API — Chatbot Q&A Testing & LLM-as-a-Judge Evaluation

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-CSV-150458?logo=pandas&logoColor=white)
![Requests](https://img.shields.io/badge/requests-HTTP-2F6DB5)
![aiohttp](https://img.shields.io/badge/aiohttp-Async-2C5BB4?logo=aiohttp&logoColor=white)

สคริปต์ Python สำหรับ **"ยิง API" (Shooting API)** เพื่อทดสอบคุณภาพของ **Chatbot / RAG** แบบอัตโนมัติ โดยนำชุดคำถามจากไฟล์ CSV ส่งเข้า Chat API พร้อมกันหลายคำถาม เก็บคำตอบของ AI แล้วส่งให้ **Evaluation API (LLM-as-a-Judge)** เทียบคำตอบของ AI กับ **คำตอบอ้างอิงที่มนุษย์เตรียมไว้** เพื่อตัดสินว่าถูกต้องหรือไม่พร้อมเหตุผล ผลลัพธ์ทั้งหมดบันทึกเป็นไฟล์ CSV สำหรับวิเคราะห์ต่อ

ใช้สำหรับงาน **QA / Regression Test ของแชตบอต** เช่น แชตบอตที่ตอบคำถามจากเอกสาร TOR หรือระเบียบข้อบังคับ ช่วยให้วัดความแม่นยำได้ทุกครั้งที่ปรับ prompt, เอกสาร หรือโมเดล โดยไม่ต้องไล่ถามและตรวจทีละข้อด้วยมือ

## สารบัญ

- [ภาพรวม](#ภาพรวม)
- [Workflow](#workflow)
- [รูปแบบไฟล์ข้อมูล](#รูปแบบไฟล์ข้อมูล)
- [API ที่เรียกใช้](#api-ที่เรียกใช้)
- [การทำงานพร้อมกันและการจัดการ Error](#การทำงานพร้อมกันและการจัดการ-error)
- [Tech Stack](#tech-stack)
- [โครงสร้างโปรเจกต์](#โครงสร้างโปรเจกต์)
- [Environment Variables](#environment-variables)
- [วิธีใช้งาน](#วิธีใช้งาน)
- [หมายเหตุและสิ่งที่ควรพัฒนาต่อ](#หมายเหตุและสิ่งที่ควรพัฒนาต่อ)

## ภาพรวม

| ไฟล์ | หน้าที่ | วิธีทำงานพร้อมกัน |
| --- | --- | --- |
| [`main_v5.py`](main_v5.py) | **Pipeline หลัก** — ส่วนที่ 1 สร้างคำตอบจาก Chat API และส่วนที่ 2 ประเมินคำตอบด้วย Evaluation API เปิด/ปิดแต่ละส่วนได้ | `ThreadPoolExecutor` (5 workers) |
| [`question_script.py`](question_script.py) | สคริปต์ทดสอบเรียก Chat API ด้วยคำถามเดียว (ใช้ตรวจว่า endpoint และ API key ใช้งานได้) | — |
| [`evaluation_script.py`](evaluation_script.py) | สคริปต์ประเมินอย่างเดียว สำหรับไฟล์ที่มีคำตอบ AI อยู่แล้ว | `asyncio` + `aiohttp` |

## Workflow

### Pipeline หลัก (`main_v5.py`)

```text
TOR_ques3.csv  (Question, AnswerHuman)
        │
        ▼
┌──────────────────── ส่วนที่ 1: Generate Answers ────────────────────┐
│  RUN_PART_1_GENERATE_ANSWERS = True                                 │
│                                                                     │
│  pd.read_csv() → เพิ่มคอลัมน์ AnswerAi / Status / Reasoning (ถ้ายังไม่มี) │
│        │                                                            │
│        ▼                                                            │
│  ThreadPoolExecutor(max_workers=5)                                  │
│    └─ ask_api(question) × ทุกแถว                                     │
│         POST API_CHAT                                               │
│           header: apiKey = BOT_KEY                                  │
│           body  : {"message": [{"role": "user", "content": ...}],   │
│                    "stream": false}                                 │
│         ← data.choices[0].message.content                           │
│         timeout 25 วินาที, retry สูงสุด 3 ครั้ง (รอ 1 วินาที)                 │
│        │                                                            │
│        ▼                                                            │
│  df["AnswerAi"] ← คำตอบ  (แสดงคำถาม/คำตอบแบบย่อระหว่างทำงาน)           │
│  บันทึก → TOR_v23_questions_with_answers.csv                          │
└────────────────────────────────┬────────────────────────────────────┘
                                 │ (ถ้าปิดส่วนที่ 1 จะโหลดไฟล์นี้แทน)
                                 ▼
┌──────────────────── ส่วนที่ 2: Evaluate Answers ────────────────────┐
│  RUN_PART_2_EVALUATE_ANSWERS = True                                 │
│                                                                     │
│  ThreadPoolExecutor(max_workers=5) + tqdm progress bar              │
│    └─ judge_api(row) × ทุกแถว                                        │
│         POST API_VAL                                                │
│           body: {"question": ...,                                   │
│                  "reference_answer": AnswerHuman,                   │
│                  "candidate_answer": AnswerAi}                      │
│         ← data.is_correct , data.reasoning                          │
│         timeout 30 วินาที, retry สูงสุด 3 ครั้ง (รอ 2 วินาที)                │
│        │                                                            │
│        ▼                                                            │
│  df["Status"] ← True / False / "Error❌"                             │
│  df["Reasoning"] ← เหตุผลจาก Judge                                   │
│  บันทึก → TOR_v23_questions_with_answers_and_evaluation.csv           │
└─────────────────────────────────────────────────────────────────────┘
```

### Evaluation แบบ Async (`evaluation_script.py`)

```text
questions_with_answers.csv (Question, AnswerHuman, AnswerAi)
        │
        ▼
aiohttp.ClientSession → สร้าง task fetch(row) ทุกแถว
        │
        ▼
tqdm_asyncio.gather(*tasks)   ── ยิงทุกคำถามพร้อมกัน, timeout 300 วินาที
        │
        ▼
df["Status"], df["Reasoning"] → questions_with_evaluation_sample.csv
```

### แนวคิด LLM-as-a-Judge

```text
            ┌──────────────┐
Question ──▶│  Chatbot API │──▶ AnswerAi (candidate)
            └──────────────┘            │
                                        ▼
                          ┌───────────────────────────┐
Question ────────────────▶│  Evaluation (Judge) API   │──▶ is_correct: true/false
AnswerHuman (reference) ─▶│  เทียบความหมายของคำตอบ     │──▶ reasoning: "..."
                          └───────────────────────────┘
```

ใช้ LLM ตัดสินแทนการเทียบข้อความตรงตัว เพราะคำตอบที่ถูกต้องอาจใช้ถ้อยคำต่างจากคำตอบอ้างอิง และ Judge ให้ **เหตุผล** ประกอบ ทำให้ตรวจย้อนได้ว่าทำไมข้อนั้นผิด

## รูปแบบไฟล์ข้อมูล

### Input — `TOR_ques3.csv`

| คอลัมน์ | จำเป็น | คำอธิบาย |
| --- | --- | --- |
| `Question` | ✅ | คำถามที่จะส่งให้แชตบอต |
| `AnswerHuman` | ✅ (สำหรับส่วนที่ 2) | คำตอบอ้างอิงที่ถูกต้อง (Ground Truth) เตรียมโดยมนุษย์ |

```csv
Question,AnswerHuman
"ระเบียบใหม่นี้มีชื่อเต็มว่าอะไร?","ระเบียบ ... ว่าด้วย ... พ.ศ. ...."
```

### Output — `TOR_v23_questions_with_answers_and_evaluation.csv`

| คอลัมน์ | คำอธิบาย |
| --- | --- |
| `Question` | คำถาม |
| `AnswerHuman` | คำตอบอ้างอิง |
| `AnswerAi` | คำตอบจากแชตบอต (หรือข้อความ `❌Error after retries: ...`) |
| `Status` | ผลตัดสินจาก Judge: `True` / `False` หรือ `Error❌` |
| `Reasoning` | เหตุผลประกอบการตัดสิน |

ไฟล์ output บันทึกด้วย `encoding="utf-8-sig"` (มี BOM) และ `quoting=csv.QUOTE_ALL` เพื่อให้เปิดใน Excel แล้วแสดงภาษาไทยถูกต้อง และข้อความที่มี comma หรือขึ้นบรรทัดใหม่ไม่ทำให้คอลัมน์เพี้ยน

## API ที่เรียกใช้

### 1. Chat API (`API_CHAT`)

```http
POST {API_CHAT}
Content-Type: application/json
apiKey: {BOT_KEY}

{
  "message": [{"role": "user", "content": "คำถาม"}],
  "stream": false
}
```

Response ที่สคริปต์อ่าน: `data.choices[0].message.content`

### 2. Evaluation API (`API_VAL`)

```http
POST {API_VAL}
Content-Type: application/json
accept: application/json

{
  "question": "คำถาม",
  "reference_answer": "คำตอบอ้างอิง",
  "candidate_answer": "คำตอบจาก AI"
}
```

Response ที่สคริปต์อ่าน: `data.is_correct` และ `data.reasoning`

## การทำงานพร้อมกันและการจัดการ Error

| หัวข้อ | `main_v5.py` ส่วนที่ 1 | `main_v5.py` ส่วนที่ 2 | `evaluation_script.py` |
| --- | --- | --- | --- |
| Concurrency | `ThreadPoolExecutor`, 5 workers | `ThreadPoolExecutor`, 5 workers | `asyncio.gather` (ไม่จำกัดจำนวน) |
| Timeout ต่อ request | 25 วินาที | 30 วินาที | 300 วินาที |
| Retry | 3 ครั้ง, รอ 1 วินาที | 3 ครั้ง, รอ 2 วินาที | ไม่มี |
| เมื่อล้มเหลว | `AnswerAi = "❌Error after retries: ..."` | `Status = "Error❌"` | `Status = "error"` |
| Progress | พิมพ์คำถาม/คำตอบแบบย่อทีละข้อ | `tqdm` progress bar | `tqdm_asyncio` progress bar |

- ใช้ `as_completed()` รับผลทันทีที่แต่ละ request เสร็จ และใช้ dict `future → index` เพื่อเขียนผลกลับแถวที่ถูกต้องแม้จะเสร็จไม่ตามลำดับ
- ใช้ threads ได้ดีเพราะงานเป็น **I/O-bound** (รอ network) ไม่ติดข้อจำกัดของ GIL
- จำกัด `MAX_WORKERS = 5` เพื่อไม่ให้ยิง API หนักเกินไปจนโดน rate limit

## Tech Stack

| หมวด | เทคโนโลยี | หน้าที่ในโปรเจกต์ |
| --- | --- | --- |
| ภาษา | **Python 3.12** | ภาษาหลัก |
| Data Handling | **pandas**, `csv` | อ่าน/เขียนไฟล์คำถามและผลลัพธ์ |
| HTTP (sync) | **requests** | เรียก Chat API และ Evaluation API ใน `main_v5.py` |
| HTTP (async) | **aiohttp**, **asyncio** | ยิง Evaluation API แบบ asynchronous ใน `evaluation_script.py` |
| Concurrency | `concurrent.futures.ThreadPoolExecutor` | ส่ง request พร้อมกันหลาย thread |
| Progress Bar | **tqdm** (`tqdm`, `tqdm.asyncio`) | แสดงความคืบหน้า |
| Configuration | **python-dotenv** | โหลด URL และ API key จาก `.env` |
| Evaluation | **LLM-as-a-Judge** (Evaluation API) | ตัดสินความถูกต้องของคำตอบพร้อมเหตุผล |

## โครงสร้างโปรเจกต์

```text
Shooting-API-PythonScript/
├── main_v5.py              # Pipeline หลัก: Generate answers → Evaluate answers
├── question_script.py      # ทดสอบ Chat API ด้วยคำถามเดียว
├── evaluation_script.py    # ประเมินคำตอบแบบ async (aiohttp)
├── .env                    # (ต้องสร้างเอง) API_CHAT, API_VAL, BOT_KEY
├── .gitignore              # กัน *.env
└── README.md
```

ไฟล์ข้อมูลที่ต้องเตรียมหรือจะถูกสร้างขึ้น (ไม่อยู่ใน repository):

```text
TOR_ques3.csv                                      # input: Question, AnswerHuman
TOR_v23_questions_with_answers.csv                 # ผลลัพธ์ส่วนที่ 1
TOR_v23_questions_with_answers_and_evaluation.csv  # ผลลัพธ์สุดท้าย
questions_with_answers.csv                         # input ของ evaluation_script.py
questions_with_evaluation_sample.csv               # output ของ evaluation_script.py
```

## Environment Variables

สร้างไฟล์ `.env` ที่ root ของโปรเจกต์ (ถูกกันไว้ใน [`.gitignore`](.gitignore) แล้ว):

```env
API_CHAT=https://your-chatbot.example.com/api/v1/chat
API_VAL=https://your-evaluator.example.com/api/v1/evaluate
BOT_KEY=your_chatbot_api_key
```

| ตัวแปร | ใช้ใน | คำอธิบาย |
| --- | --- | --- |
| `API_CHAT` | `main_v5.py`, `question_script.py` | URL ของ Chat API ที่ต้องการทดสอบ |
| `API_VAL` | `main_v5.py`, `evaluation_script.py` | URL ของ Evaluation (Judge) API |
| `BOT_KEY` | `main_v5.py`, `question_script.py` | API key ของแชตบอต (ส่งใน header `apiKey`) |

## วิธีใช้งาน

### 1. ติดตั้ง dependencies

```bash
cd Shooting-API-PythonScript
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install pandas requests aiohttp tqdm python-dotenv
```

### 2. ตั้งค่า `.env`

ดูหัวข้อ [Environment Variables](#environment-variables)

### 3. ทดสอบการเชื่อมต่อ Chat API

```bash
python question_script.py
```

สคริปต์จะส่งคำถามตัวอย่าง 1 ข้อแล้วพิมพ์คำตอบ ถ้าได้คำตอบแปลว่า `API_CHAT` และ `BOT_KEY` ถูกต้อง

### 4. เตรียมไฟล์คำถาม

สร้าง `TOR_ques3.csv` ที่มีคอลัมน์ `Question` และ `AnswerHuman` (ดู [รูปแบบไฟล์ข้อมูล](#รูปแบบไฟล์ข้อมูล)) หรือแก้ชื่อไฟล์ใน `main_v5.py`

### 5. รัน Pipeline

ตั้งค่าใน Control Panel ของ `main_v5.py`:

```python
RUN_PART_1_GENERATE_ANSWERS = True   # สร้างคำตอบจาก Chat API
RUN_PART_2_EVALUATE_ANSWERS = True   # ประเมินคำตอบ

INPUT_FILE = "TOR_ques3.csv"
INTERMEDIATE_FILE = "TOR_v23_questions_with_answers.csv"
FINAL_OUTPUT_FILE = "TOR_v23_questions_with_answers_and_evaluation.csv"
MAX_WORKERS = 5
```

```bash
python main_v5.py
```

| ต้องการ | ตั้งค่า |
| --- | --- |
| รันครบทั้ง 2 ส่วน | Part 1 = `True`, Part 2 = `True` |
| สร้างคำตอบอย่างเดียว | Part 1 = `True`, Part 2 = `False` |
| ประเมินใหม่จากคำตอบเดิม (ไม่ยิง Chat API ซ้ำ) | Part 1 = `False`, Part 2 = `True` (โหลดจาก `INTERMEDIATE_FILE`) |

### 6. (ทางเลือก) ประเมินแบบ async

เตรียม `questions_with_answers.csv` ที่มีคอลัมน์ `Question`, `AnswerHuman`, `AnswerAi` แล้วรัน:

```bash
python evaluation_script.py
```

## หมายเหตุและสิ่งที่ควรพัฒนาต่อ

### ความปลอดภัยและข้อมูล

- **อย่าเขียน API key หรือ URL ภายในองค์กรไว้ในโค้ด แม้จะเป็น comment หรือตัวอย่าง `curl`** — ให้อ่านจาก `.env` เท่านั้น ถ้าเคย commit หรือแชร์ไปแล้วควรขอออก key ใหม่
- ไฟล์ CSV คำถาม/คำตอบอาจเป็นข้อมูลของลูกค้าหรือเอกสารภายใน ควรเพิ่ม `*.csv` ลงใน `.gitignore` และเตรียมไฟล์ตัวอย่างที่ไม่มีข้อมูลจริงแทน

### ปัญหาที่พบในโค้ด

- **`is_correct` ถูกแปลงด้วย `bool()`** — ถ้า API ไม่ส่งค่ามา (`None`) จะกลายเป็น `False` เหมือนตอบผิด และถ้าส่งมาเป็น string `"false"` จะกลายเป็น `True` ควรตรวจชนิดข้อมูลให้ชัดเจน และแยกกรณี error ออกจากกรณีตอบผิด
- **ส่วนที่ 2 ไม่ตรวจ HTTP status** — response ที่เป็น error (เช่น 500) อาจถูกนับว่าเป็น `False` แทนที่จะ retry ควรเรียก `response.raise_for_status()` เหมือนส่วนที่ 1
- **ต้องมีคอลัมน์ `AnswerHuman`** — ตอนบันทึกไฟล์สุดท้ายระบุคอลัมน์นี้ไว้ ถ้า input ไม่มีจะเกิด `KeyError` หลังจากยิง API เสร็จแล้ว ควรตรวจคอลัมน์ตั้งแต่ตอนโหลดไฟล์
- **ค่าว่างใน CSV** — ถ้า `AnswerHuman` ว่าง `str(NaN)` จะส่งคำว่า `"nan"` ไปเป็นคำตอบอ้างอิง
- **`evaluation_script.py`** ยิงทุกคำถามพร้อมกันโดยไม่จำกัดจำนวน (ควรใช้ `asyncio.Semaphore`) ไม่มี retry และข้อความสุดท้ายบอกชื่อไฟล์ไม่ตรงกับไฟล์ที่บันทึกจริง (`questions_with_evaluation.csv` กับ `questions_with_evaluation_sample.csv`)
- **`main_v5.py`** import `aiohttp`, `asyncio`, `tqdm_asyncio` ไว้แต่ไม่ได้ใช้
- ยังไม่มี `requirements.txt`

### แนวทางพัฒนาต่อ

- **สรุปผลอัตโนมัติ** — คำนวณ Accuracy (% ที่ `Status = True`), จำนวน error และเวลาเฉลี่ยต่อคำถาม แล้วพิมพ์ท้าย pipeline
- บันทึก **latency** ของแต่ละคำถาม (ใน `evaluation_script.py` คำนวณไว้แล้วแต่ยังไม่ได้บันทึก) เพื่อใช้ทดสอบประสิทธิภาพ
- รับชื่อไฟล์และการเปิด/ปิดแต่ละส่วนผ่าน **command line (`argparse`)** แทนการแก้โค้ด
- บันทึกผลเป็นระยะระหว่างทำงาน เพื่อไม่ให้ข้อมูลหายถ้าสคริปต์หยุดกลางทาง และรันต่อจากข้อที่ค้างได้
- เปรียบเทียบผลระหว่างเวอร์ชันของแชตบอต (เช่น v22 กับ v23) เพื่อดูว่าข้อไหนดีขึ้นหรือแย่ลง
