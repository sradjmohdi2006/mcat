import os
import shutil
import sqlite3
from datetime import datetime, timezone
from cat_tool.mcat_format_manager import MCatProjectManager, SCHEMA_SQL
from cat_tool.formats.tag_utils import extract_all_tags


def _app_status_from_mcat(status_text, has_target):
    if status_text == "Confirmed":
        return {"translated": True, "fuzzy": False}
    if status_text == "Draft":
        return {"translated": bool(has_target), "fuzzy": True}
    return {"translated": False, "fuzzy": False}


def _mcat_status_from_app(fuzzy, translated):
    if fuzzy:
        return "Draft"
    if translated:
        return "Confirmed"
    return "Untranslated"


class McatDbHandler:
    def load(self, file_path):
        rows = MCatProjectManager.get_editor_stream(file_path)
        segments = []
        for r in rows:
            source = r["source_text"]
            target = r["target_text"]
            src_tags = extract_all_tags(source)
            tgt_tags = extract_all_tags(target)
            all_tags = list(src_tags)
            for t in tgt_tags:
                if t not in all_tags:
                    all_tags.append(t)
            source_clean = source
            target_clean = target
            if all_tags:
                from cat_tool.formats.tag_utils import apply_tags
                source_clean = apply_tags(source, all_tags)
                target_clean = apply_tags(target, all_tags)

            status = _app_status_from_mcat(r["status"], target)
            segments.append({
                "index": r["id"],
                "source": source,
                "target": target,
                "source_clean": source_clean,
                "target_clean": target_clean,
                "all_tags": all_tags,
                "notes": "",
                "fuzzy": status["fuzzy"],
                "translated": status["translated"],
                "locations": r["file_id"],
                "source_location": {"unit_id": r["id"]},
                "store": None,
                "unit": None,
            })
        return segments

    def save(self, segments, target_path):
        if not segments:
            raise ValueError("No segments to save.")

        if not os.path.exists(target_path):
            tmp_conn = sqlite3.connect(target_path)
            try:
                tmp_conn.executescript(SCHEMA_SQL)
                now = datetime.now(timezone.utc).isoformat()
                tmp_conn.execute(
                    "INSERT OR REPLACE INTO project_meta (key, value) VALUES (?, ?)",
                    ("created_at", now),
                )
                tmp_conn.commit()
            except BaseException:
                tmp_conn.rollback()
                raise
            finally:
                tmp_conn.close()
            conn = None
        else:
            conn = None

        conn = MCatProjectManager._connect(target_path)
        try:
            conn.execute("DELETE FROM format_tags")
            conn.execute("DELETE FROM translation_units")
            for seg in segments:
                status = _mcat_status_from_app(seg.get("fuzzy", False),
                                               bool(seg.get("target", "")))
                cursor = conn.execute(
                    """INSERT INTO translation_units
                       (file_id, source_text, target_text, status, match_score)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        seg.get("locations", ""),
                        seg.get("source", ""),
                        seg.get("target", ""),
                        status,
                        seg.get("match_score", 0),
                    ),
                )
                unit_id = cursor.lastrowid
                tags = seg.get("all_tags", [])
                if tags:
                    tag_rows = [
                        (unit_id, f"{{{i}}}", tag if isinstance(tag, str) else tag.get("raw", str(tag)))
                        for i, tag in enumerate(tags)
                    ]
                    conn.executemany(
                        """INSERT INTO format_tags (unit_id, tag_index, raw_xml_tag)
                           VALUES (?, ?, ?)""",
                        tag_rows,
                    )
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def render(self, original_path, segments, output_path):
        shutil.copy2(original_path, output_path)
