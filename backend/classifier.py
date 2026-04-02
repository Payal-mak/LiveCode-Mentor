# backend/classifier.py
# Hour 3 — Deep DSA Concept Detection
# Detects programming paradigms (via AST) + DSA algorithm types (via pattern matching)
# Works for Python AND C++

import ast
import re

# ─────────────────────────────────────────────
# MAJOR DSA SET  (shared with database.py)
# ─────────────────────────────────────────────
MAJOR_DSA = {
    "Binary Search", "Two Pointer", "Sliding Window",
    "Dynamic Programming", "Backtracking", "Graph BFS", "Graph DFS",
    "Greedy", "Divide and Conquer", "Recursion", "Sorting",
    "Linked List", "Stack", "Queue", "Hash Map", "Tree Traversal", "Heap",
    "Object-Oriented Programming", "Inheritance", "Functional Programming",
    "Procedural Programming", "Async / Concurrency",
}


# ─────────────────────────────────────────────
# 1. PROGRAMMING PARADIGM DETECTOR
# ─────────────────────────────────────────────
def detect_paradigm(code: str, language: str) -> list[str]:
    paradigms = []

    if language == "python":
        try:
            tree = ast.parse(code)
            has_class      = any(isinstance(n, ast.ClassDef)    for n in ast.walk(tree))
            has_inherit    = any(
                isinstance(n, ast.ClassDef) and n.bases
                for n in ast.walk(tree)
            )
            has_lambda     = any(isinstance(n, ast.Lambda)      for n in ast.walk(tree))
            has_listcomp   = any(isinstance(n, ast.ListComp)    for n in ast.walk(tree))
            has_genexp     = any(isinstance(n, ast.GeneratorExp) for n in ast.walk(tree))
            has_async      = any(isinstance(n, (ast.AsyncFunctionDef, ast.Await))
                                 for n in ast.walk(tree))
            has_func       = any(isinstance(n, ast.FunctionDef) for n in ast.walk(tree))

            if has_class:
                paradigms.append("Object-Oriented Programming")
            if has_inherit:
                paradigms.append("Inheritance")
            if has_lambda or has_listcomp or has_genexp:
                paradigms.append("Functional Programming")
            if has_async:
                paradigms.append("Async / Concurrency")
            if not has_class and has_func:
                paradigms.append("Procedural Programming")

        except SyntaxError:
            # Fallback to regex for syntactically incomplete code
            paradigms = _detect_paradigm_regex(code, "python")

    else:
        # C++ / other — use regex patterns
        paradigms = _detect_paradigm_regex(code, language)

    return paradigms


def _detect_paradigm_regex(code: str, language: str) -> list[str]:
    paradigms = []
    has_class = bool(re.search(r'\bclass\s+\w+', code))
    has_inherit = bool(re.search(r'\bclass\s+\w+\s*[:(]', code))   # Python or C++ style
    has_lambda = bool(re.search(r'\blambda\b|\[\s*\].*\(', code))
    has_template = bool(re.search(r'\btemplate\s*<', code))
    has_async = bool(re.search(r'\basync\b|\bawait\b|std::future|std::async', code))

    if has_class:
        paradigms.append("Object-Oriented Programming")
    if has_inherit:
        paradigms.append("Inheritance")
    if has_lambda or has_template:
        paradigms.append("Functional Programming")
    if has_async:
        paradigms.append("Async / Concurrency")

    return paradigms


# ─────────────────────────────────────────────
# 2. DSA ALGORITHM DETECTOR
#    Pattern-based — works for Python AND C++
# ─────────────────────────────────────────────
_ALGO_PATTERNS: dict[str, list[str]] = {
    "Binary Search": [
        r"binary.search", r"mid\s*=", r"\blo\b.*\bhi\b", r"\bleft\b.*\bright\b",
        r"while.*left.*<=.*right", r"while.*lo.*<=.*hi",
    ],
    "Two Pointer": [
        r"two.pointer", r"\bi\s*,\s*j\b", r"\bleft\s*,\s*right\b",
        r"\bstart\s*,\s*end\b", r"i\s*=\s*0.*j\s*=.*len",
    ],
    "Sliding Window": [
        r"sliding.window", r"\bwindow\b", r"\bcurr.sum\b", r"\bmax.sum\b",
        r"window.size", r"window.start",
    ],
    "Dynamic Programming": [
        r"\bdp\[", r"\bdp\s*=\s*\[", r"\bmemo\b", r"\bmemoize\b",
        r"tabulation", r"knapsack", r"lcs", r"longest.common",
        r"@lru_cache", r"@functools.lru_cache",
    ],
    "Backtracking": [
        r"backtrack", r"backtracking", r"is_valid", r"n.queens",
        r"def.*backtrack", r"void.*backtrack",
    ],
    "Graph BFS": [
        r"\bbfs\b", r"from collections import deque",
        r"queue\.append", r"queue\.popleft", r"deque\(\)",
        r"visited.*set\(\)", r"level.order",
    ],
    "Graph DFS": [
        r"\bdfs\b", r"def dfs", r"void dfs",
        r"stack\.append", r"stack\.pop\(\)",
        r"recursive.*visited",
    ],
    "Greedy": [
        r"\bgreedy\b", r"max.profit", r"min.cost",
        r"activity.selection", r"interval", r"sort.*key.*lambda",
    ],
    "Divide and Conquer": [
        r"merge.sort", r"quick.sort", r"def.*divide",
        r"divide.*conquer", r"mid\s*=.*\/\/.*2",
    ],
    "Recursion": [
        r"def factorial", r"def fib", r"return.*factorial",
        r"return.*fib\(", r"return.*n\s*\*.*\(n", r"base.case",
        r"recursive.call", r"int factorial", r"int fib",
    ],
    "Sorting": [
        r"bubble.sort", r"insertion.sort", r"selection.sort",
        r"merge.sort", r"quick.sort", r"\.sort\(\)", r"\bsorted\(",
        r"std::sort", r"qsort",
    ],
    "Linked List": [
        r"ListNode", r"\.next\s*=", r"head\.next",
        r"linked.list", r"struct.*Node", r"class.*Node",
    ],
    "Stack": [
        r"stack\.append", r"stack\.pop\b", r"stack\s*=\s*\[\]",
        r"def push", r"def pop", r"std::stack",
        r"push\(", r"\.top\(\)",
    ],
    "Queue": [
        r"\bdeque\b", r"queue\.append", r"queue\.popleft",
        r"std::queue", r"enqueue", r"dequeue",
    ],
    "Hash Map": [
        r"unordered_map", r"\bmp\[", r"counter\s*=\s*\{\}",
        r"freq\s*=\s*\{\}", r"hashmap", r"defaultdict",
        r"Counter\(", r"\.get\(.*0\)",
    ],
    "Tree Traversal": [
        r"inorder", r"preorder", r"postorder",
        r"root\.left", r"root\.right", r"\.left\s*=",
        r"TreeNode", r"struct.*Tree",
    ],
    "Heap": [
        r"heapq", r"heap\.push", r"heap\.pop",
        r"priority.queue", r"std::priority_queue",
        r"heappush", r"heappop",
    ],
}


def detect_algorithm_type(code: str) -> list[str]:
    """
    Returns list of detected DSA algorithm types (max 5).
    Works for Python and C++ by using regex patterns on raw source.
    """
    found = []
    code_lower = code.lower()

    for algo, patterns in _ALGO_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, code_lower):
                found.append(algo)
                break   # only count each algo once

    # Deduplicate while preserving insertion order
    seen = set()
    unique = []
    for a in found:
        if a not in seen:
            seen.add(a)
            unique.append(a)

    return unique[:5]   # cap at 5 — keeps UI clean


# ─────────────────────────────────────────────
# 3. UNIFIED CONCEPT MERGER
# ─────────────────────────────────────────────
def get_all_concepts(code: str, language: str, basic_concepts: list[str]) -> dict:
    """
    Returns merged concept dict for use in /analyze.
    Priority order: algorithms → paradigms → basic_concepts (deduplicated).
    """
    algorithms = detect_algorithm_type(code)
    paradigms  = detect_paradigm(code, language)

    # Merge, algorithms first
    merged = list(dict.fromkeys(algorithms + paradigms + basic_concepts))[:12]

    return {
        "algorithms": algorithms,
        "paradigms": paradigms,
        "all_concepts": merged,
    }