import sqlite3
import os
from datetime import datetime
from rapidfuzz import fuzz

class TranslationMemory:
    def __init__(self, db_path="translation_memory.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS translation_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT UNIQUE,
                target TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def add_translation(self, source, target):
        if not source or not source.strip():
            return
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO translation_memory (source, target)
                VALUES (?, ?)
                ON CONFLICT(source) DO UPDATE SET target = excluded.target
            """, (source.strip(), target.strip()))
            conn.commit()
        except Exception as e:
            print(f"Error adding to TM: {e}")
        finally:
            conn.close()

    def clear(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM translation_memory")
        conn.commit()
        conn.close()

    def get_fuzzy_matches(self, query_source, min_score=50.0, limit=5):
        if not query_source or not query_source.strip():
            return []

        query_source = query_source.strip()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT source, target FROM translation_memory")
        rows = cursor.fetchall()
        conn.close()

        matches = []
        for source, target in rows:
            # We can use ratio, token_set_ratio, or WRatio for better matching
            score = fuzz.ratio(query_source.lower(), source.lower())
            if score >= min_score:
                matches.append({
                    "source": source,
                    "target": target,
                    "score": round(score, 1)
                })

        # Sort matches by score descending
        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches[:limit]
