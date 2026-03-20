from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
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

@app.get("/health")
def health():
    return {"status": "LiveCode Mentor backend running ✅"}

@app.post("/analyze")
async def analyze(payload: CodePayload):
    print(f"[LiveCode Mentor] Analyzing code ({payload.trigger}) - {len(payload.code)} chars")

    prompt = f"""You are LiveCode Mentor, a friendly coding tutor for beginners.
Analyze this {payload.language} code and return ONLY a JSON object with these exact fields:
- "explanation": 2-3 simple sentences explaining what this code does in plain English for a beginner
- "concepts": a list of programming concepts used (e.g. ["for loop", "function", "array", "recursion"])
- "has_error": false
- "friendly_error": null

Code to analyze:
```{payload.language}
{payload.code}
```

Return ONLY valid JSON, no markdown, no backticks, nothing else."""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.3
        )

        raw = response.choices[0].message.content.strip()
        print(f"[LiveCode Mentor] Groq response: {raw}")

        # Parse JSON response
        result = json.loads(raw)
        return result

    except json.JSONDecodeError:
        # If JSON parsing fails, return a safe response
        return {
            "explanation": response.choices[0].message.content,
            "concepts": [],
            "has_error": False,
            "friendly_error": None
        }
    except Exception as e:
        print(f"[LiveCode Mentor] Error: {e}")
        return {
            "explanation": "Could not analyze code. Please try again.",
            "concepts": [],
            "has_error": False,
            "friendly_error": None
        }