from cat_tool.formats.tag_utils import extract_all_tags, apply_tags


class FactoryHandler:
    def load(self, file_path):
        from translate.storage.factory import getclass
        store_class = getclass(file_path)
        if not store_class:
            raise ValueError(f"Unsupported translation format: {file_path}")
        store = store_class.parsefile(file_path)
        segments = []
        for idx, unit in enumerate(store.units):
            if unit.isheader():
                continue
            locations = unit.getlocations()
            loc_str = ", ".join(locations) if locations else ""
            source_text = str(unit.source) if unit.source else ""
            target_text = str(unit.target) if unit.target else ""

            src_tags = extract_all_tags(source_text)
            tgt_tags = extract_all_tags(target_text)
            all_tags = list(src_tags)
            for t in tgt_tags:
                if t not in all_tags:
                    all_tags.append(t)
            source_clean = apply_tags(source_text, all_tags)
            target_clean = apply_tags(target_text, all_tags)

            segments.append({
                "index": idx, "source": source_text, "target": target_text,
                "source_clean": source_clean, "target_clean": target_clean,
                "all_tags": all_tags,
                "notes": unit.getnotes() or "",
                "fuzzy": unit.isfuzzy(), "translated": unit.istranslated(),
                "locations": loc_str,
                "source_location": {"unit_index": idx},
                "store": store, "unit": unit,
            })
        return segments

    def save(self, segments, target_path):
        if not segments:
            raise ValueError("No segments to save.")
        store = segments[0].get("store")
        if store is None:
            raise ValueError("No store object available; cannot save factory format.")
        for seg in segments:
            unit = seg["unit"]
            unit.target = seg["target"]
            if hasattr(unit, "markfuzzy"):
                unit.markfuzzy(seg["fuzzy"])
        store.savefile(target_path)

    def render(self, original_path, segments, output_path):
        self.save(segments, output_path)
