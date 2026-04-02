import sqlite3
import os

# Only track major DSA/CS concepts in progress — filter out trivial ones like 'print function'
MAJOR_DSA = {
    # Data Structures
    "list / array", "linked list", "stack", "queue",
    "hash map / dictionary", "dictionary", "tree", "graph", "heap", "set",
    # Algorithms
    "recursion", "dynamic programming", "binary search",
    "sorting algorithm", "sorting", "graph traversal (BFS/DFS)",
    "two pointer", "sliding window", "backtracking",
    "divide and conquer", "greedy algorithm",
    # Paradigms
    "class / OOP", "inheritance", "polymorphism",
    "functional programming", "lambda function",
    # Core Constructs (only complex ones)
    "try/except (error handling)", "async function",
    "list comprehension", "decorator", "generator",
    "higher-order functions"
}

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
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        concept TEXT NOT NULL,
        seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS mistake_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mistake_type TEXT NOT NULL,
        fixed INTEGER DEFAULT 0,
        seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS session_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event TEXT NOT NULL,
        detail TEXT,
        logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()
    conn.close()
    print("[LiveCode Mentor] Database initialized ✅")

def save_concepts(concepts: list):
    if not concepts:
        return
    # Only save major DSA concepts — skip trivial ones like 'print function'
    major_lower = {m.lower() for m in MAJOR_DSA}
    major_only = [c for c in concepts if c.lower() in major_lower]
    if not major_only:
        return
    conn = get_conn()
    try:
        for concept in major_only:
            # Dedup: skip if the same concept was saved within last 5 minutes
            recent = conn.execute(
                "SELECT COUNT(*) FROM concept_history WHERE concept = ? AND seen_at > datetime('now', '-5 minutes')",
                (concept,)
            ).fetchone()[0]
            if recent == 0:
                conn.execute(
                    "INSERT INTO concept_history (concept) VALUES (?)",
                    (concept,)
                )
        conn.commit()
    finally:
        conn.close()

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

def get_experience_level(concepts: list) -> str:
    if not concepts:
        return "beginner"
    conn = get_conn()
    try:
        total = 0
        for concept in concepts:
            count = conn.execute(
                "SELECT COUNT(*) FROM concept_history WHERE concept = ?",
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

def get_stats() -> dict:
    conn = get_conn()
    try:
        # Only show major DSA concepts in progress — build filter
        major_lower = {m.lower() for m in MAJOR_DSA}
        
        # Get ALL concepts from DB, filter to major only
        all_concepts = conn.execute(
            "SELECT concept, COUNT(*) as cnt FROM concept_history GROUP BY concept ORDER BY cnt DESC"
        ).fetchall()
        top_concepts = [
            {"name": c[0], "count": c[1]}
            for c in all_concepts
            if c[0].lower() in major_lower
        ][:8]  # Show top 8 major concepts
        
        total_mistakes = conn.execute(
            "SELECT COUNT(*) FROM mistake_history"
        ).fetchone()[0]
        fixed_mistakes = conn.execute(
            "SELECT COUNT(*) FROM mistake_history WHERE fixed = 1"
        ).fetchone()[0]
        
        # Count only major concepts seen
        total_concepts_seen = sum(c["count"] for c in top_concepts)
        unique_major = len(top_concepts)
    finally:
        conn.close()
    return {
        "top_concepts": top_concepts,
        "total_mistakes": total_mistakes,
        "fixed_mistakes": fixed_mistakes,
        "total_concepts_seen": total_concepts_seen,
        "unique_major_concepts": unique_major
    }

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