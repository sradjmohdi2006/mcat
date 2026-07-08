from cat_tool.formats._text_base import make_segments_from_texts
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter
import io


class PdfHandler:
    def load(self, file_path):
        import pdfplumber
        texts = []
        locations = []
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                chars = page.chars
                if not chars:
                    continue
                chars.sort(key=lambda c: (c["top"], c["x0"]))
                lines = []
                current_line = []
                current_top = chars[0]["top"]
                for c in chars:
                    if abs(c["top"] - current_top) > max(c.get("height", 8) * 0.5, 3):
                        if current_line:
                            lines.append("".join(current_line))
                            current_line = []
                        current_top = c["top"]
                    current_line.append(c.get("text", ""))
                if current_line:
                    lines.append("".join(current_line))
                block_text = " ".join(line.strip() for line in lines if line.strip())
                if block_text.strip():
                    texts.append(block_text.strip())
                    locations.append({"page": page_num, "block": len(locations)})
        return make_segments_from_texts(texts, "Page ", source_locations=locations)

    def render(self, original_path, segments, output_path):
        reader = PdfReader(original_path)
        writer = PdfWriter()

        page_data = {}
        for seg in segments:
            loc = seg.get("source_location", {})
            if not loc:
                continue
            page_num = loc.get("page", 0)
            target = seg.get("target", "").strip()
            source = seg.get("source", "").strip()
            page_data.setdefault(page_num, []).append({
                "source": source,
                "target": target or source,
                "index": seg.get("index", 0),
            })

        num_pages = len(reader.pages)
        for page_num in range(num_pages):
            packet = io.BytesIO()
            w, h = letter
            c = canvas.Canvas(packet, pagesize=letter)
            c.setFont("Helvetica", 10)
            y = h - 50
            segs = page_data.get(page_num, [])
            if segs:
                for s in segs:
                    c.drawString(50, y, f"{s['target']}")
                    y -= 16
            else:
                c.drawString(50, y, "(no translated content)")
            c.save()
            packet.seek(0)
            overlay = PdfReader(packet)
            page = reader.pages[page_num]
            page.merge_page(overlay.pages[0])
            writer.add_page(page)

        with open(output_path, "wb") as f:
            writer.write(f)
