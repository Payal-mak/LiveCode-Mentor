"""
LiveCode Mentor — apply_fixes.py
Run this from your backend/ folder:

    cd path/to/your/backend
    python apply_fixes.py

It patches main.py in-place with 3 targeted fixes.
A backup is saved as main.py.bak before any changes.
"""

import re, shutil, sys
from pathlib import Path

TARGET = Path("main.py")
if not TARGET.exists():
    print("❌  main.py not found. Run this from your backend/ directory.")
    sys.exit(1)

# ── Backup ────────────────────────────────────────────────────────────────────
shutil.copy(TARGET, TARGET.with_suffix(".py.bak"))
print("📦  Backup saved → main.py.bak")

src = TARGET.read_text(encoding="utf-8")

fixes_applied = 0

# ─────────────────────────────────────────────────────────────────────────────
# FIX 1 — /trace endpoint: C++ response must match trace shape, not auto-test
# ─────────────────────────────────────────────────────────────────────────────
OLD_TRACE = '''\
    if payload.language != "python":
    # For C++/Java — detect hardcoded inputs and show what we know
        is_hard = has_hardcoded_inputs(payload.code, payload.language)
        if is_hard:
            return {
                "tests": [{
                    "description": "Hardcoded input values detected",
                    "input_code": "Run locally to see output",
                    "output": "C++ code must be compiled and run locally",
                    "success": True,
                    "error": None,
                    "note": "hardcoded"
                }],
                "input_style": "hardcoded",
                "message": "C++ code detected \u2014 compile and run locally to see output"
            }
        return {
            "tests": [],
            "input_style": "none",
            "message": "Auto-testing only supports Python currently"
        }'''

NEW_TRACE = '''\
    if payload.language != "python":
        # C++/Java cannot be traced — return the correct trace-shaped response
        return {
            "steps":       [],
            "output":      "",
            "success":     False,
            "error":       "Step Through only works for Python. For C++, compile and run locally.",
            "total_steps": 0,
        }'''

# Normalise CRLF so matching works on Windows-saved files
src_normalised = src.replace("\r\n", "\n")

if OLD_TRACE.replace("\r\n", "\n") in src_normalised:
    src = src_normalised.replace(OLD_TRACE.replace("\r\n", "\n"), NEW_TRACE, 1)
    fixes_applied += 1
    print("✅  Fix 1 applied — /trace C++ now returns correct trace shape")
else:
    # Try a looser regex match in case whitespace differs
    pattern = re.compile(
        r'if payload\.language != "python":\s*\n'
        r'.*?# For C\+\+/Java.*?\n'
        r'.*?is_hard = has_hardcoded_inputs.*?\n'
        r'.*?if is_hard:.*?\n'
        r'(?:.*?\n)*?'
        r'.*?"message": "Auto-testing only supports Python currently"\s*\n'
        r'\s*\}',
        re.DOTALL
    )
    m = pattern.search(src_normalised)
    if m:
        src = src_normalised[:m.start()] + NEW_TRACE + src_normalised[m.end():]
        fixes_applied += 1
        print("✅  Fix 1 applied (regex) — /trace C++ now returns correct trace shape")
    else:
        print("⚠️   Fix 1 SKIPPED — pattern not found (may already be fixed)")


# ─────────────────────────────────────────────────────────────────────────────
# FIX 2 — /auto-test: C++ else block crashes on undefined `tree`/`classes`
# Replace the whole broken else block with a clean early return
# ─────────────────────────────────────────────────────────────────────────────
OLD_CPP_ELSE_MARKER = '            has_class = any(isinstance(n, ast.ClassDef) for n in ast.walk(tree))'
NEW_CPP_ELSE = '''\
        else:
            # C++ dynamic (cin) or no-input — cannot execute, inform user
            input_hint = "uses cin for input — provide values when compiling" if input_style == "dynamic" else "no input detected"
            return {
                "tests": [{
                    "description":  "C++ code detected",
                    "input_code":   f"g++ your_file.cpp -o out && ./out   # {input_hint}",
                    "output":       "\\u25b6 Compile and run locally to see output",
                    "success":      True,
                    "error":        None,
                    "note":         input_style
                }],
                "input_style": input_style,
                "message": "C++ code must be compiled and run locally. Auto-testing only supports Python."
            }'''

if OLD_CPP_ELSE_MARKER in src:
    # Find the `else:` that immediately precedes this marker and the block end
    # We'll find the else: + everything up to "    # ── Python only below this point"
    pattern2 = re.compile(
        r'        else:\s*\n'
        r'            # "none".*?\n'
        r'            has_class = any\(isinstance\(n, ast\.ClassDef\) for n in ast\.walk\(tree\)\).*?'
        r'            num_tests_expected = 3\s*\n',
        re.DOTALL
    )
    m2 = pattern2.search(src)
    if m2:
        src = src[:m2.start()] + NEW_CPP_ELSE + "\n\n" + src[m2.end():]
        fixes_applied += 1
        print("✅  Fix 2 applied — C++ auto-test else block fixed")
    else:
        print("⚠️   Fix 2 SKIPPED — couldn't isolate else block (may already be fixed)")
else:
    print("⚠️   Fix 2 SKIPPED — broken marker not found (may already be fixed)")


# ─────────────────────────────────────────────────────────────────────────────
# FIX 3 — /auto-test: mock_inputs undefined before use in trace_code calls
# ─────────────────────────────────────────────────────────────────────────────
OLD_GROQ_CALL = '    # ── Call Groq ─────────────────────────────────────────────────────────────\n    try:\n        response = client.chat.completions.create(\n            model="llama-3.3-70b-versatile",\n            messages=[{"role": "user", "content": prompt}],\n            max_tokens=150 if num_tests_expected == 1 else 400,'

NEW_GROQ_CALL = '    # ── Call Groq ─────────────────────────────────────────────────────────────\n    # mock_inputs used by trace_code for any input() calls in the Python code\n    mock_inputs = ["5", "1 2 3 4 5", "3", "1 2 3", "10", "hello", "0"]\n\n    try:\n        response = client.chat.completions.create(\n            model="llama-3.3-70b-versatile",\n            messages=[{"role": "user", "content": prompt}],\n            max_tokens=150 if num_tests_expected == 1 else 400,'

# Only patch if mock_inputs is NOT already defined near the Groq call
if '# mock_inputs used by trace_code for any input()' not in src:
    if OLD_GROQ_CALL in src:
        src = src.replace(OLD_GROQ_CALL, NEW_GROQ_CALL, 1)
        fixes_applied += 1
        print("✅  Fix 3 applied — mock_inputs defined before trace_code calls")
    else:
        # Looser: just insert mock_inputs before the try: block in auto_test
        pattern3 = re.compile(
            r'(    # ── Call Groq ─+\s*\n)'
            r'(    try:\s*\n'
            r'        response = client\.chat\.completions\.create\(\s*\n'
            r'            model="llama-3\.3-70b-versatile",\s*\n'
            r'            messages=\[.*?prompt.*?\],\s*\n'
            r'            max_tokens=150 if num_tests_expected == 1 else 400,)',
            re.DOTALL
        )
        m3 = pattern3.search(src)
        if m3:
            insert = (
                m3.group(1) +
                '    # mock_inputs used by trace_code for any input() calls\n'
                '    mock_inputs = ["5", "1 2 3 4 5", "3", "1 2 3", "10", "hello", "0"]\n\n' +
                m3.group(2)
            )
            src = src[:m3.start()] + insert + src[m3.end():]
            fixes_applied += 1
            print("✅  Fix 3 applied (regex) — mock_inputs defined before trace_code calls")
        else:
            print("⚠️   Fix 3 SKIPPED — pattern not found (may already be fixed)")
else:
    print("⚠️   Fix 3 SKIPPED — mock_inputs already defined")


# ─────────────────────────────────────────────────────────────────────────────
# FIX 4 — /recommendations: improve prompt for C++ articles
# ─────────────────────────────────────────────────────────────────────────────
OLD_ARTICLE_LINE = '2. One high-quality article/documentation page'
NEW_ARTICLE_LINE = '2. One high-quality article — for C++ prefer GeeksforGeeks, Medium, or cp-algorithms.com; for Python prefer official docs or Real Python'

if OLD_ARTICLE_LINE in src:
    src = src.replace(OLD_ARTICLE_LINE, NEW_ARTICLE_LINE, 1)
    fixes_applied += 1
    print("✅  Fix 4 applied — recommendations prompt improved for C++ articles")
else:
    print("⚠️   Fix 4 SKIPPED — article line not found (may already be fixed)")

OLD_RULES_BLOCK = '- If it\'s OOP \u2192 recommend OOP design problems\n- Difficulty: Easy or Medium ONLY'
NEW_RULES_BLOCK = '- If it\'s OOP \u2192 recommend OOP design problems\n- If it\'s a prime/math/number check \u2192 recommend Number Theory or Math tagged problems\n- Difficulty: Easy or Medium ONLY'

if OLD_RULES_BLOCK in src:
    src = src.replace(OLD_RULES_BLOCK, NEW_RULES_BLOCK, 1)
    fixes_applied += 1
    print("✅  Fix 4b applied — prime/math hint added to recommendations")
else:
    print("⚠️   Fix 4b SKIPPED")

OLD_ARTICLE_RULE = '- Use REAL LeetCode problem titles and actual URLs'
NEW_ARTICLE_RULE = '- Use REAL LeetCode problem titles and actual URLs\n- The article MUST be a real accessible URL — prefer geeksforgeeks.org, medium.com, or cp-algorithms.com'

if OLD_ARTICLE_RULE in src and 'geeksforgeeks.org' not in src:
    src = src.replace(OLD_ARTICLE_RULE, NEW_ARTICLE_RULE, 1)
    fixes_applied += 1
    print("✅  Fix 4c applied — article URL rule added")
else:
    print("⚠️   Fix 4c SKIPPED")

# ─────────────────────────────────────────────────────────────────────────────
# Write result
# ─────────────────────────────────────────────────────────────────────────────
TARGET.write_text(src, encoding="utf-8")
print(f"\n{'✅' if fixes_applied > 0 else '⚠️'}  Done — {fixes_applied} fix(es) applied to main.py")
print("   Restart your FastAPI server:  uvicorn main:app --reload --port 8000")
