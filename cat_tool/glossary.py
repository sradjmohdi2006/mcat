import sqlite3
import os
import re
import xml.etree.ElementTree as ET

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
                description TEXT,
                source_lang TEXT DEFAULT '',
                target_lang TEXT DEFAULT ''
            )
        """)
        for col in ("source_lang", "target_lang"):
            try:
                cursor.execute(f"ALTER TABLE glossary ADD COLUMN {col} TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS collections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                description TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS collection_terms (
                collection_id INTEGER,
                term_source TEXT,
                PRIMARY KEY (collection_id, term_source),
                FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE
            )
        """)
        conn.commit()
        conn.close()

    def add_term(self, source, target, description="", source_lang="", target_lang=""):
        if not source or not target:
            return
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO glossary (source_term, target_translation, description, source_lang, target_lang)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source_term) DO UPDATE SET 
                    target_translation = excluded.target_translation,
                    description = excluded.description,
                    source_lang = excluded.source_lang,
                    target_lang = excluded.target_lang
            """, (source.strip(), target.strip(), description.strip(), source_lang.strip(), target_lang.strip()))
            conn.commit()
        except Exception as e:
            print(f"Error adding to Glossary: {e}")
        finally:
            conn.close()

    def remove_term(self, source):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM glossary WHERE source_term = ?", (source.strip(),))
        cursor.execute("DELETE FROM collection_terms WHERE term_source = ?", (source.strip(),))
        conn.commit()
        conn.close()

    def get_all_terms(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT source_term, target_translation, description, source_lang, target_lang FROM glossary")
        rows = cursor.fetchall()
        conn.close()
        return [{"source": r[0], "target": r[1], "description": r[2], "source_lang": r[3] or "", "target_lang": r[4] or ""} for r in rows]

    def _tokenize(self, text):
        return re.findall(r"\w+(?:'\w+)?", text.lower())

    def peek_tmx(self, file_path):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"TMX file not found: {file_path}")
        tree = ET.parse(file_path)
        root = tree.getroot()
        XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"

        header = root.find("header")
        srclang = header.get("srclang", "") if header is not None else ""

        body = root.find("body")
        if body is None:
            return {"source_lang": srclang, "target_lang": "", "count": 0}

        all_langs = set()
        seen_langs = set()
        tuv_count = 0
        for tu in body.findall("tu"):
            for tuv in tu.findall("tuv"):
                lang = tuv.get(XML_LANG) or tuv.get("lang") or ""
                seg = tuv.find("seg")
                seg_text = seg.text.strip() if seg is not None and seg.text else ""
                if seg_text:
                    seen_langs.add(lang)
                    tuv_count += 1

        total_pairs = tuv_count // 2
        target_langs = seen_langs - {srclang} if srclang else seen_langs
        target_lang = next(iter(target_langs)) if len(target_langs) == 1 else ", ".join(sorted(target_langs)) if target_langs else ""
        return {"source_lang": srclang, "target_lang": target_lang, "count": total_pairs}

    def import_tmx(self, file_path, source_lang=None):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"TMX file not found: {file_path}")
        tree = ET.parse(file_path)
        root = tree.getroot()
        XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"

        header = root.find("header")
        if header is not None and source_lang is None:
            source_lang = header.get("srclang", "en")
        if source_lang is None:
            source_lang = "en"

        body = root.find("body")
        if body is None:
            return 0

        count = 0
        for tu in body.findall("tu"):
            tuvs = tu.findall("tuv")
            source_text = None
            target_text = None
            target_lang = ""
            for tuv in tuvs:
                lang = tuv.get(XML_LANG) or tuv.get("lang") or ""
                seg = tuv.find("seg")
                seg_text = seg.text.strip() if seg is not None and seg.text else ""
                if not seg_text:
                    continue
                if lang == source_lang:
                    source_text = seg_text
                elif target_text is None:
                    target_text = seg_text
                    target_lang = lang
            if source_text and target_text:
                self.add_term(source_text, target_text,
                              f"Imported from TMX: {os.path.basename(file_path)}",
                              source_lang=source_lang, target_lang=target_lang)
                count += 1
        return count

    def export_tmx(self, file_path, source_lang=None, target_lang=None):
        terms = self.get_all_terms()
        if not terms:
            return 0

        if source_lang is None:
            source_lang = terms[0].get("source_lang") or "en"
        if target_lang is None:
            target_lang = terms[0].get("target_lang") or ""

        XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"

        root = ET.Element("tmx", version="1.4")
        header = ET.SubElement(root, "header")
        header.set("srclang", source_lang)
        header.set("datatype", "plaintext")
        body = ET.SubElement(root, "body")

        for t in terms:
            tu = ET.SubElement(body, "tu")
            note = ET.SubElement(tu, "note")
            note.text = t.get("description", "")

            tuv_src = ET.SubElement(tu, "tuv")
            tuv_src.set(XML_LANG, t.get("source_lang") or source_lang)
            seg_src = ET.SubElement(tuv_src, "seg")
            seg_src.text = t["source"]

            tl = t.get("target_lang") or target_lang
            tuv_tgt = ET.SubElement(tu, "tuv")
            tuv_tgt.set(XML_LANG, tl if tl else source_lang)
            seg_tgt = ET.SubElement(tuv_tgt, "seg")
            seg_tgt.text = t["target"]

        tree = ET.ElementTree(root)
        tree.write(file_path, encoding="utf-8", xml_declaration=True)
        return len(terms)

    def create_collection(self, name, description=""):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO collections (name, description) VALUES (?, ?)",
                           (name.strip(), description.strip()))
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None
        finally:
            conn.close()

    def delete_collection(self, collection_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM collection_terms WHERE collection_id = ?", (collection_id,))
        cursor.execute("DELETE FROM collections WHERE id = ?", (collection_id,))
        conn.commit()
        conn.close()

    def get_all_collections(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, description, created_at FROM collections ORDER BY name")
        rows = cursor.fetchall()
        conn.close()
        return [{"id": r[0], "name": r[1], "description": r[2], "created_at": r[3]} for r in rows]

    def add_term_to_collection(self, collection_id, term_source):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT OR IGNORE INTO collection_terms (collection_id, term_source) VALUES (?, ?)",
                           (collection_id, term_source.strip()))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def remove_term_from_collection(self, collection_id, term_source):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM collection_terms WHERE collection_id = ? AND term_source = ?",
                       (collection_id, term_source.strip()))
        conn.commit()
        conn.close()

    def get_collection_terms(self, collection_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT g.source_term, g.target_translation, g.description, g.source_lang, g.target_lang
            FROM glossary g
            JOIN collection_terms ct ON g.source_term = ct.term_source
            WHERE ct.collection_id = ?
            ORDER BY g.source_term
        """, (collection_id,))
        rows = cursor.fetchall()
        conn.close()
        return [{"source": r[0], "target": r[1], "description": r[2], "source_lang": r[3] or "", "target_lang": r[4] or ""} for r in rows]

    def export_collection_tmx(self, collection_id, file_path):
        terms = self.get_collection_terms(collection_id)
        if not terms:
            return 0
        source_lang = terms[0].get("source_lang") or "en"
        target_lang = terms[0].get("target_lang") or ""
        XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
        root = ET.Element("tmx", version="1.4")
        header = ET.SubElement(root, "header")
        header.set("srclang", source_lang)
        header.set("datatype", "plaintext")
        body = ET.SubElement(root, "body")
        for t in terms:
            tu = ET.SubElement(body, "tu")
            note = ET.SubElement(tu, "note")
            note.text = t.get("description", "")
            tuv_src = ET.SubElement(tu, "tuv")
            tuv_src.set(XML_LANG, t.get("source_lang") or source_lang)
            seg_src = ET.SubElement(tuv_src, "seg")
            seg_src.text = t["source"]
            tl = t.get("target_lang") or target_lang
            tuv_tgt = ET.SubElement(tu, "tuv")
            tuv_tgt.set(XML_LANG, tl if tl else source_lang)
            seg_tgt = ET.SubElement(tuv_tgt, "seg")
            seg_tgt.text = t["target"]
        tree = ET.ElementTree(root)
        tree.write(file_path, encoding="utf-8", xml_declaration=True)
        return len(terms)

    def import_collection_tmx(self, file_path, name=None):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"TMX file not found: {file_path}")
        tree = ET.parse(file_path)
        root = tree.getroot()
        XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
        header = root.find("header")
        srclang = header.get("srclang", "en") if header is not None else "en"
        body = root.find("body")
        if body is None:
            return 0, None
        coll_name = name or os.path.splitext(os.path.basename(file_path))[0]
        coll_id = self.create_collection(coll_name, f"Imported from {os.path.basename(file_path)}")
        if coll_id is None:
            return 0, None
        count = 0
        for tu in body.findall("tu"):
            tuvs = tu.findall("tuv")
            source_text = None
            target_text = None
            target_lang = ""
            for tuv in tuvs:
                lang = tuv.get(XML_LANG) or tuv.get("lang") or ""
                seg = tuv.find("seg")
                seg_text = seg.text.strip() if seg is not None and seg.text else ""
                if not seg_text:
                    continue
                if lang == srclang:
                    source_text = seg_text
                elif target_text is None:
                    target_text = seg_text
                    target_lang = lang
            if source_text and target_text:
                self.add_term(source_text, target_text,
                              f"Imported from TMX: {os.path.basename(file_path)}",
                              source_lang=srclang, target_lang=target_lang)
                self.add_term_to_collection(coll_id, source_text)
                count += 1
        return count, coll_id

    def check_segment(self, text, source_lang=None, target_lang=None):
        if not text or not text.strip():
            return []

        tokens = self._tokenize(text)
        terms = self.get_all_terms()
        matched_terms = []

        for term in terms:
            if source_lang and term.get("source_lang") and term["source_lang"] != source_lang:
                continue
            if target_lang and term.get("target_lang") and term["target_lang"] != target_lang:
                continue

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
