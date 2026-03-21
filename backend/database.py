import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "learner.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    
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
    conn = sqlite3.connect(DB_PATH)
    for concept in concepts:
        conn.execute(
            "INSERT INTO concept_history (concept) VALUES (?)", 
            (concept,)
        )
    conn.commit()
    conn.close()

def save_mistake(mistake_type: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO mistake_history (mistake_type) VALUES (?)",
        (mistake_type,)
    )
    conn.commit()
    conn.close()

def mark_mistake_fixed(mistake_type: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE mistake_history SET fixed = 1 WHERE mistake_type = ? AND fixed = 0",
        (mistake_type,)
    )
    conn.commit()
    conn.close()

def get_concept_count(concept: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute(
        "SELECT COUNT(*) FROM concept_history WHERE concept = ?",
        (concept,)
    ).fetchone()[0]
    conn.close()
    return count

def get_experience_level(concepts: list) -> str:
    if not concepts:
        return "beginner"
    conn = sqlite3.connect(DB_PATH)
    total = 0
    for concept in concepts:
        count = conn.execute(
            "SELECT COUNT(*) FROM concept_history WHERE concept = ?",
            (concept,)
        ).fetchone()[0]
        total += count
    conn.close()
    avg = total / len(concepts)
    if avg < 3:
        return "beginner"
    elif avg < 7:
        return "intermediate"
    else:
        return "expert"

def get_stats() -> dict:
    conn = sqlite3.connect(DB_PATH)
    
    top_concepts = conn.execute(
        "SELECT concept, COUNT(*) as cnt FROM concept_history GROUP BY concept ORDER BY cnt DESC LIMIT 5"
    ).fetchall()
    
    total_mistakes = conn.execute(
        "SELECT COUNT(*) FROM mistake_history"
    ).fetchone()[0]
    
    fixed_mistakes = conn.execute(
        "SELECT COUNT(*) FROM mistake_history WHERE fixed = 1"
    ).fetchone()[0]
    
    total_concepts_seen = conn.execute(
        "SELECT COUNT(*) FROM concept_history"
    ).fetchone()[0]
    
    conn.close()
    
    return {
        "top_concepts": [{"name": c[0], "count": c[1]} for c in top_concepts],
        "total_mistakes": total_mistakes,
        "fixed_mistakes": fixed_mistakes,
        "total_concepts_seen": total_concepts_seen
    }

def log_session(event: str, detail: str = ""):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO session_logs (event, detail) VALUES (?, ?)",
        (event, detail)
    )
    conn.commit()
    conn.close()