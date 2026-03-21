from database import init_db, save_concepts, save_mistake, get_stats, get_experience_level, log_session
from tracer import trace_code

# Initialize DB on startup
init_db()

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
    level = get_experience_level(concepts)
    print(f"[LiveCode Mentor] Experience level: {level}")

    if level == "beginner":
        style = """Explain this like the student has never coded before.
Use a simple real-world analogy. 3 sentences max.
Avoid ALL technical jargon."""
    elif level == "intermediate":
        style = """Explain this to someone who understands basic programming.
Be clear and concise. 2 sentences maximum."""
    else:
        style = """Give a concise 1-sentence technical summary.
Assume expert-level Python knowledge."""

    prompt = f"""You are LiveCode Mentor, a coding tutor.
{style}

Analyze this {language} code and return ONLY a JSON object:
- "explanation": your explanation
- "concepts": {json.dumps(concepts)}
- "has_error": false
- "friendly_error": null
- "level": "{level}"
- "time_complexity": Big O time complexity (e.g. "O(n)", "O(n²)", "O(1)") with a one-line reason
- "space_complexity": Big O space complexity (e.g. "O(1)", "O(n)") with a one-line reason

For complexity fields use this format:
"time_complexity": {{"notation": "O(n)", "reason": "Single loop iterates n times"}}
"space_complexity": {{"notation": "O(1)", "reason": "Only stores a few variables"}}

Code:
```{language}
{code}
```

Return ONLY valid JSON, no markdown, no backticks, nothing else."""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=600,
        temperature=0.3
    )

    raw = response.choices[0].message.content.strip()
    print(f"[LiveCode Mentor] Groq response ({level}): {raw}")

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "explanation": raw,
            "concepts": concepts,
            "has_error": False,
            "friendly_error": None,
            "level": level,
            "time_complexity": None,
            "space_complexity": None
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
    
    # FR12: Save concepts to database
    save_concepts(concepts)
    log_session("analyze", f"trigger:{payload.trigger}")

    # FR9: Detect mistakes
    mistake_result = detect_mistakes(payload.code)
    print(f"[LiveCode Mentor] Mistakes: {mistake_result}")
    
    # FR12: Save mistake to database
    if mistake_result["has_mistake"] and mistake_result["mistake"]:
        save_mistake(mistake_result["mistake"]["type"])

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

@app.get("/stats")
def get_progress():
    return get_stats()

@app.get("/profile")
def get_profile():
    stats = get_stats()
    return {
        "status": "ok",
        "learner": stats
    }
    
    # FR14 + FR15: Generate LeetCode + article recommendations
@app.post("/recommendations")
async def get_recommendations(payload: CodePayload):
    concepts = detect_concepts(payload.code)
    if not concepts:
        return {"leetcode": [], "article": None}

    print(f"[LiveCode Mentor] Generating recommendations for: {concepts}")

    # Use AST to extract deeper context
    try:
        tree = ast.parse(payload.code)
    except:
        tree = None

    functions = []
    has_recursion = False
    has_sorting = False
    has_searching = False
    has_class = False
    has_nested_loops = False
    algorithm_hints = []

    if tree:
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append(node.name)
                # Check for recursion
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Name):
                            if child.func.id == node.name:
                                has_recursion = True
            if isinstance(node, ast.ClassDef):
                has_class = True
            if isinstance(node, ast.For):
                # Check for nested loops
                for child in ast.walk(node):
                    if isinstance(child, ast.For) and child is not node:
                        has_nested_loops = True

        # Check function names for algorithm hints
        all_names = [n.id for n in ast.walk(tree) if isinstance(n, ast.Name)]
        name_str = " ".join(all_names + functions).lower()
        if any(w in name_str for w in ["sort", "bubble", "merge", "quick", "insertion"]):
            has_sorting = True
            algorithm_hints.append("sorting algorithm")
        if any(w in name_str for w in ["search", "find", "binary", "linear"]):
            has_searching = True
            algorithm_hints.append("searching algorithm")
        if any(w in name_str for w in ["factorial", "fibonacci", "fib", "power", "hanoi"]):
            algorithm_hints.append("mathematical recursion")
        if any(w in name_str for w in ["stack", "queue", "linked", "tree", "graph", "node"]):
            algorithm_hints.append("data structure")
        if any(w in name_str for w in ["dp", "memo", "cache", "dynamic"]):
            algorithm_hints.append("dynamic programming")
        if any(w in name_str for w in ["matrix", "grid", "row", "col"]):
            algorithm_hints.append("matrix/grid problem")

    # Build rich context
    context_lines = []
    context_lines.append(f"Programming concepts used: {', '.join(concepts)}")
    if functions:
        context_lines.append(f"Functions defined: {', '.join(functions)}")
    if has_recursion:
        context_lines.append("Uses recursion")
    if has_nested_loops:
        context_lines.append("Has nested loops — O(n²) pattern")
    if has_class:
        context_lines.append("Uses object-oriented programming")
    if algorithm_hints:
        context_lines.append(f"Algorithm type: {', '.join(algorithm_hints)}")

    context = "\n".join(context_lines)

    prompt = f"""You are a coding mentor recommending practice problems and learning resources.

Here is the student's code:
```python
{payload.code}
```

Code analysis:
{context}

Based on EXACTLY what this student is practicing, recommend:
1. Two LeetCode problems that directly practice the SAME concepts
2. One high-quality article or documentation page to learn more

RULES for LeetCode problems:
- Must be directly related to concepts in THIS specific code
- If code uses recursion → recommend recursion problems
- If code uses sorting → recommend sorting problems  
- If code uses nested loops → recommend array/matrix problems
- If code uses OOP → recommend OOP design problems
- If code uses dynamic programming → recommend DP problems
- If code uses linked list/tree/graph → recommend those data structure problems
- Difficulty: Easy or Medium only (student is learning)
- Use REAL LeetCode problem titles and their actual URLs

RULES for article:
- Must be directly relevant to the main concept in this code
- Prefer: realpython.com, docs.python.org, geeksforgeeks.org, programiz.com
- Title must describe exactly what the article teaches

Return ONLY this JSON structure:
{{
  "leetcode": [
    {{
      "title": "exact leetcode problem title",
      "difficulty": "Easy",
      "url": "https://leetcode.com/problems/exact-slug/"
    }},
    {{
      "title": "exact leetcode problem title",
      "difficulty": "Medium",
      "url": "https://leetcode.com/problems/exact-slug/"
    }}
  ],
  "article": {{
    "title": "exact article title",
    "url": "https://exact-article-url.com"
  }}
}}

Return ONLY valid JSON. No markdown. No explanation."""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.2
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        print(f"[LiveCode Mentor] Recommendations: {raw}")
        result = json.loads(raw)
        return result

    except json.JSONDecodeError as e:
        print(f"[LiveCode Mentor] Recommendations JSON error: {e}")
        return {"leetcode": [], "article": None}
    except Exception as e:
        print(f"[LiveCode Mentor] Recommendations error: {e}")
        return {"leetcode": [], "article": None}
    
    # FR7: Execution trace with variable values
@app.post("/trace")
async def get_trace(payload: CodePayload):
    print(f"[LiveCode Mentor] Running execution trace...")

    if payload.language != "python":
        return {"success": False, "error": "Tracing only supported for Python", "steps": []}

    result = trace_code(payload.code, max_steps=30)
    print(f"[LiveCode Mentor] Trace: {result['total_steps'] if result['success'] else 0} steps")
    return result

# FR8: Auto test input generation + execution
@app.post("/auto-test")
async def auto_test(payload: CodePayload):
    if payload.language != "python":
        return {"tests": [], "error": "Only Python supported"}

    print(f"[LiveCode Mentor] Generating auto tests...")

    # Use AST to understand what's in the code
    try:
        tree = ast.parse(payload.code)
    except SyntaxError as e:
        return {"tests": [], "error": f"Syntax error: {e.msg}"}

    # Extract functions, classes, and top-level variables
    functions = []
    variables = []
    classes = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            args = [a.arg for a in node.args.args]
            functions.append({"name": node.name, "args": args})
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    variables.append(target.id)

    # Build context string for Groq
    context_parts = []
    if functions:
        for f in functions:
            context_parts.append(f"Function: {f['name']}({', '.join(f['args'])})")
    if classes:
        context_parts.append(f"Classes: {', '.join(classes)}")
    if variables:
        context_parts.append(f"Variables defined: {', '.join(set(variables))}")

    context = "\n".join(context_parts) if context_parts else "No functions or classes — just statements"

    prompt = f"""You are a Python testing assistant.

Here is the code to test:
```python
{payload.code}
```

Code structure detected:
{context}

Your job: Generate exactly 3 test lines that will be APPENDED to the end of this code.

STRICT RULES — read carefully:
1. Each test line is ONE single Python print() statement
2. It will run AFTER the code above, so all variables/functions are already defined
3. Use ONLY names that actually exist in the code above
4. Do NOT redeclare variables, do NOT rewrite the code
5. Do NOT use semicolons
6. Do NOT write multi-line code in a single test

Examples of GOOD tests depending on code type:
- If code defines function add(a,b): print(add(2, 3))
- If code defines variable total: print(total)
- If code defines list arr: print(len(arr))
- If code defines class Dog: print(Dog())
- If code just runs loops: print("Done")

Return ONLY this JSON format:
{{
  "tests": [
    {{"input_code": "print(something)", "description": "short description"}},
    {{"input_code": "print(something_else)", "description": "short description"}},
    {{"input_code": "print(another_thing)", "description": "short description"}}
  ]
}}

Return ONLY valid JSON. No markdown. No explanation."""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.1
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        test_data = json.loads(raw)

        # Run each test safely
        results = []
        for test in test_data.get("tests", []):
            # Append test line to original code
            full_code = payload.code.rstrip() + "\n" + test["input_code"]
            trace_result = trace_code(full_code, max_steps=100)
            results.append({
                "description": test["description"],
                "input_code": test["input_code"],
                "output": trace_result.get("output", "").strip(),
                "success": trace_result["success"],
                "error": trace_result.get("error", None)
            })

        print(f"[LiveCode Mentor] Auto tests done: {len(results)} ran")
        return {"tests": results}

    except json.JSONDecodeError as e:
        print(f"[LiveCode Mentor] JSON parse error: {e}")
        return {"tests": [], "error": "Could not parse test cases"}
    except Exception as e:
        print(f"[LiveCode Mentor] Auto test error: {e}")
        return {"tests": [], "error": str(e)}