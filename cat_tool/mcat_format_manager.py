import sqlite3
import os
from datetime import datetime, timezone

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS project_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS translation_units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT NOT NULL,
    source_text TEXT NOT NULL,
    target_text TEXT DEFAULT '',
    status TEXT DEFAULT 'Untranslated',
    match_score INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS format_tags (
    unit_id INTEGER NOT NULL,
    tag_index TEXT NOT NULL,
    raw_xml_tag TEXT NOT NULL,
    PRIMARY KEY (unit_id, tag_index),
    FOREIGN KEY(unit_id) REFERENCES translation_units(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS project_glossary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_term TEXT NOT NULL,
    target_term TEXT NOT NULL,
    definition TEXT DEFAULT ''
);

PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;
"""

ENGINE_VERSION = "1.0.0"


class MCatProjectManager:

    @staticmethod
    def _connect(file_path):
        conn = sqlite3.connect(file_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @staticmethod
    def create_project_file(file_path, src_lang, tgt_lang):
        if not file_path.endswith(".mcat.db"):
            file_path += ".mcat.db"
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)

        conn = MCatProjectManager._connect(file_path)
        try:
            conn.executescript(SCHEMA_SQL)
            now = datetime.now(timezone.utc).isoformat()
            meta = [
                ("source_language", src_lang),
                ("target_language", tgt_lang),
                ("created_at", now),
                ("engine_version", ENGINE_VERSION),
            ]
            conn.executemany(
                "INSERT OR REPLACE INTO project_meta (key, value) VALUES (?, ?)", meta
            )
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def import_extracted_segments(file_path, segments_list):
        conn = MCatProjectManager._connect(file_path)
        try:
            with conn:
                for seg in segments_list:
                    cursor = conn.execute(
                        """INSERT INTO translation_units
                           (file_id, source_text, target_text, status, match_score)
                           VALUES (?, ?, ?, ?, ?)""",
                        (
                            seg.get("file_id", ""),
                            seg.get("source", ""),
                            seg.get("target", ""),
                            seg.get("status", "Untranslated"),
                            seg.get("match_score", 0),
                        ),
                    )
                    unit_id = cursor.lastrowid
                    tags = seg.get("all_tags", [])
                    if tags:
                        tag_rows = [
                            (unit_id, tag.get("index", f"{{{i}}}"), tag.get("raw", ""))
                            for i, tag in enumerate(tags)
                        ]
                        conn.executemany(
                            """INSERT OR IGNORE INTO format_tags
                               (unit_id, tag_index, raw_xml_tag) VALUES (?, ?, ?)""",
                            tag_rows,
                        )
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def get_editor_stream(file_path, filter_status=None):
        conn = MCatProjectManager._connect(file_path)
        try:
            if filter_status:
                rows = conn.execute(
                    "SELECT * FROM translation_units WHERE status = ? ORDER BY id",
                    (filter_status,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM translation_units ORDER BY id"
                ).fetchall()
            return [dict(r) for r in rows]
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def update_segment_translation(file_path, unit_id, target_text, status="Confirmed"):
        conn = MCatProjectManager._connect(file_path)
        try:
            conn.execute(
                """UPDATE translation_units
                   SET target_text = ?, status = ?
                   WHERE id = ?""",
                (target_text, status, unit_id),
            )
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()
