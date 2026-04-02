# backend/database.py
import sqlite3
import os

# ─────────────────────────────────────────────────────────────────────────────
# MAJOR DSA / CS CONCEPTS — only these are saved to DB and shown in progress.
#
# Includes BOTH formats:
#   • Old lowercase names  (from ConceptDetector / basic detection)
#   • New capitalized names (from classifier.py — H3 deep detection)
#
# Matching is always case-insensitive (see save_concepts), so both resolve
# correctly regardless of which detector produced them.
# ─────────────────────────────────────────────────────────────────────────────
MAJOR_DSA = {
    # ── Data Structures (old names kept for backward compat) ──────────────────
    "list / array",
    "linked list",          # also matches "Linked List" from classifier
    "stack",                # also matches "Stack"
    "queue",                # also matches "Queue"
    "hash map / dictionary",
    "dictionary",
    "tree",
    "graph",
    "heap",                 # also matches "Heap"
    "set",

    # ── Algorithms (old names) ────────────────────────────────────────────────
    "recursion",            # also matches "Recursion"
    "dynamic programming",  # also matches "Dynamic Programming"
    "binary search",        # also matches "Binary Search"
    "sorting algorithm",
    "sorting",              # also matches "Sorting"
    "graph traversal (bfs/dfs)",
    "two pointer",          # also matches "Two Pointer"
    "sliding window",       # also matches "Sliding Window"
    "backtracking",         # also matches "Backtracking"
    "divide and conquer",   # also matches "Divide and Conquer"
    "greedy algorithm",

    # ── NEW names from classifier.py (H3) ─────────────────────────────────────
    "Binary Search",
    "Two Pointer",
    "Sliding Window",
    "Dynamic Programming",
    "Backtracking",
    "Graph BFS",            # classifier returns this; old set had "graph traversal"
    "Graph DFS",            # classifier returns this
    "Greedy",               # classifier returns this; old set had "greedy algorithm"
    "Divide and Conquer",
    "Recursion",
    "Sorting",
    "Linked List",
    "Stack",
    "Queue",
    "Hash Map",             # classifier returns this; old set had "hash map / dictionary"
    "Tree Traversal",       # classifier returns this; old set had "tree"
    "Heap",

    # ── Paradigms (old names) ─────────────────────────────────────────────────
    "class / OOP",
    "inheritance",
    "polymorphism",
    "functional programming",
    "lambda function",

    # ── NEW paradigm names from classifier.py (H3) ────────────────────────────
    "Object-Oriented Programming",  # classifier returns this; old had "class / OOP"
    "Inheritance",
    "Functional Programming",
    "Procedural Programming",       # new from classifier
    "Async / Concurrency",          # new from classifier

    # ── Core Constructs ───────────────────────────────────────────────────────
    "try/except (error handling)",
    "async function",
    "list comprehension",
    "decorator",
    "generator",
    "higher-order functions",
}


# ─────────────────────────────────────────────────────────────────────────────
# DATABASE SETUP
# ─────────────────────────────────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), "learner.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS concept_history (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            concept  TEXT NOT NULL,
            seen_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mistake_history (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            mistake_type TEXT NOT NULL,
            fixed        INTEGER DEFAULT 0,
            seen_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS session_logs (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            event     TEXT NOT NULL,
            detail    TEXT,
            logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    init_scores_table()
    print("[LiveCode Mentor] Database initialized ✅")


# ─────────────────────────────────────────────────────────────────────────────
# CONCEPT SAVING
# ─────────────────────────────────────────────────────────────────────────────
# Build the lowercase lookup once at module load — O(1) membership checks
_MAJOR_DSA_LOWER = {m.lower() for m in MAJOR_DSA}


def save_concepts(concepts: list) -> int:
    """
    Save ONLY major DSA/CS concepts to DB.
    Matching is case-insensitive, so both 'recursion' and 'Recursion' are accepted.
    Deduplicates: same concept is not saved more than once per 5-minute window.
    Returns the count of concepts actually saved.
    """
    if not concepts:
        return 0

    major_only = [c for c in concepts if c.lower() in _MAJOR_DSA_LOWER]
    if not major_only:
        return 0

    saved = 0
    conn = get_conn()
    try:
        for concept in major_only:
            recent = conn.execute(
                """
                SELECT COUNT(*) FROM concept_history
                WHERE concept = ? AND seen_at > datetime('now', '-5 minutes')
                """,
                (concept,)
            ).fetchone()[0]

            if recent == 0:
                conn.execute(
                    "INSERT INTO concept_history (concept) VALUES (?)",
                    (concept,)
                )
                saved += 1

        conn.commit()
    finally:
        conn.close()

    return saved


# ─────────────────────────────────────────────────────────────────────────────
# MISTAKE TRACKING
# ─────────────────────────────────────────────────────────────────────────────
def save_mistake(mistake_type: str):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO mistake_history (mistake_type) VALUES (?)",
            (mistake_type,)
        )
        conn.commit()
    finally:
        conn.close()


def mark_mistake_fixed(mistake_type: str):
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE mistake_history SET fixed = 1 WHERE mistake_type = ? AND fixed = 0",
            (mistake_type,)
        )
        conn.commit()
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# EXPERIENCE LEVEL
# ─────────────────────────────────────────────────────────────────────────────
def get_experience_level(concepts: list) -> str:
    """
    Returns 'beginner' / 'intermediate' / 'expert' based on how many times
    the given concepts have been seen historically.
    """
    if not concepts:
        return "beginner"

    conn = get_conn()
    try:
        total = 0
        for concept in concepts:
            # Try exact match first, then case-insensitive
            count = conn.execute(
                "SELECT COUNT(*) FROM concept_history WHERE LOWER(concept) = LOWER(?)",
                (concept,)
            ).fetchone()[0]
            total += count
    finally:
        conn.close()

    avg = total / len(concepts)
    if avg < 3:
        return "beginner"
    elif avg < 7:
        return "intermediate"
    else:
        return "expert"


# ─────────────────────────────────────────────────────────────────────────────
# STATS  (used by Progress Tab)
# ─────────────────────────────────────────────────────────────────────────────
def get_stats() -> dict:
    """
    Returns progress stats for the sidebar Progress tab.
    Only major DSA concepts are included — trivial ones (print, range, etc.) 
    never reach the DB, so no extra filtering is needed here.
    """
    conn = get_conn()
    try:
        # All concepts in DB are already major (enforced by save_concepts)
        all_concepts = conn.execute(
            """
            SELECT concept, COUNT(*) AS cnt
            FROM concept_history
            GROUP BY LOWER(concept)      -- group case-insensitively
            ORDER BY cnt DESC
            """
        ).fetchall()

        # Build display list — deduplicate capitalization variants
        seen_lower = set()
        top_concepts = []
        for name, count in all_concepts:
            key = name.lower()
            if key not in seen_lower and key in _MAJOR_DSA_LOWER:
                seen_lower.add(key)
                top_concepts.append({"name": name, "count": count})
            if len(top_concepts) == 8:
                break

        total_mistakes = conn.execute(
            "SELECT COUNT(*) FROM mistake_history"
        ).fetchone()[0]

        fixed_mistakes = conn.execute(
            "SELECT COUNT(*) FROM mistake_history WHERE fixed = 1"
        ).fetchone()[0]

        total_concepts_seen = sum(c["count"] for c in top_concepts)
        unique_major = len(top_concepts)

    finally:
        conn.close()

    return {
        "top_concepts":          top_concepts,
        "total_mistakes":        total_mistakes,
        "fixed_mistakes":        fixed_mistakes,
        "total_concepts_seen":   total_concepts_seen,
        "unique_major_concepts": unique_major,
    }

# ─────────────────────────────────────────────────────────────────────────────
# GAMIFICATION — SCORING SYSTEM
# ─────────────────────────────────────────────────────────────────────────────
def init_scores_table():
    conn = get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scores (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                delta     INTEGER NOT NULL,
                reason    TEXT NOT NULL,
                total     INTEGER DEFAULT 0,
                logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS badges (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                badge_id    TEXT UNIQUE NOT NULL,
                earned_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    finally:
        conn.close()

def update_score(delta: int, reason: str) -> int:
    """Add or subtract points. Returns new total."""
    conn = get_conn()
    try:
        row = conn.execute("SELECT SUM(delta) FROM scores").fetchone()
        current = row[0] or 0
        new_total = max(0, current + delta)   # score never goes below 0
        actual_delta = new_total - current    # real delta after floor
        conn.execute(
            "INSERT INTO scores (delta, reason, total) VALUES (?, ?, ?)",
            (actual_delta, reason, new_total)
        )
        conn.commit()
        return new_total
    finally:
        conn.close()

def get_score() -> int:
    conn = get_conn()
    try:
        row = conn.execute("SELECT SUM(delta) FROM scores").fetchone()
        return max(0, row[0] or 0)
    finally:
        conn.close()

def get_score_history(limit: int = 10) -> list:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT delta, reason, total, logged_at FROM scores ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [{"delta": r[0], "reason": r[1], "total": r[2], "time": r[3]} for r in rows]
    finally:
        conn.close()

def award_badge(badge_id: str) -> bool:
    """Award a badge. Returns True if newly earned, False if already had it."""
    conn = get_conn()
    try:
        existing = conn.execute(
            "SELECT id FROM badges WHERE badge_id = ?", (badge_id,)
        ).fetchone()
        if existing:
            return False
        conn.execute("INSERT INTO badges (badge_id) VALUES (?)", (badge_id,))
        conn.commit()
        return True
    finally:
        conn.close()

def get_badges() -> list:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT badge_id, earned_at FROM badges ORDER BY earned_at DESC"
        ).fetchall()
        return [{"badge_id": r[0], "earned_at": r[1]} for r in rows]
    finally:
        conn.close()

def get_fix_count() -> int:
    """How many bugs fixed total."""
    conn = get_conn()
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM mistake_history WHERE fixed = 1"
        ).fetchone()[0]
    finally:
        conn.close()
        
def get_streak() -> int:
    """Count how many consecutive days the user has coded."""
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT DATE(logged_at) as day
            FROM session_logs
            GROUP BY DATE(logged_at)
            ORDER BY day DESC
            """
        ).fetchall()
        if not rows:
            return 0
        from datetime import date, timedelta
        streak = 0
        today = date.today()
        for i, (day_str,) in enumerate(rows):
            day = date.fromisoformat(day_str)
            expected = today - timedelta(days=i)
            if day == expected:
                streak += 1
            else:
                break
        return streak
    finally:
        conn.close()
        
# ─────────────────────────────────────────────────────────────────────────────
# SESSION LOGGING
# ─────────────────────────────────────────────────────────────────────────────
def log_session(event: str, detail: str = ""):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO session_logs (event, detail) VALUES (?, ?)",
            (event, detail)
        )
        conn.commit()
    finally:
        conn.close()
        