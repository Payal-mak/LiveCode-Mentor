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

class HintPayload(BaseModel):
    code: str
    mistake_type: str
    language: str = "python"

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

# FR9: Detect common beginner mistakes
class MistakeDetector(ast.NodeVisitor):
    def __init__(self, code_lines):
        self.mistakes = []
        self.code_lines = code_lines

    def visit_For(self, node):
        # Check off-by-one: range(len(arr)+1)
        if isinstance(node.iter, ast.Call):
            func = node.iter
            if isinstance(func.func, ast.Name) and func.func.id == "range":
                if func.args:
                    arg = func.args[0]
                    if isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Add):
                        self.mistakes.append({
                            "type": "off_by_one",
                            "line": node.lineno,
                            "description": "Possible off-by-one error in loop range"
                        })
        self.generic_visit(node)

    def visit_While(self, node):
        # Check for while True without break
        if isinstance(node.test, ast.Constant) and node.test.value is True:
            has_break = any(
                isinstance(n, ast.Break)
                for n in ast.walk(node)
            )
            if not has_break:
                self.mistakes.append({
                    "type": "infinite_loop",
                    "line": node.lineno,
                    "description": "while True loop with no break statement"
                })
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        # Check mutable default arguments (def f(x=[]))
        for default in node.args.defaults:
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                self.mistakes.append({
                    "type": "mutable_default",
                    "line": node.lineno,
                    "description": f"Mutable default argument in function '{node.name}'"
                })
        self.generic_visit(node)

def detect_mistakes(code: str) -> dict:
    try:
        tree = ast.parse(code)
        code_lines = code.split("\n")
        detector = MistakeDetector(code_lines)
        detector.visit(tree)
        if detector.mistakes:
            return {
                "has_mistake": True,
                "mistake": detector.mistakes[0]
            }
        return {"has_mistake": False, "mistake": None}
    except:
        return {"has_mistake": False, "mistake": None}

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

In 2 friendly sentences explain what went wrong and how to fix it.
Be encouraging and simple. No technical jargon."""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150,
        temperature=0.3
    )
    return response.choices[0].message.content.strip()

async def get_explanation(code: str, language: str, concepts: list) -> dict:
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
                "friendly_error": friendly,
                "mistake": None
            }

    # FR5: Detect concepts using AST
    concepts = detect_concepts(payload.code)
    print(f"[LiveCode Mentor] Concepts: {concepts}")

    # FR9: Detect mistakes
    mistake_result = detect_mistakes(payload.code)
    print(f"[LiveCode Mentor] Mistakes: {mistake_result}")

    # FR3: Get AI explanation
    try:
        result = await get_explanation(payload.code, payload.language, concepts)
        result["mistake"] = mistake_result
        return result
    except Exception as e:
        print(f"[LiveCode Mentor] Error: {e}")
        return {
            "explanation": "Could not analyze code. Please try again.",
            "concepts": concepts,
            "has_error": False,
            "friendly_error": None,
            "mistake": mistake_result
        }

# FR10: Generate hint for detected mistake
@app.post("/hint")
async def get_hint(payload: HintPayload):
    print(f"[LiveCode Mentor] Generating hint for: {payload.mistake_type}")

    prompt = f"""A beginner has this bug in their {payload.language} code:
Bug type: {payload.mistake_type}

Code:
{payload.code}

Give ONE helpful hint that guides them toward the solution WITHOUT giving the answer.
Be encouraging. Maximum 2 sentences."""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=100,
        temperature=0.4
    )

    hint = response.choices[0].message.content.strip()
    return {"hint": hint, "has_mistake": True}

# FR11: Check if mistake is fixed
@app.post("/check-fix")
async def check_fix(payload: CodePayload):
    print(f"[LiveCode Mentor] Checking if fix is applied...")
    mistake_result = detect_mistakes(payload.code)

    if not mistake_result["has_mistake"]:
        return {"fixed": True, "message": "Great job! The issue is resolved! 🎉"}
    else:
        return {"fixed": False, "message": "Not quite yet — check the hint again!"}
    
    # FR6: Generate Mermaid.js flow diagram
@app.post("/flow")
async def generate_flow(payload: CodePayload):
    print(f"[LiveCode Mentor] Generating flow diagram...")

    prompt = f"""Convert this {payload.language} code into a Mermaid.js flowchart.

Rules:
- Use flowchart TD direction
- Start with a Start node and end with an End node
- Show variable initialization, loops with conditions, function calls, return statements
- Keep node labels short — max 4 words each
- Use proper Mermaid.js syntax
- For loops use: loopCondition{{condition}} with Yes/No paths
- Return ONLY the raw Mermaid code, no backticks, no explanation

Code:
{payload.code}"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=400,
        temperature=0.2
    )

    mermaid_code = response.choices[0].message.content.strip()

    # Clean up any backticks if model added them
    mermaid_code = mermaid_code.replace("```mermaid", "").replace("```", "").strip()
    print(f"[LiveCode Mentor] Mermaid code: {mermaid_code}")

    return {"mermaid": mermaid_code}