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
                source_lang TEXT DEFAULT '',
                target_lang TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        for col in ("source_lang", "target_lang"):
            try:
                cursor.execute(f"ALTER TABLE translation_memory ADD COLUMN {col} TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass
        conn.commit()
        conn.close()

    def add_translation(self, source, target, source_lang="", target_lang=""):
        if not source or not source.strip():
            return
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO translation_memory (source, target, source_lang, target_lang)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(source) DO UPDATE SET
                    target = excluded.target,
                    source_lang = excluded.source_lang,
                    target_lang = excluded.target_lang
            """, (source.strip(), target.strip(), source_lang.strip(), target_lang.strip()))
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

    def get_fuzzy_matches(self, query_source, min_score=50.0, limit=5, source_lang=None, target_lang=None):
        if not query_source or not query_source.strip():
            return []

        query_source = query_source.strip()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT source, target, source_lang, target_lang FROM translation_memory")
        rows = cursor.fetchall()
        conn.close()

        q = query_source.lower()
        matches = []
        for source, target, sl, tl in rows:
            if source_lang and sl and sl != source_lang:
                continue
            if target_lang and tl and tl != target_lang:
                continue
            s = source.lower()
            ratio = fuzz.ratio(q, s)
            sort_ratio = fuzz.token_sort_ratio(q, s)
            score = max(ratio, sort_ratio)
            if score >= min_score:
                matches.append({
                    "source": source,
                    "target": target,
                    "score": round(score, 1)
                })

        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches[:limit]
