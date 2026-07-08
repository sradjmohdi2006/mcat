from cat_tool.formats._text_base import make_segments_from_texts


class TextHandler:
    def load(self, file_path):
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = [l.strip() for l in f.readlines()]
        locations = [{"line": i} for i in range(len(lines))]
        return make_segments_from_texts(lines, "Line ", source_locations=locations)

    def render(self, original_path, segments, output_path):
        translated = []
        for seg in segments:
            translated.append(seg.get("target", "").strip() or seg["source"])
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(translated))
