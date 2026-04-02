from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import ast
import json
import re
from dotenv import load_dotenv
from groq import Groq

from database import (
    init_db, save_concepts, save_mistake, get_stats,
    get_experience_level, log_session, MAJOR_DSA,
    update_score, get_score, get_score_history,
    award_badge, get_badges, get_fix_count
)
from tracer import trace_code
from classifier import get_all_concepts

load_dotenv()

app = FastAPI()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize DB after app is created
init_db()

#--------------------------------------------------------------------------------------------------------

class CodePayload(BaseModel):
    code: str
    language: str = "python"
    fileName: str = ""
    trigger: str = "change"
    mode: str = "learning"  # "learning" or "developer"

class HintPayload(BaseModel):
    code: str
    mistake_type: str
    language: str = "python"

class LinePayload(BaseModel):
    code: str
    line: str
    line_number: int
    language: str = "python"
    context: str = ""

# FR5: AST-based concept detector
class ConceptDetector(ast.NodeVisitor):
    def __init__(self):
        self.concepts = set()  # set prevents duplicates

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

    def visit_Dict(self, node):
        self.concepts.add("dictionary")
        self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            name = node.func.id
            if name == "print":
                self.concepts.add("print function")
            elif name == "range":
                self.concepts.add("range function")
            elif name == "len":
                self.concepts.add("len function")
            elif name == "input":
                self.concepts.add("user input")
            elif name in ("map", "filter", "zip"):
                self.concepts.add("higher-order functions")
            elif name in ("sorted", "sort"):
                self.concepts.add("sorting")
        self.generic_visit(node)

    def visit_List(self, node):
        # Only count if it's an assignment, not just any list
        self.concepts.add("list / array")
        self.generic_visit(node)

def detect_concepts(code: str) -> list:
    try:
        tree = ast.parse(code)
        detector = ConceptDetector()
        detector.visit(tree)
        # Return sorted unique list, max 10 concepts
        return sorted(list(detector.concepts))[:10]
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

# ─────────────────────────────────────────────────────────────────────────────
# KNOWN COMPLEXITY HINTS — used to anchor Groq instead of letting it guess
# Keys match exactly what classifier.py detect_algorithm_type() returns
# ─────────────────────────────────────────────────────────────────────────────
_KNOWN_COMPLEXITY: dict[str, tuple[str, str]] = {
    "Binary Search":       ("O(log n)",         "O(1)"),
    "Two Pointer":         ("O(n)",              "O(1)"),
    "Sliding Window":      ("O(n)",              "O(1)"),
    "Dynamic Programming": ("O(n²) typical",    "O(n) to O(n²)"),
    "Backtracking":        ("O(2ⁿ) worst-case", "O(n) call stack"),
    "Graph BFS":           ("O(V + E)",          "O(V)"),
    "Graph DFS":           ("O(V + E)",          "O(V) call stack"),
    "Greedy":              ("O(n log n)",        "O(1)"),
    "Divide and Conquer":  ("O(n log n)",        "O(n)"),
    "Recursion":           ("O(2ⁿ) worst-case", "O(n) call stack"),
    "Sorting":             ("O(n log n) avg",    "O(n)"),
    "Linked List":         ("O(n)",              "O(n)"),
    "Stack":               ("O(n)",              "O(n)"),
    "Queue":               ("O(n)",              "O(n)"),
    "Hash Map":            ("O(n)",              "O(n)"),
    "Tree Traversal":      ("O(n)",              "O(h) where h = tree height"),
    "Heap":                ("O(n log n)",        "O(n)"),
}


# ─────────────────────────────────────────────────────────────────────────────
# ALGORITHM-SPECIFIC EXPLANATION INSTRUCTIONS
# Tells Groq exactly what to focus on for each DSA category
# ─────────────────────────────────────────────────────────────────────────────
_ALGO_INSTRUCTIONS: dict[str, str] = {
    "Binary Search": (
        "Explain the search space halving. Mention what 'left', 'right', and 'mid' represent. "
        "Explain the condition that determines which half to discard."
    ),
    "Two Pointer": (
        "Explain why two pointers are used instead of a nested loop. "
        "Describe what each pointer tracks and how they converge."
    ),
    "Sliding Window": (
        "Explain the window concept — what it 'slides' over and why. "
        "Describe how the window expands or shrinks."
    ),
    "Dynamic Programming": (
        "Explain the DP state definition first. Then explain the recurrence/transition. "
        "Mention whether this is top-down (memoization) or bottom-up (tabulation). "
        "If a DP table exists, describe what each cell means."
    ),
    "Backtracking": (
        "Explain the state space tree this code is exploring. "
        "Identify the 'is_valid' / pruning condition. "
        "Describe what one 'branch' of the recursion tree looks like."
    ),
    "Graph BFS": (
        "Explain the layer-by-layer traversal. Mention the role of the queue and the visited set. "
        "Describe what one BFS level looks like conceptually."
    ),
    "Graph DFS": (
        "Explain the depth-first exploration. Mention the role of the stack (or call stack for recursive DFS). "
        "Describe when backtracking happens."
    ),
    "Recursion": (
        "Identify the base case and recursive case explicitly. "
        "Describe what one level of the recursion tree looks like. "
        "Explain how the call stack unwinds."
    ),
    "Divide and Conquer": (
        "Explain the three phases: Divide, Conquer, Combine. "
        "Describe what the subproblems are and how results are merged."
    ),
    "Sorting": (
        "Name the sorting algorithm and explain its comparison/swap strategy. "
        "Explain why the time complexity is what it is (e.g. why merge sort is O(n log n))."
    ),
    "Tree Traversal": (
        "Identify the traversal order (inorder / preorder / postorder / level-order). "
        "Explain what visiting a node means and in what order children are processed."
    ),
    "Greedy": (
        "Explain the greedy choice made at each step. "
        "Describe why a locally optimal choice leads to a globally optimal solution here."
    ),
    "Heap": (
        "Explain the heap property being maintained. "
        "Describe when elements are pushed vs. popped and what that achieves."
    ),
    "Linked List": (
        "Explain the pointer manipulation. Describe what 'head', 'current', and 'next' point to at each step. "
        "If traversal or insertion/deletion is happening, describe the pointer re-linking."
    ),
    "Hash Map": (
        "Explain what is being stored in the map and why. "
        "Describe how the hash map reduces time complexity vs. a brute-force approach."
    ),
}


def _build_complexity_hint(algorithms: list) -> tuple[str, str]:
    """
    Returns (time_hint, space_hint) strings from the first recognized algorithm.
    Falls back to empty strings so Groq must figure it out itself.
    """
    for algo in (algorithms or []):
        if algo in _KNOWN_COMPLEXITY:
            return _KNOWN_COMPLEXITY[algo]
    return ("", "")


def _build_algo_context(algorithms: list, paradigms: list, language: str) -> str:
    """
    Builds a context block injected into the prompt so Groq knows
    exactly what type of code it is analyzing.
    """
    lines = []

    if language == "cpp":
        lines.append("Language: C++ — explain memory management, pointers, or STL containers if relevant.")
    elif language == "java":
        lines.append("Language: Java — note class structure and OOP patterns if relevant.")

    if algorithms:
        lines.append(f"Detected algorithm type(s): {', '.join(algorithms)}")
        # Add the specific instruction for the primary algorithm
        primary = algorithms[0]
        if primary in _ALGO_INSTRUCTIONS:
            lines.append(f"Focus on: {_ALGO_INSTRUCTIONS[primary]}")

    if paradigms:
        lines.append(f"Detected paradigm(s): {', '.join(paradigms)}")
        if "Object-Oriented Programming" in paradigms:
            lines.append("Explain class design, attributes, and method responsibilities.")
        if "Functional Programming" in paradigms:
            lines.append("Explain lambda/list comprehension/generator usage and why it's used here.")

    return "\n".join(lines)


async def get_explanation(
    code: str,
    language: str,
    concepts: list,
    mode: str = "learning",
    algorithms: list = None,
    paradigms: list = None
) -> dict:
    level = get_experience_level(concepts)
    algorithms = algorithms or []
    paradigms  = paradigms  or []

    print(f"[LiveCode Mentor] get_explanation | level={level} | mode={mode} | "
          f"algos={algorithms} | paradigms={paradigms} | lang={language}")

    algo_context   = _build_algo_context(algorithms, paradigms, language)
    time_hint, space_hint = _build_complexity_hint(algorithms)

    # ── Complexity hint string to anchor Groq ─────────────────────────────────
    complexity_hint = ""
    if time_hint and space_hint:
        complexity_hint = (
            f'\nIMPORTANT: The expected complexity for this algorithm is '
            f'Time {time_hint}, Space {space_hint}. '
            f'Use these as your answer unless the specific code clearly differs — explain why.'
        )

    # ── JSON template (same shape for all modes) ─────────────────────────────
    json_template = (
        '{'
        '"explanation": "...", '
        f'"concepts": {json.dumps(concepts)}, '
        '"has_error": false, '
        '"friendly_error": null, '
        f'"level": "{level if mode != "developer" else "developer"}", '
        '"time_complexity": {"notation": "O(...)", "reason": "..."}, '
        '"space_complexity": {"notation": "O(...)", "reason": "..."}'
        '}'
    )

    # ─────────────────────────────────────────────────────────────────────────
    # DEVELOPER MODE — unchanged logic, just now passes through algo context
    # ─────────────────────────────────────────────────────────────────────────
    if mode == "developer":
        prompt = f"""Summarize this {language} code in ONE concise technical sentence.
No analogies. No beginner explanations. Just what it does and its complexity.
{algo_context}
{complexity_hint}

Code:
```{language}
{code}
```

Return ONLY this JSON (no markdown, no backticks):
{json_template}"""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=250,
            temperature=0.1
        )
        raw = response.choices[0].message.content.strip()
        return _parse_or_fallback(raw, concepts, "developer")

    # ─────────────────────────────────────────────────────────────────────────
    # LEARNING MODE — adaptive by level + algorithm-specific instructions
    # ─────────────────────────────────────────────────────────────────────────

    # Decide if this is complex DSA code — affects explanation depth
    is_complex_dsa = bool(algorithms) and any(a in _ALGO_INSTRUCTIONS for a in algorithms)

    if level == "beginner":
        if is_complex_dsa:
            style = f"""Explain this to a complete beginner who has never seen {algorithms[0]} before.
Start with a 1-sentence real-world analogy (e.g. "Binary search is like opening a dictionary in the middle...").
Then explain step-by-step what the code does in plain English. 4 sentences max.
Avoid ALL jargon — if you must use a term, define it in the same sentence."""
        else:
            style = """Explain this like the student has never coded before.
Use a simple real-world analogy. 3 sentences max.
Avoid ALL technical jargon."""

    elif level == "intermediate":
        if is_complex_dsa:
            style = f"""Explain this to someone who knows basic programming but is learning {algorithms[0]}.
Name the algorithm/technique. Explain HOW it works in this code (not just what it does).
Be specific about the key variables, conditions, or data structures involved. 3 sentences max."""
        else:
            style = """Explain this to someone who understands basic programming.
Be clear and concise. 2 sentences maximum."""

    else:  # expert
        if is_complex_dsa:
            style = f"""Give a precise technical explanation for an expert who knows {algorithms[0]}.
Focus on the specific implementation choices: time/space trade-offs, edge cases handled, 
any non-obvious optimizations. 2 sentences max."""
        else:
            style = """Give a concise 1-sentence technical summary.
Assume expert-level knowledge."""

    # ── Full learning mode prompt ─────────────────────────────────────────────
    prompt = f"""You are LiveCode Mentor, an adaptive coding tutor.

STUDENT LEVEL: {level}
{style}

{f"ALGORITHM CONTEXT:{chr(10)}{algo_context}" if algo_context else ""}
{complexity_hint}

Analyze this {language} code:
```{language}
{code}
```

Return ONLY valid JSON (no markdown, no backticks, no commentary before or after):
{json_template}

Rules:
- "explanation" must follow the style instructions above exactly
- "time_complexity.notation" and "space_complexity.notation" must be Big-O strings like "O(n log n)"
- "time_complexity.reason" and "space_complexity.reason" must each be one line, max 12 words
- If the code is too short to analyze (< 3 lines), set both complexities to "O(1)"
- Never put markdown, code blocks, or extra text outside the JSON"""

    # More tokens for complex DSA — it genuinely needs more output
    max_tokens = 800 if is_complex_dsa else 600

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.2   # lower than before — less hallucination on complexity
    )

    raw = response.choices[0].message.content.strip()
    print(f"[LiveCode Mentor] Groq raw ({level}, complex={is_complex_dsa}): {raw[:120]}...")
    return _parse_or_fallback(raw, concepts, level)


# ─────────────────────────────────────────────────────────────────────────────
# SHARED PARSE HELPER — extracted so both modes use identical fallback logic
# ─────────────────────────────────────────────────────────────────────────────
def _parse_or_fallback(raw: str, concepts: list, level: str) -> dict:
    """
    Try to parse Groq's response as JSON.
    If it fails, strip common wrapping artifacts and retry once.
    Falls back to a plain-text explanation dict on second failure.
    """
    # Attempt 1: direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Attempt 2: strip markdown fences Groq sometimes adds despite instructions
    cleaned = raw
    if "```" in cleaned:
        # Extract content between first ``` and last ```
        parts = cleaned.split("```")
        # parts[1] is between first and second fence — strip language hint if present
        if len(parts) >= 3:
            inner = parts[1]
            if inner.startswith("json"):
                inner = inner[4:]
            cleaned = inner.strip()

    # Sometimes Groq adds text before the JSON object
    brace_start = cleaned.find('{')
    brace_end   = cleaned.rfind('}')
    if brace_start != -1 and brace_end != -1:
        cleaned = cleaned[brace_start:brace_end + 1]

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Final fallback — return whatever text Groq gave as the explanation
    return {
        "explanation":      raw,
        "concepts":         concepts,
        "has_error":        False,
        "friendly_error":   None,
        "level":            level,
        "time_complexity":  None,
        "space_complexity": None,
        "algorithms":       [],
        "paradigms":        []
    }
    
@app.get("/health")
def health():
    return {"status": "LiveCode Mentor backend running ✅"}

@app.post("/analyze")
async def analyze(payload: CodePayload):
    print(f"[LiveCode Mentor] Analyzing ({payload.trigger}) - {len(payload.code)} chars")

    # FR5: Detect concepts FIRST (needed by all branches below)
    basic_concepts = detect_concepts(payload.code)
    print(f"[LiveCode Mentor] Basic concepts: {basic_concepts}")

    # H3: Deep DSA classification — paradigms + algorithm types + merged list
    classification = get_all_concepts(payload.code, payload.language, basic_concepts)
    algorithms   = classification["algorithms"]
    paradigms    = classification["paradigms"]
    all_concepts = classification["all_concepts"]
    print(f"[LiveCode Mentor] Algorithms: {algorithms} | Paradigms: {paradigms}")

    # FR4: Check syntax AFTER concepts are defined
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
                "mistake": None,
                "algorithms": [],
                "paradigms": [],
                "time_complexity": None,
                "space_complexity": None,
                "level": "beginner"
            }

    # FR12: Save concepts to DB — only on save trigger
    if payload.trigger == 'save':
        saved = save_concepts(all_concepts)
        print(f"[LiveCode Mentor] Saved {saved} major concepts to DB")
    log_session("analyze", f"trigger:{payload.trigger}")

    # FR9: Detect mistakes
    mistake_result = detect_mistakes(payload.code)
    print(f"[LiveCode Mentor] Mistakes: {mistake_result}")

    # FR12: Save mistake to DB — only on save trigger
    if payload.trigger == 'save' and mistake_result["has_mistake"] and mistake_result["mistake"]:
        save_mistake(mistake_result["mistake"]["type"])

    # FR3: Get AI explanation
    try:
        result = await get_explanation(
            payload.code,
            payload.language,
            all_concepts,
            payload.mode,
            algorithms=algorithms,
            paradigms=paradigms
        )
        result["mistake"]    = mistake_result
        result["algorithms"] = algorithms
        result["paradigms"]  = paradigms
        return result
    except Exception as e:
        print(f"[LiveCode Mentor] Error: {e}")
        return {
            "explanation":    "Could not analyze code. Please try again.",
            "concepts":       all_concepts,
            "has_error":      False,
            "friendly_error": None,
            "mistake":        mistake_result,
            "algorithms":     algorithms,
            "paradigms":      paradigms,
            "time_complexity": None,
            "space_complexity": None,
            "level":          "beginner"
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
        # Award points for fixing the bug
        new_total = update_score(+10, "Fixed a bug ✓")
        newly_earned = check_and_award_badges(new_total)
        new_badge_details = [b for b in BADGE_DEFS if b["id"] in newly_earned]
        return {
            "fixed": True,
            "message": "Great job! Issue resolved! 🎉",
            "score_delta": +10,
            "new_score": new_total,
            "new_badges": new_badge_details
        }
    else:
        return {
            "fixed": False,
            "message": "Not quite yet — check the hint again!",
            "score_delta": 0,
            "new_score": get_score(),
            "new_badges": []
        }
    
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

# Reset stats — clear inflated data from DB
@app.post("/reset-stats")
def reset_stats():
    from database import get_conn
    conn = get_conn()
    try:
        conn.execute("DELETE FROM concept_history")
        conn.execute("DELETE FROM mistake_history")
        conn.commit()
    finally:
        conn.close()
    return {"status": "ok", "message": "Stats reset successfully"}

# FR23: Current-code mistakes — tracks ONLY current code's issues (not lifetime)
@app.post("/current-mistakes")
async def current_mistakes(payload: CodePayload):
    mistake_result = detect_mistakes(payload.code)
    concepts = detect_concepts(payload.code)
    major_lower = {m.lower() for m in MAJOR_DSA}
    major = [c for c in concepts if c.lower() in major_lower]
    return {
        "has_mistake": mistake_result["has_mistake"],
        "mistake": mistake_result.get("mistake"),
        "major_concepts_count": len(major),
        "major_concepts": major
    }

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

    # Detect if code uses input() and generate smart mock values
    mock_inputs = ["5", "1 2 3 4 5", "3", "1 2 3", "10", "hello", "0"]

    try:
        tree = ast.parse(payload.code)
        has_input = any(
            isinstance(node, ast.Call) and
            isinstance(node.func, ast.Name) and
            node.func.id == 'input'
            for node in ast.walk(tree)
        )

        if has_input:
            # Ask Groq for smart mock inputs
            prompt = f"""This Python code uses input(). Generate realistic mock input values.
Code:
{payload.code}

Return ONLY a JSON array of strings that would be valid inputs, in order:
["5", "1 2 3 4 5"]

Return ONLY the JSON array, nothing else."""
            try:
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=100,
                    temperature=0.1
                )
                raw = response.choices[0].message.content.strip()
                raw = raw.replace("```json", "").replace("```", "").strip()
                mock_inputs = json.loads(raw)
                print(f"[LiveCode Mentor] Mock inputs: {mock_inputs}")
            except:
                mock_inputs = ["5", "1 2 3 4 5", "3", "1 2 3"]

    except:
        pass

    result = trace_code(payload.code, max_steps=50, mock_inputs=mock_inputs)
    print(f"[LiveCode Mentor] Trace: {result['total_steps']} steps, success: {result['success']}")
    return result

# FR8: Auto test input generation + execution
# ─────────────────────────────────────────────────────────────────────────────
# H5: INPUT STYLE DETECTOR
# Returns whether code uses hardcoded literals, dynamic input(), or neither.
# Drives how many tests to show and what kind of prompt to send Groq.
# ─────────────────────────────────────────────────────────────────────────────
def detect_input_style(code: str, language: str) -> dict:
    """
    Returns:
      input_style : "hardcoded" | "dynamic" | "none"
      hardcoded_vars : list of variable names assigned with literals (Python only)
      has_input_call : bool — True if input() / cin detected
    """
    if language == "cpp":
        # Regex-based detection — AST not available for C++
        cpp_hardcoded = [
            r'vector\s*<\w+>\s*\w+\s*=\s*\{',   # vector<int> arr = {2, 7, 11}
            r'int\s+\w+\s*=\s*-?\d+',            # int target = 9
            r'string\s+\w+\s*=\s*"',             # string s = "hello"
            r'array\s*<\w+',                      # array<int, n> arr
            r'int\s+\w+\[\s*\d*\s*\]\s*=\s*\{',  # int arr[] = {1, 2, 3}
            r'char\s+\w+\[\s*\d*\s*\]\s*=\s*"',  # char s[] = "hello"
        ]
        has_hardcoded = any(re.search(p, code) for p in cpp_hardcoded)
        has_cin       = bool(re.search(r'\bcin\s*>>', code))

        if has_cin:
            return {"input_style": "dynamic", "hardcoded_vars": [], "has_input_call": True}
        if has_hardcoded:
            return {"input_style": "hardcoded", "hardcoded_vars": [], "has_input_call": False}
        return {"input_style": "none", "hardcoded_vars": [], "has_input_call": False}

    # ── Python — use AST ──────────────────────────────────────────────────────
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {"input_style": "none", "hardcoded_vars": [], "has_input_call": False}

    # Dynamic check — any input() call anywhere in the code
    has_input_call = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "input"
        for node in ast.walk(tree)
    )
    if has_input_call:
        return {"input_style": "dynamic", "hardcoded_vars": [], "has_input_call": True}

    # Hardcoded check — top-level variable assignments with literal values
    # (lists, dicts, sets, tuples, numbers, strings — but NOT input() or function calls)
    _LITERAL_TYPES = (
        ast.List, ast.Dict, ast.Set, ast.Tuple,
        ast.Constant,              # Python 3.8+ (covers str, int, float, bool)
        ast.Num, ast.Str, ast.Bytes  # older AST nodes — kept for 3.7 compat
    )
    hardcoded_vars = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and isinstance(node.value, _LITERAL_TYPES):
                    hardcoded_vars.append(target.id)

    if hardcoded_vars:
        return {"input_style": "hardcoded", "hardcoded_vars": hardcoded_vars, "has_input_call": False}

    return {"input_style": "none", "hardcoded_vars": [], "has_input_call": False}


# ─────────────────────────────────────────────────────────────────────────────
# H5: UPDATED /auto-test ENDPOINT
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/auto-test")
async def auto_test(payload: CodePayload):
    language = payload.language or "python"

    print(f"[LiveCode Mentor] Auto-test | lang={language} | {len(payload.code)} chars")

    # ── H5: Detect input style first — drives everything below ────────────────
    style_info  = detect_input_style(payload.code, language)
    input_style = style_info["input_style"]      # "hardcoded" | "dynamic" | "none"
    hard_vars   = style_info["hardcoded_vars"]   # e.g. ["arr", "target"]
    print(f"[LiveCode Mentor] Input style: {input_style} | hardcoded vars: {hard_vars}")

    # ── C++: can't execute — return informational result only ─────────────────
    if language == "cpp":
        if input_style == "hardcoded":
            # Extract the hardcoded variable lines to show as context
            var_lines = []
            for line in payload.code.splitlines():
                stripped = line.strip()
                # Show lines that look like variable declarations with values
                if re.search(
                    r'(vector|int|string|array|char|float|double)\s+\w+.*=',
                    stripped
                ):
                    var_lines.append(stripped)

            vars_display = "\n".join(var_lines[:5]) if var_lines else "Hardcoded values found"
            return {
                "tests": [{
                    "description":  "C++ code with hardcoded input values",
                    "input_code":   vars_display,
                    "output":       "▶ Compile and run locally to see output",
                    "success":      True,
                    "error":        None,
                    "note":         "hardcoded"
                }],
                "input_style": "hardcoded"
            }
        else:
            # Dynamic cin or no input — just tell user to run locally
            return {
                "tests": [],
                "error": "C++ execution requires local compilation. Use g++ to run.",
                "input_style": input_style
            }

    # ── Python only below this point ──────────────────────────────────────────
    try:
        tree = ast.parse(payload.code)
    except SyntaxError as e:
        return {"tests": [], "error": f"Syntax error: {e.msg}"}

    # Extract code structure for prompt context
    functions, variables, classes = [], [], []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            functions.append({
                "name": node.name,
                "args": [a.arg for a in node.args.args]
            })
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    variables.append(t.id)

    context_parts = []
    if functions:
        for f in functions:
            context_parts.append(f"Function: {f['name']}({', '.join(f['args'])})")
    if classes:
        context_parts.append(f"Classes: {', '.join(classes)}")
    if variables:
        context_parts.append(f"Variables defined: {', '.join(set(variables))}")
    context = "\n".join(context_parts) if context_parts else "No functions — just statements"

    # ── H5: Build prompt based on input style ─────────────────────────────────
    if input_style == "hardcoded":
        # 1 test only — use the existing hardcoded variables, don't redeclare
        hard_vars_str = ", ".join(hard_vars) if hard_vars else "the variables already defined"
        prompt = f"""You are a Python testing assistant.

Here is the code to test:
```python
{payload.code}
```

Code structure:
{context}

IMPORTANT: This code already has hardcoded input values ({hard_vars_str}).
Generate EXACTLY 1 test line that:
1. Is a single print() statement
2. Uses ONLY names already defined in the code — do NOT redeclare any variable
3. Calls the main function (if one exists) with the already-defined variables as arguments
4. If no function exists, just prints the result variable

Example — if code defines arr = [2,7,11] and function twoSum(nums, target):
Good: print(twoSum(arr, target))
Bad:  print(twoSum([2,7,11], 9))  ← don't hardcode values again

Return ONLY this JSON:
{{
  "tests": [
    {{"input_code": "print(functionName(var1, var2))", "description": "Run with hardcoded values"}}
  ]
}}

Return ONLY valid JSON. No markdown. No explanation."""

        num_tests_expected = 1

    elif input_style == "dynamic":
        # 3 tests — generate diverse realistic inputs for input() calls
        prompt = f"""You are a Python testing assistant.

Here is the code to test:
```python
{payload.code}
```

Code structure:
{context}

This code uses input() for dynamic values.
Generate EXACTLY 3 test lines. Each test is ONE print() statement appended after the code.

STRICT RULES:
1. Each test line is ONE single Python print() statement
2. It runs AFTER the code above — all functions/classes are already defined
3. Use ONLY names that exist in the code
4. Do NOT redeclare variables, do NOT rewrite the code
5. No semicolons, no multi-line code

Return ONLY this JSON:
{{
  "tests": [
    {{"input_code": "print(something)", "description": "short description"}},
    {{"input_code": "print(something_else)", "description": "short description"}},
    {{"input_code": "print(another_thing)", "description": "short description"}}
  ]
}}

Return ONLY valid JSON. No markdown. No explanation."""

        num_tests_expected = 3

    else:
        # "none" — no input, no hardcoded vars (e.g. pure logic, loops, classes)
        # Treat same as dynamic — 3 tests probing what exists
        prompt = f"""You are a Python testing assistant.

Here is the code to test:
```python
{payload.code}
```

Code structure:
{context}

Generate EXACTLY 3 test lines that probe the code's output or behavior.
Each test is ONE print() statement appended after the code.

STRICT RULES:
1. Each line is ONE single print() statement
2. It runs AFTER the code above — all names already exist
3. Use ONLY names that appear in the code above
4. No semicolons, no multi-line code

Return ONLY this JSON:
{{
  "tests": [
    {{"input_code": "print(something)", "description": "short description"}},
    {{"input_code": "print(something_else)", "description": "short description"}},
    {{"input_code": "print(another_thing)", "description": "short description"}}
  ]
}}

Return ONLY valid JSON. No markdown. No explanation."""

        num_tests_expected = 3

    # ── Call Groq ─────────────────────────────────────────────────────────────
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150 if num_tests_expected == 1 else 400,
            temperature=0.1
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()

        # Same 2-attempt parse as _parse_or_fallback
        try:
            test_data = json.loads(raw)
        except json.JSONDecodeError:
            brace_start = raw.find('{')
            brace_end   = raw.rfind('}')
            if brace_start != -1 and brace_end != -1:
                test_data = json.loads(raw[brace_start:brace_end + 1])
            else:
                raise

        # ── Run each test via trace_code ──────────────────────────────────────
        # For hardcoded style: Groq returns 1 test, cap at 1
        # For dynamic/none:    Groq returns 3, cap at 3
        tests_to_run = test_data.get("tests", [])[:num_tests_expected]

        results = []
        for test in tests_to_run:
            full_code   = payload.code.rstrip() + "\n" + test["input_code"]
            trace_result = trace_code(full_code, max_steps=100)
            results.append({
                "description": test.get("description", ""),
                "input_code":  test["input_code"],
                "output":      trace_result.get("output", "").strip(),
                "success":     trace_result["success"],
                "error":       trace_result.get("error") or None,
                "note":        input_style   # H5: "hardcoded" | "dynamic" | "none"
            })

        print(f"[LiveCode Mentor] Auto tests done: {len(results)} ran (style={input_style})")
        return {"tests": results, "input_style": input_style}

    except json.JSONDecodeError as e:
        print(f"[LiveCode Mentor] JSON parse error: {e}")
        return {"tests": [], "error": "Could not parse test cases", "input_style": input_style}
    except Exception as e:
        print(f"[LiveCode Mentor] Auto test error: {e}")
        return {"tests": [], "error": str(e), "input_style": input_style}

@app.post("/explain-line")
async def explain_line(payload: LinePayload):
    print(f"[LiveCode Mentor] Explaining line {payload.line_number}: {payload.line}")

    prompt = f"""You are LiveCode Mentor, a friendly coding tutor.

A student clicked on this specific line of code and wants to understand it deeply:

Line {payload.line_number}: {payload.line}

Full code context:
```{payload.language}
{payload.code}
```

Explain ONLY this specific line in detail. Cover:
1. What this line does step by step
2. Why it is needed in this program
3. What would happen if it was removed or changed
4. Any important concepts used in this line

Be beginner-friendly. Use simple language and analogies.
Keep explanation under 5 sentences."""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.3
        )
        explanation = response.choices[0].message.content.strip()
        return {
            "line": payload.line,
            "line_number": payload.line_number,
            "explanation": explanation
        }
    except Exception as e:
        print(f"[LiveCode Mentor] Explain line error: {e}")
        return {
            "line": payload.line,
            "line_number": payload.line_number,
            "explanation": "Could not explain this line. Please try again."
        }
        
# ─────────────────────────────────────────────────────────────────────────────
# GAMIFICATION ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

class ScorePayload(BaseModel):
    delta: int
    reason: str

# Badge definitions — shared between backend and frontend
BADGE_DEFS = [
    {
        "id": "first_fix",
        "name": "Bug Squasher",
        "icon": "🐛",
        "desc": "Fixed your first bug without giving up"
    },
    {
        "id": "no_paste_50",
        "name": "Pure Coder",
        "icon": "✍️",
        "desc": "Typed 50+ chars in a row without copy-pasting"
    },
    {
        "id": "dsa_3",
        "name": "DSA Explorer",
        "icon": "🧭",
        "desc": "Used 3 different DSA concepts"
    },
    {
        "id": "score_50",
        "name": "Half Century",
        "icon": "🌟",
        "desc": "Reached 50 points"
    },
    {
        "id": "score_100",
        "name": "Century",
        "icon": "💯",
        "desc": "Reached 100 points"
    },
    {
        "id": "fix_3",
        "name": "Debugger",
        "icon": "🔧",
        "desc": "Fixed 3 bugs independently"
    },
    {
        "id": "fix_10",
        "name": "Bug Hunter",
        "icon": "🎯",
        "desc": "Fixed 10 bugs total"
    },
    {
        "id": "dsa_5",
        "name": "Algorithm Ace",
        "icon": "🚀",
        "desc": "Used 5 different DSA algorithms"
    },
]

def check_and_award_badges(current_score: int) -> list:
    """Check all badge conditions and award any newly earned badges."""
    newly_earned = []

    # Score-based badges
    if current_score >= 50:
        if award_badge("score_50"):
            newly_earned.append("score_50")
    if current_score >= 100:
        if award_badge("score_100"):
            newly_earned.append("score_100")

    # Fix-based badges
    fixes = get_fix_count()
    if fixes >= 1:
        if award_badge("first_fix"):
            newly_earned.append("first_fix")
    if fixes >= 3:
        if award_badge("fix_3"):
            newly_earned.append("fix_3")
    if fixes >= 10:
        if award_badge("fix_10"):
            newly_earned.append("fix_10")

    # DSA concept badges
    stats = get_stats()
    unique_dsa = stats.get("unique_major_concepts", 0)
    if unique_dsa >= 3:
        if award_badge("dsa_3"):
            newly_earned.append("dsa_3")
    if unique_dsa >= 5:
        if award_badge("dsa_5"):
            newly_earned.append("dsa_5")

    return newly_earned

@app.post("/score")
async def add_score(payload: ScorePayload):
    new_total = update_score(payload.delta, payload.reason)
    newly_earned = check_and_award_badges(new_total)

    # Find badge details for newly earned
    new_badge_details = [
        b for b in BADGE_DEFS if b["id"] in newly_earned
    ]

    print(f"[LiveCode Mentor] Score update: {payload.delta:+d} ({payload.reason}) → total={new_total}")
    return {
        "score": new_total,
        "delta": payload.delta,
        "reason": payload.reason,
        "new_badges": new_badge_details
    }

@app.get("/score")
async def get_current_score():
    score = get_score()
    newly_earned = check_and_award_badges(score)
    earned_badge_ids = [b["badge_id"] for b in get_badges()]
    badge_details = [
        {**b, "earned": b["id"] in earned_badge_ids}
        for b in BADGE_DEFS
    ]
    return {
        "score": score,
        "badges": badge_details,
        "history": get_score_history(5),
        "new_badges": [b for b in badge_details if b["id"] in newly_earned]
    }