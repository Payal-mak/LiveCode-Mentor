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

# FR5: AST-based concept detector
class ConceptDetector(ast.NodeVisitor):
    def __init__(self):
        self.concepts = set()

    def visit_For(self, node):
        self.concepts.add("for loop")
        self.generic_visit(node)

    def visit_While(self, node):
        self.concepts.add("while loop")
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self.concepts.add("function")
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self.concepts.add("async function")
        self.generic_visit(node)

    def visit_Return(self, node):
        self.concepts.add("return statement")
        self.generic_visit(node)

    def visit_If(self, node):
        self.concepts.add("conditional (if/else)")
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self.concepts.add("class / OOP")
        self.generic_visit(node)

    def visit_ListComp(self, node):
        self.concepts.add("list comprehension")
        self.generic_visit(node)

    def visit_Lambda(self, node):
        self.concepts.add("lambda function")
        self.generic_visit(node)

    def visit_Try(self, node):
        self.concepts.add("try/except (error handling)")
        self.generic_visit(node)

    def visit_Import(self, node):
        self.concepts.add("import / modules")
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        self.concepts.add("import / modules")
        self.generic_visit(node)

    def visit_List(self, node):
        self.concepts.add("list / array")
        self.generic_visit(node)

    def visit_Dict(self, node):
        self.concepts.add("dictionary")
        self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            if node.func.id == "print":
                self.concepts.add("print function")
            elif node.func.id == "range":
                self.concepts.add("range function")
            elif node.func.id == "len":
                self.concepts.add("len function")
            elif node.func.id == "input":
                self.concepts.add("user input")
        self.generic_visit(node)

def detect_concepts(code: str) -> list:
    try:
        tree = ast.parse(code)
        detector = ConceptDetector()
        detector.visit(tree)
        return list(detector.concepts)
    except:
        return []

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

async def get_explanation(code: str, language: str, concepts: list) -> dict:
    concepts_str = ", ".join(concepts) if concepts else "none detected"

    prompt = f"""You are LiveCode Mentor, a friendly coding tutor for beginners.
Analyze this {language} code and return ONLY a JSON object with these exact fields:
- "explanation": 2-3 simple sentences explaining what this code does in plain English
- "concepts": {json.dumps(concepts)}
- "has_error": false
- "friendly_error": null

Code:
```{language}
{code}
```

The concepts list is already detected, just include it as-is.
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
            "concepts": concepts,
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
            print(f"[LiveCode Mentor] Syntax error: {syntax_error}")
            friendly = await get_friendly_error(syntax_error, payload.code)
            return {
                "explanation": f"There's a syntax error on line {syntax_error['line']}.",
                "concepts": [],
                "has_error": True,
                "friendly_error": friendly
            }

    # FR5: Detect concepts using AST
    concepts = detect_concepts(payload.code)
    print(f"[LiveCode Mentor] Concepts detected: {concepts}")

    # FR3: Get AI explanation
    try:
        result = await get_explanation(payload.code, payload.language, concepts)
        return result
    except Exception as e:
        print(f"[LiveCode Mentor] Error: {e}")
        return {
            "explanation": "Could not analyze code. Please try again.",
            "concepts": concepts,
            "has_error": False,
            "friendly_error": None
        }