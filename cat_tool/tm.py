import gc
import sqlite3
import os
import sys
from datetime import datetime
from rapidfuzz import fuzz
import numpy as np


def _load_vec_extension(conn):
    conn.enable_load_extension(True)
    if getattr(sys, 'frozen', False):
        our_dir = os.path.dirname(os.path.abspath(__file__))
        dll_path = os.path.normpath(os.path.join(our_dir, '..', 'sqlite_vec', 'vec0.dll'))
        conn.load_extension(dll_path)
    else:
        import sqlite_vec
        sqlite_vec.load(conn)
    conn.enable_load_extension(False)


class TranslationMemory:
    def __init__(self, db_path="translation_memory.db"):
        self.db_path = db_path
        self._embedding_model = None
        self._match_cache = {}
        self._cache_max = 256
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        _load_vec_extension(conn)
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
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_embeddings USING vec0(
                embedding int8[384] distance_metric=cosine
            )
        """)
        conn.commit()
        conn.close()

    def unload_model(self):
        if self._embedding_model is not None and self._embedding_model is not False:
            del self._embedding_model
        self._embedding_model = None
        gc.collect()

    def clear_cache(self):
        self._match_cache.clear()

    def _get_embedding_model(self):
        if self._embedding_model is None:
            try:
                from fastembed import TextEmbedding
                self._embedding_model = TextEmbedding("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
            except Exception as e:
                print(f"Failed to load embedding model: {e}")
                self._embedding_model = False
        return self._embedding_model if self._embedding_model is not False else None

    def _float32_to_int8(self, vec):
        scaled = np.clip(vec * 127.0, -128.0, 127.0)
        return np.round(scaled).astype(np.int8)

    def _compute_embedding(self, text):
        model = self._get_embedding_model()
        if model is None or not text or not text.strip():
            return None
        try:
            embeddings = list(model.embed([text.strip()]))
            if embeddings:
                return self._float32_to_int8(np.array(embeddings[0], dtype=np.float32))
        except Exception as e:
            print(f"Embedding failed: {e}")
        return None

    def add_translation(self, source, target, source_lang="", target_lang=""):
        if not source or not source.strip():
            return None
        if not target or not target.strip():
            return None
        source = source.strip()
        target = target.strip()
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
            """, (source, target, source_lang.strip(), target_lang.strip()))
            conn.commit()
            self._match_cache.clear()
            return cursor.lastrowid
        except Exception as e:
            print(f"Error adding to TM: {e}")
            return None
        finally:
            conn.close()

    def _add_embedding_for_row(self, source, row_id):
        emb = self._compute_embedding(source)
        if emb is None:
            return
        conn = sqlite3.connect(self.db_path)
        _load_vec_extension(conn)
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM vec_embeddings WHERE rowid = ?", [row_id])
            cursor.execute(
                "INSERT INTO vec_embeddings(rowid, embedding) VALUES (?, vec_int8(?))",
                [row_id, emb.tobytes()]
            )
            conn.commit()
        except Exception as e:
            print(f"Error storing embedding: {e}")
        finally:
            conn.close()

    def clear(self):
        conn = sqlite3.connect(self.db_path)
        _load_vec_extension(conn)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM translation_memory")
        conn.commit()
        try:
            cursor.execute("DELETE FROM vec_embeddings")
            conn.commit()
        except Exception:
            pass
        conn.close()

    def get_fuzzy_matches(self, query_source, min_score=50.0, limit=5, source_lang=None, target_lang=None):
        if not query_source or not query_source.strip():
            return []

        query_source = query_source.strip()
        key = (query_source, min_score, limit, source_lang, target_lang)
        cached = self._match_cache.get(key)
        if cached is not None:
            return cached

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
        result = matches[:limit]
        self._match_cache[key] = result
        if len(self._match_cache) > self._cache_max:
            self._match_cache.pop(next(iter(self._match_cache)))
        return result

    def get_semantic_matches(self, query_source, limit=5, source_lang=None, target_lang=None):
        if not query_source or not query_source.strip():
            return []

        model = self._get_embedding_model()
        if model is None:
            return []

        query_source = query_source.strip()
        try:
            query_emb = list(model.embed([query_source]))[0]
            query_int8 = self._float32_to_int8(np.array(query_emb, dtype=np.float32))
        except Exception as e:
            print(f"Query embedding failed: {e}")
            return []

        conn = sqlite3.connect(self.db_path)
        _load_vec_extension(conn)
        cursor = conn.cursor()

        try:
            vec_rows = cursor.execute(
                """
                SELECT rowid, distance
                FROM vec_embeddings
                WHERE embedding MATCH vec_int8(?)
                  AND k = ?
                ORDER BY distance
                """,
                [query_int8.tobytes(), limit * 3]
            ).fetchall()
        except Exception as e:
            print(f"Semantic search failed: {e}")
            conn.close()
            return []

        q = query_source.lower()
        matches = []
        for row_id, distance in vec_rows:
            cursor.execute(
                "SELECT source, target, source_lang, target_lang FROM translation_memory WHERE id = ?",
                [row_id]
            )
            row = cursor.fetchone()
            if row is None:
                continue
            source, target, sl, tl = row
            if source_lang and sl and sl != source_lang:
                continue
            if target_lang and tl and tl != target_lang:
                continue
            if source.lower() == q:
                continue
            sim = max(0, (1.0 - distance) * 100)
            if sim > 0:
                matches.append({
                    "source": source,
                    "target": target,
                    "score": round(sim, 1),
                })

        conn.close()
        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches[:limit]
