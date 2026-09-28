from cat_tool.formats._text_base import make_segments_from_texts
import fitz  # PyMuPDF


class PdfHandler:
    def load(self, file_path):
        texts = []
        locations = []
        doc = fitz.open(file_path)
        for page_num, page in enumerate(doc):
            blocks = page.get_text("dict")["blocks"]
            for block in blocks:
                if "lines" not in block:
                    continue
                block_text = ""
                for line in block["lines"]:
                    for span in line["spans"]:
                        block_text += span["text"]
                    block_text += "\n"
                block_text = block_text.strip()
                if block_text:
                    texts.append(block_text)
                    locations.append({"page": page_num, "block": len(locations)})
        doc.close()
        return make_segments_from_texts(texts, "Page ", source_locations=locations)

    def render(self, original_path, segments, output_path):
        """Render translated PDF preserving original layout using PyMuPDF."""
        doc = fitz.open(original_path)
        
        # Group segments by page
        page_data = {}
        for seg in segments:
            loc = seg.get("source_location", {})
            if not loc:
                continue
            page_num = loc.get("page", 0)
            target = seg.get("target", "").strip()
            source = seg.get("source", "").strip()
            if target:
                page_data.setdefault(page_num, []).append({
                    "source": source,
                    "target": target,
                    "index": seg.get("index", 0),
                })
        
        # For each page, replace text in-place
        for page_num, segs in page_data.items():
            if page_num >= len(doc):
                continue
            page = doc[page_num]
            
            # Get text instances with positions
            for seg in segs:
                source = seg["source"]
                target = seg["target"]
                
                # Search for source text on page
                text_instances = page.search_for(source)
                if not text_instances:
                    # Try fuzzy search - split into words
                    words = source.split()
                    if len(words) > 1:
                        for word in words:
                            instances = page.search_for(word)
                            if instances:
                                text_instances = instances
                                break
                
                if text_instances:
                    # Replace text in each instance (usually just one)
                    for inst in text_instances:
                        # Add redaction annotation to remove original
                        page.add_redact_annot(inst, fill=(1, 1, 1))
                    # Apply redactions
                    page.apply_redactions()
                    
                    # Insert translated text at same position
                    # Use first instance's position
                    inst = text_instances[0]
                    # Get font info from original text
                    text_dict = page.get_text("dict")
                    font_name = "helv"  # default
                    font_size = 10
                    color = (0, 0, 0)
                    
                    # Try to find font info from the text block
                    for block in text_dict["blocks"]:
                        if "lines" in block:
                            for line in block["lines"]:
                                for span in line["spans"]:
                                    span_rect = fitz.Rect(span["bbox"])
                                    if span_rect.intersects(inst):
                                        font_name = span["font"]
                                        font_size = span["size"]
                                        color = span["color"]
                                        break
                    
                    # Insert translated text
                    page.insert_text(
                        inst.tl,  # top-left point
                        target,
                        fontname=font_name,
                        fontsize=font_size,
                        color=color,
                    )
        
        doc.save(output_path)
        doc.close()

    def load_bookmarks(self, file_path):
        """Extract PDF outline/bookmark titles using PyMuPDF."""
        bookmarks = []
        try:
            doc = fitz.open(file_path)
            toc = doc.get_toc()
            for level, title, page in toc:
                bookmarks.append({
                    "title": title.strip(),
                    "level": level - 1,
                    "page": page - 1,  # 0-indexed
                })
            doc.close()
        except Exception:
            pass
        return bookmarks
