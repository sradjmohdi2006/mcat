"""
Unified Search Fetcher for mcat.

Provides searching across four sources:
1. In-memory segments (currently loaded file)
2. TM Sources (translation memory source segments)
3. TM Targets (translation memory target segments)
4. Glossary (terminology database)

Supports both fuzzy (rapidfuzz) and semantic (vector embeddings) search modes.
"""
import sqlite3
import os
import sys
from rapidfuzz import fuzz
from typing import List, Dict, Any, Optional, Tuple

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

# Handle sqlite-vec extension loading
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


class SearchFetcher:
    """Unified search across in-memory, TM sources, TM targets, and glossary."""
    
    def __init__(self, tm_db_path: str = "translation_memory.db", glossary_db_path: str = "glossary.db"):
        self.tm_db_path = tm_db_path
        self.glossary_db_path = glossary_db_path
        self._embedding_model = None
        self._model_load_failed = False
    
    def _get_embedding_model(self):
        """Lazy-load the embedding model."""
        if self._embedding_model is None and not self._model_load_failed:
            try:
                from fastembed import TextEmbedding
                self._embedding_model = TextEmbedding("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
            except Exception as e:
                print(f"Failed to load embedding model: {e}")
                self._model_load_failed = True
        return self._embedding_model if not self._model_load_failed else None
    
    def _float32_to_int8(self, vec):
        """Convert float32 embedding to int8 for sqlite-vec."""
        if not NUMPY_AVAILABLE:
            return None
        scaled = np.clip(vec * 127.0, -128.0, 127.0)
        return np.round(scaled).astype(np.int8)
    
    def _compute_query_embedding(self, text: str):
        """Compute embedding for query text."""
        model = self._get_embedding_model()
        if model is None or not text or not text.strip():
            return None
        try:
            embeddings = list(model.embed([text.strip()]))
            if embeddings:
                return self._float32_to_int8(np.array(embeddings[0], dtype=np.float32))
        except Exception as e:
            print(f"Query embedding failed: {e}")
        return None

    # ============================================================
    # 1. IN-MEMORY SEARCH (currently loaded file segments)
    # ============================================================
    
    def search_in_memory(
        self,
        segments: List[Dict[str, Any]],
        query: str,
        search_in: str = "both",  # "source", "target", "both"
        min_score: float = 30.0,
        limit: int = 50,
        use_fuzzy: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Search in currently loaded segments (in-memory).
        
        Args:
            segments: List of segment dicts with 'source', 'target', etc.
            query: Search query string
            search_in: "source", "target", or "both"
            min_score: Minimum fuzzy score (0-100)
            limit: Maximum results
            use_fuzzy: Use fuzzy matching (rapidfuzz) vs simple substring
        
        Returns:
            List of match dicts with keys: source, target, score, index, match_type, context
        """
        if not query or not query.strip() or not segments:
            return []
        
        query = query.strip().lower()
        matches = []
        
        for idx, seg in enumerate(segments):
            source = seg.get("source", "") or ""
            target = seg.get("target", "") or ""
            source_lower = source.lower()
            target_lower = target.lower()
            
            best_score = 0.0
            match_field = ""
            match_text = ""
            
            if search_in in ("source", "both"):
                if use_fuzzy:
                    score = max(
                        fuzz.ratio(query, source_lower),
                        fuzz.token_sort_ratio(query, source_lower),
                        fuzz.partial_ratio(query, source_lower)
                    )
                else:
                    score = 100.0 if query in source_lower else 0.0
                
                if score >= min_score and score > best_score:
                    best_score = score
                    match_field = "source"
                    match_text = source
            
            if search_in in ("target", "both"):
                if use_fuzzy:
                    score = max(
                        fuzz.ratio(query, target_lower),
                        fuzz.token_sort_ratio(query, target_lower),
                        fuzz.partial_ratio(query, target_lower)
                    )
                else:
                    score = 100.0 if query in target_lower else 0.0
                
                if score >= min_score and score > best_score:
                    best_score = score
                    match_field = "target"
                    match_text = target
            
            if best_score >= min_score:
                matches.append({
                    "source": source,
                    "target": target,
                    "score": round(best_score, 1),
                    "index": idx,
                    "match_field": match_field,
                    "match_text": match_text,
                    "source_lang": seg.get("source_lang", ""),
                    "target_lang": seg.get("target_lang", ""),
                    "fuzzy": seg.get("fuzzy", False),
                    "context": "in_memory"
                })
        
        # Sort by score descending
        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches[:limit]

    # ============================================================
    # 2. TM SOURCES SEARCH (fuzzy + semantic)
    # ============================================================
    
    def search_tm_sources(
        self,
        query: str,
        min_score: float = 30.0,
        limit: int = 50,
        source_lang: Optional[str] = None,
        target_lang: Optional[str] = None,
        use_fuzzy: bool = True,
        use_semantic: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Search TM database source segments.
        
        Args:
            query: Search query
            min_score: Minimum score threshold
            limit: Max results
            source_lang: Filter by source language
            target_lang: Filter by target language
            use_fuzzy: Include fuzzy matches
            use_semantic: Include semantic (vector) matches
        
        Returns:
            List of match dicts
        """
        if not query or not query.strip():
            return []
        
        query = query.strip()
        all_matches = {}  # Use dict to deduplicate by source text
        
        # ---- Fuzzy search ----
        if use_fuzzy:
            fuzzy_matches = self._tm_fuzzy_search(
                query, min_score, limit * 2, source_lang, target_lang, search_field="source"
            )
            for m in fuzzy_matches:
                key = m["source"]
                if key not in all_matches or m["score"] > all_matches[key]["score"]:
                    m["match_type"] = "fuzzy"
                    m["context"] = "tm_source"
                    all_matches[key] = m
        
        # ---- Semantic search ----
        if use_semantic:
            semantic_matches = self._tm_semantic_search(
                query, limit * 2, source_lang, target_lang, search_field="source"
            )
            for m in semantic_matches:
                key = m["source"]
                if key not in all_matches or m["score"] > all_matches[key]["score"]:
                    m["match_type"] = "semantic"
                    m["context"] = "tm_source"
                    all_matches[key] = m
        
        # Sort and limit
        results = list(all_matches.values())
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]
    
    def _tm_fuzzy_search(
        self,
        query: str,
        min_score: float,
        limit: int,
        source_lang: Optional[str],
        target_lang: Optional[str],
        search_field: str = "source"
    ) -> List[Dict[str, Any]]:
        """Internal fuzzy search in TM database."""
        conn = sqlite3.connect(self.tm_db_path)
        cursor = conn.cursor()
        
        # Build query with optional language filters
        sql = f"SELECT source, target, source_lang, target_lang FROM translation_memory"
        params = []
        conditions = []
        
        if source_lang:
            conditions.append("source_lang = ?")
            params.append(source_lang)
        if target_lang:
            conditions.append("target_lang = ?")
            params.append(target_lang)
        
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        
        q = query.lower()
        matches = []
        for source, target, sl, tl in rows:
            field_text = source if search_field == "source" else target
            field_lower = field_text.lower()
            
            ratio = fuzz.ratio(q, field_lower)
            sort_ratio = fuzz.token_sort_ratio(q, field_lower)
            partial_ratio = fuzz.partial_ratio(q, field_lower)
            score = max(ratio, sort_ratio, partial_ratio)
            
            if score >= min_score:
                matches.append({
                    "source": source,
                    "target": target,
                    "score": round(score, 1),
                    "source_lang": sl or "",
                    "target_lang": tl or "",
                })
        
        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches[:limit]
    
    def _tm_semantic_search(
        self,
        query: str,
        limit: int,
        source_lang: Optional[str],
        target_lang: Optional[str],
        search_field: str = "source"
    ) -> List[Dict[str, Any]]:
        """Internal semantic (vector) search in TM database."""
        query_emb = self._compute_query_embedding(query)
        if query_emb is None:
            return []
        
        conn = sqlite3.connect(self.tm_db_path)
        _load_vec_extension(conn)
        cursor = conn.cursor()
        
        try:
            # Get candidate rowids from vector search
            vec_rows = cursor.execute(
                """
                SELECT rowid, distance
                FROM vec_embeddings
                WHERE embedding MATCH vec_int8(?)
                  AND k = ?
                ORDER BY distance
                """,
                [query_emb.tobytes(), limit * 3]
            ).fetchall()
        except Exception as e:
            print(f"Semantic search failed: {e}")
            conn.close()
            return []
        
        matches = []
        q = query.lower()
        
        for row_id, distance in vec_rows:
            cursor.execute(
                "SELECT source, target, source_lang, target_lang FROM translation_memory WHERE id = ?",
                [row_id]
            )
            row = cursor.fetchone()
            if row is None:
                continue
            
            source, target, sl, tl = row
            
            # Language filtering
            if source_lang and sl and sl != source_lang:
                continue
            if target_lang and tl and tl != target_lang:
                continue
            
            # Skip exact matches (already handled by fuzzy)
            field_text = source if search_field == "source" else target
            if field_text.lower() == q:
                continue
            
            sim = max(0, (1.0 - distance) * 100)
            if sim > 0:
                matches.append({
                    "source": source,
                    "target": target,
                    "score": round(sim, 1),
                    "source_lang": sl or "",
                    "target_lang": tl or "",
                })
        
        conn.close()
        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches[:limit]

    # ============================================================
    # 3. TM TARGETS SEARCH (fuzzy + semantic)
    # ============================================================
    
    def search_tm_targets(
        self,
        query: str,
        min_score: float = 30.0,
        limit: int = 50,
        source_lang: Optional[str] = None,
        target_lang: Optional[str] = None,
        use_fuzzy: bool = True,
        use_semantic: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Search TM database target (translated) segments.
        
        Same parameters as search_tm_sources but searches the target field.
        """
        if not query or not query.strip():
            return []
        
        query = query.strip()
        all_matches = {}
        
        # ---- Fuzzy search on targets ----
        if use_fuzzy:
            fuzzy_matches = self._tm_fuzzy_search(
                query, min_score, limit * 2, source_lang, target_lang, search_field="target"
            )
            for m in fuzzy_matches:
                key = m["target"]  # Dedupe by target text
                if key not in all_matches or m["score"] > all_matches[key]["score"]:
                    m["match_type"] = "fuzzy"
                    m["context"] = "tm_target"
                    all_matches[key] = m
        
        # ---- Semantic search on targets ----
        if use_semantic:
            semantic_matches = self._tm_semantic_search(
                query, limit * 2, source_lang, target_lang, search_field="target"
            )
            for m in semantic_matches:
                key = m["target"]
                if key not in all_matches or m["score"] > all_matches[key]["score"]:
                    m["match_type"] = "semantic"
                    m["context"] = "tm_target"
                    all_matches[key] = m
        
        results = list(all_matches.values())
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    # ============================================================
    # 4. GLOSSARY SEARCH (fuzzy)
    # ============================================================
    
    def search_glossary(
        self,
        query: str,
        min_score: float = 30.0,
        limit: int = 50,
        source_lang: Optional[str] = None,
        target_lang: Optional[str] = None,
        search_in: str = "both"  # "source", "target", "description", "both", "all"
    ) -> List[Dict[str, Any]]:
        """
        Search glossary database for terms.
        
        Args:
            query: Search query
            min_score: Minimum fuzzy score threshold
            limit: Max results
            source_lang: Filter by source language
            target_lang: Filter by target language
            search_in: "source", "target", "description", "both" (source+target), "all" (all three)
        
        Returns:
            List of match dicts with keys: source_term, target_translation, description, score, etc.
        """
        if not query or not query.strip():
            return []
        
        query = query.strip().lower()
        
        conn = sqlite3.connect(self.glossary_db_path)
        cursor = conn.cursor()
        
        # Build query with optional language filters
        sql = "SELECT source_term, target_translation, description, source_lang, target_lang FROM glossary"
        params = []
        conditions = []
        
        if source_lang:
            conditions.append("source_lang = ?")
            params.append(source_lang)
        if target_lang:
            conditions.append("target_lang = ?")
            params.append(target_lang)
        
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        
        matches = []
        for source_term, target_translation, description, sl, tl in rows:
            source_term = source_term or ""
            target_translation = target_translation or ""
            description = description or ""
            
            source_lower = source_term.lower()
            target_lower = target_translation.lower()
            desc_lower = description.lower()
            
            best_score = 0.0
            match_field = ""
            match_text = ""
            
            # Search in source term
            if search_in in ("source", "both", "all"):
                score = max(
                    fuzz.ratio(query, source_lower),
                    fuzz.token_sort_ratio(query, source_lower),
                    fuzz.partial_ratio(query, source_lower)
                )
                if score >= min_score and score > best_score:
                    best_score = score
                    match_field = "source_term"
                    match_text = source_term
            
            # Search in target translation
            if search_in in ("target", "both", "all"):
                score = max(
                    fuzz.ratio(query, target_lower),
                    fuzz.token_sort_ratio(query, target_lower),
                    fuzz.partial_ratio(query, target_lower)
                )
                if score >= min_score and score > best_score:
                    best_score = score
                    match_field = "target_translation"
                    match_text = target_translation
            
            # Search in description
            if search_in in ("description", "all"):
                score = max(
                    fuzz.ratio(query, desc_lower),
                    fuzz.token_sort_ratio(query, desc_lower),
                    fuzz.partial_ratio(query, desc_lower)
                )
                if score >= min_score and score > best_score:
                    best_score = score
                    match_field = "description"
                    match_text = description
            
            if best_score >= min_score:
                matches.append({
                    "source": source_term,
                    "target": target_translation,
                    "description": description,
                    "score": round(best_score, 1),
                    "source_lang": sl or "",
                    "target_lang": tl or "",
                    "match_field": match_field,
                    "match_text": match_text,
                    "context": "glossary",
                    "match_type": "fuzzy"
                })
        
        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches[:limit]

    # ============================================================
    # UNIFIED SEARCH (combines all four sources)
    # ============================================================
    
    def search_all(
        self,
        query: str,
        in_memory_segments: Optional[List[Dict[str, Any]]] = None,
        min_score: float = 30.0,
        limit: int = 50,
        source_lang: Optional[str] = None,
        target_lang: Optional[str] = None,
        search_in_memory: bool = True,
        search_tm_sources: bool = True,
        search_tm_targets: bool = True,
        search_glossary: bool = True,
        in_memory_search_in: str = "both",  # "source", "target", "both"
        glossary_search_in: str = "both",   # "source", "target", "description", "both", "all"
        use_fuzzy: bool = True,
        use_semantic: bool = False
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Unified search across all sources.
        
        Returns:
            Dict with keys: "in_memory", "tm_sources", "tm_targets", "glossary", "all"
            Each value is a list of match dicts.
            The "all" key contains combined results sorted by score.
        """
        results = {
            "in_memory": [],
            "tm_sources": [],
            "tm_targets": [],
            "glossary": [],
            "all": []
        }
        
        # Search in-memory segments
        if search_in_memory and in_memory_segments:
            results["in_memory"] = self.search_in_memory(
                in_memory_segments, query,
                search_in=in_memory_search_in,
                min_score=min_score,
                limit=limit,
                use_fuzzy=use_fuzzy
            )
        
        # Search TM sources
        if search_tm_sources:
            results["tm_sources"] = self.search_tm_sources(
                query, min_score, limit,
                source_lang, target_lang,
                use_fuzzy, use_semantic
            )
        
        # Search TM targets
        if search_tm_targets:
            results["tm_targets"] = self.search_tm_targets(
                query, min_score, limit,
                source_lang, target_lang,
                use_fuzzy, use_semantic
            )
        
        # Search glossary
        if search_glossary:
            results["glossary"] = self.search_glossary(
                query, min_score, limit,
                source_lang, target_lang,
                search_in=glossary_search_in
            )
        
        # Combine all results with source labels
        all_matches = []
        for match in results["in_memory"]:
            m = match.copy()
            m["search_source"] = "in_memory"
            all_matches.append(m)
        for match in results["tm_sources"]:
            m = match.copy()
            m["search_source"] = "tm_source"
            all_matches.append(m)
        for match in results["tm_targets"]:
            m = match.copy()
            m["search_source"] = "tm_target"
            all_matches.append(m)
        for match in results["glossary"]:
            m = match.copy()
            m["search_source"] = "glossary"
            all_matches.append(m)
        
        # Sort combined results by score
        all_matches.sort(key=lambda x: x["score"], reverse=True)
        results["all"] = all_matches[:limit]
        
        return results


# Convenience function for quick searches
def quick_search(
    query: str,
    tm_db_path: str = "translation_memory.db",
    glossary_db_path: str = "glossary.db",
    in_memory_segments: Optional[List[Dict[str, Any]]] = None,
    **kwargs
) -> Dict[str, List[Dict[str, Any]]]:
    """Quick search with default settings."""
    fetcher = SearchFetcher(tm_db_path, glossary_db_path)
    return fetcher.search_all(query, in_memory_segments, **kwargs)