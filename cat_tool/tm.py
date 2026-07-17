import sqlite3
import os
from datetime import datetime
from rapidfuzz import fuzz
import numpy as np


class TranslationMemory:
    def __init__(self, db_path="translation_memory.db"):
        self.db_path = db_path
        self._embedding_model = None
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
        for col in ("source_lang", "target_lang", "embedding"):
            try:
                cursor.execute(f"ALTER TABLE translation_memory ADD COLUMN {col} TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass
        conn.commit()
        conn.close()

    def _get_embedding_model(self):
        if self._embedding_model is None:
            try:
                from fastembed import TextEmbedding
                self._embedding_model = TextEmbedding("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
            except Exception as e:
                print(f"Failed to load embedding model: {e}")
                self._embedding_model = False
        return self._embedding_model if self._embedding_model is not False else None

    def _compute_embedding(self, text):
        model = self._get_embedding_model()
        if model is None or not text or not text.strip():
            return None
        try:
            embeddings = list(model.embed([text.strip()]))
            if embeddings:
                return np.array(embeddings[0], dtype=np.float32).tobytes()
        except Exception as e:
            print(f"Embedding failed: {e}")
        return None

    def add_translation(self, source, target, source_lang="", target_lang=""):
        if not source or not source.strip():
            return
        if not target or not target.strip():
            return
        source = source.strip()
        target = target.strip()
        embedding_bytes = self._compute_embedding(source)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO translation_memory (source, target, source_lang, target_lang, embedding)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source) DO UPDATE SET
                    target = excluded.target,
                    source_lang = excluded.source_lang,
                    target_lang = excluded.target_lang,
                    embedding = excluded.embedding
            """, (source, target, source_lang.strip(), target_lang.strip(), embedding_bytes))
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

    def get_semantic_matches(self, query_source, limit=5, source_lang=None, target_lang=None):
        if not query_source or not query_source.strip():
            return []

        model = self._get_embedding_model()
        if model is None:
            return []

        query_source = query_source.strip()
        try:
            query_emb = list(model.embed([query_source]))[0]
            query_emb = np.array(query_emb, dtype=np.float32)
        except Exception as e:
            print(f"Query embedding failed: {e}")
            return []

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT source, target, source_lang, target_lang, embedding FROM translation_memory WHERE embedding IS NOT NULL AND embedding != ''")
        rows = cursor.fetchall()
        conn.close()

        q = query_source.lower()
        matches = []
        for source, target, sl, tl, emb_bytes in rows:
            if source_lang and sl and sl != source_lang:
                continue
            if target_lang and tl and tl != target_lang:
                continue
            if source.lower() == q:
                continue
            try:
                emb = np.frombuffer(emb_bytes, dtype=np.float32)
                sim = float(np.dot(query_emb, emb) / (np.linalg.norm(query_emb) * np.linalg.norm(emb) + 1e-10))
                score = round(max(0, sim * 100), 1)
                if score > 0:
                    matches.append({
                        "source": source,
                        "target": target,
                        "score": score,
                    })
            except Exception:
                continue

        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches[:limit]
