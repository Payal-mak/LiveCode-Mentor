from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import ast
import json
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

app = FastAPI()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class CodePayload(BaseModel):
    code: str
    language: str = "python"
    fileName: str = ""
    trigger: str = "change"

def check_syntax(code: str, language: str):
    if language != "python":
        return None
    try:
        ast.parse(code)
        return None
    except SyntaxError as e:
        return {
            "line": e.lineno,
            "msg": str(e.msg),
            "text": str(e.text).strip() if e.text else ""
        }

async def get_friendly_error(error: dict, code: str) -> str:
    prompt = f"""A beginner programmer got this Python syntax error:

Error: {error['msg']}
Line {error['line']}: {error['text']}

In 2 friendly sentences, explain:
1. What went wrong in simple words
2. How to fix it

Be encouraging and simple. No technical jargon."""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150,
        temperature=0.3
    )
    return response.choices[0].message.content.strip()

async def get_explanation(code: str, language: str) -> dict:
    prompt = f"""You are LiveCode Mentor, a friendly coding tutor for beginners.
Analyze this {language} code and return ONLY a JSON object with these exact fields:
- "explanation": 2-3 simple sentences explaining what this code does in plain English
- "concepts": a list of programming concepts used (e.g. ["for loop", "function", "array"])
- "has_error": false
- "friendly_error": null

Code:
```{language}
{code}
```

Return ONLY valid JSON, no markdown, no backticks, nothing else."""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,
        temperature=0.3
    )

    raw = response.choices[0].message.content.strip()
    print(f"[LiveCode Mentor] Groq response: {raw}")

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "explanation": raw,
            "concepts": [],
            "has_error": False,
            "friendly_error": None
        }

@app.get("/health")
def health():
    return {"status": "LiveCode Mentor backend running ✅"}

@app.post("/analyze")
async def analyze(payload: CodePayload):
    print(f"[LiveCode Mentor] Analyzing ({payload.trigger}) - {len(payload.code)} chars")

    # FR4: Check syntax first
    if payload.language == "python":
        syntax_error = check_syntax(payload.code, payload.language)
        if syntax_error:
            print(f"[LiveCode Mentor] Syntax error found: {syntax_error}")
            friendly = await get_friendly_error(syntax_error, payload.code)
            return {
                "explanation": f"There's a syntax error on line {syntax_error['line']}.",
                "concepts": [],
                "has_error": True,
                "friendly_error": friendly
            }

    # FR3: Get AI explanation
    try:
        result = await get_explanation(payload.code, payload.language)
        return result
    except Exception as e:
        print(f"[LiveCode Mentor] Error: {e}")
        return {
            "explanation": "Could not analyze code. Please try again.",
            "concepts": [],
            "has_error": False,
            "friendly_error": None
        }