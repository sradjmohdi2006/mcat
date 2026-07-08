import sqlite3
import os
import re

class Glossary:
    def __init__(self, db_path="glossary.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS glossary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_term TEXT UNIQUE,
                target_translation TEXT,
                description TEXT
            )
        """)
        conn.commit()
        conn.close()

    def add_term(self, source, target, description=""):
        if not source or not target:
            return
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO glossary (source_term, target_translation, description)
                VALUES (?, ?, ?)
                ON CONFLICT(source_term) DO UPDATE SET 
                    target_translation = excluded.target_translation,
                    description = excluded.description
            """, (source.strip(), target.strip(), description.strip()))
            conn.commit()
        except Exception as e:
            print(f"Error adding to Glossary: {e}")
        finally:
            conn.close()

    def remove_term(self, source):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM glossary WHERE source_term = ?", (source.strip(),))
        conn.commit()
        conn.close()

    def get_all_terms(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT source_term, target_translation, description FROM glossary")
        rows = cursor.fetchall()
        conn.close()
        return [{"source": r[0], "target": r[1], "description": r[2]} for r in rows]

    def _tokenize(self, text):
        return re.findall(r"\w+(?:'\w+)?", text.lower())

    def check_segment(self, text):
        if not text or not text.strip():
            return []

        tokens = self._tokenize(text)
        terms = self.get_all_terms()
        matched_terms = []

        for term in terms:
            src_lower = term["source"].lower()
            term_tokens = self._tokenize(src_lower)

            if not term_tokens:
                continue

            n_tokens = len(tokens)
            n_term = len(term_tokens)
            is_match = False
            for i in range(n_tokens - n_term + 1):
                if tokens[i:i+n_term] == term_tokens:
                    is_match = True
                    break

            if is_match:
                matched_terms.append(term)

        return matched_terms
