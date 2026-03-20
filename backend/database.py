import sqlite3, os

DB_PATH = "backend/learner.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS concept_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        concept TEXT, seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS mistake_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mistake_type TEXT, fixed INTEGER DEFAULT 0,
        seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit(); conn.close()

def save_concepts(concepts):
    conn = sqlite3.connect(DB_PATH)
    for c in concepts:
        conn.execute("INSERT INTO concept_history (concept) VALUES (?)", (c,))
    conn.commit(); conn.close()

def get_stats():
    conn = sqlite3.connect(DB_PATH)
    concepts = conn.execute("SELECT concept, COUNT(*) as cnt FROM concept_history GROUP BY concept ORDER BY cnt DESC LIMIT 5").fetchall()
    mistakes = conn.execute("SELECT COUNT(*) FROM mistake_history").fetchone()[0]
    conn.close()
    return {"top_concepts": concepts, "total_mistakes": mistakes}