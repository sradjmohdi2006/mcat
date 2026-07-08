from translate.storage.po import pofile
from cat_tool.formats.tag_utils import extract_all_tags, apply_tags


def make_segments_from_texts(texts, notes_prefix="", source_locations=None):
    store = pofile()
    segments = []
    for idx, text in enumerate(texts):
        if not text.strip():
            continue
        all_tags = extract_all_tags(text)
        source_clean = apply_tags(text, all_tags)
        unit = store.addsourceunit(text)
        unit.source = text
        unit.target = ""
        loc = source_locations[idx] if source_locations and idx < len(source_locations) else {}
        segments.append({
            "index": idx, "source": text, "target": "",
            "source_clean": source_clean, "target_clean": "",
            "all_tags": all_tags,
            "notes": f"{notes_prefix}{idx + 1}" if notes_prefix else "",
            "fuzzy": False, "translated": False,
            "locations": f"{notes_prefix.strip().lower()}:{idx + 1}" if notes_prefix else "",
            "source_location": loc,
            "store": store, "unit": unit,
        })
    return segments
