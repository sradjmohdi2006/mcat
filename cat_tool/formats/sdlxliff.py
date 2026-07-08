import os
import xml.etree.ElementTree as ET
from cat_tool.formats.tag_utils import extract_all_tags, apply_tags


XLF_NS = "urn:oasis:names:tc:xliff:document:1.2"
SDL_NS = "http://sdl.com/FileTypes/SdlXliff/1.0"


class SdlxliffHandler:
    def load(self, file_path):
        segments = []
        tree = ET.parse(file_path)
        root = tree.getroot()

        for idx, unit_el in enumerate(root.findall(f".//{{{XLF_NS}}}trans-unit")):
            if unit_el.get("translate") == "no":
                continue

            src_text = ""
            tgt_text = ""

            seg_source_el = unit_el.find(f"{{{XLF_NS}}}seg-source")
            target_el = unit_el.find(f"{{{XLF_NS}}}target")
            source_el = unit_el.find(f"{{{XLF_NS}}}source")

            if seg_source_el is not None:
                src_parts = []
                for mrk in seg_source_el.findall(f"{{{XLF_NS}}}mrk"):
                    txt = "".join(mrk.itertext()) if mrk.text else (mrk.text or "")
                    src_parts.append(txt.strip())
                src_text = " ".join(p for p in src_parts if p)
            elif source_el is not None:
                src_text = "".join(source_el.itertext()).strip()

            if target_el is not None:
                mrks = target_el.findall(f"{{{XLF_NS}}}mrk")
                if mrks:
                    tgt_parts = []
                    for mrk in mrks:
                        txt = "".join(mrk.itertext()) if mrk.text else (mrk.text or "")
                        tgt_parts.append(txt.strip())
                    tgt_text = " ".join(p for p in tgt_parts if p)
                else:
                    tgt_text = "".join(target_el.itertext()).strip()

            if not src_text:
                continue

            src_tags = extract_all_tags(src_text)
            tgt_tags = extract_all_tags(tgt_text)
            all_tags = list(src_tags)
            for t in tgt_tags:
                if t not in all_tags:
                    all_tags.append(t)
            source_clean = apply_tags(src_text, all_tags)
            target_clean = apply_tags(tgt_text, all_tags)

            segments.append({
                "index": idx, "source": src_text, "target": tgt_text,
                "source_clean": source_clean, "target_clean": target_clean,
                "all_tags": all_tags, "notes": "",
                "fuzzy": False, "translated": bool(tgt_text.strip()),
                "locations": "", "store": None, "unit": None,
            })

        return segments

    def save(self, segments, output_path, src_lang="en", tgt_lang="es"):
        ET.register_namespace("", XLF_NS)
        ET.register_namespace("sdl", SDL_NS)
        ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")

        root = ET.Element(f"{{{XLF_NS}}}xliff", {
            "version": "1.2",
            f"{{{SDL_NS}}}version": "1.0",
        })

        file_el = ET.SubElement(root, f"{{{XLF_NS}}}file", {
            "original": os.path.basename(output_path),
            "datatype": "x-sdlfilterframework2",
            "source-language": src_lang,
            "target-language": tgt_lang,
        })

        header = ET.SubElement(file_el, f"{{{XLF_NS}}}header")
        body = ET.SubElement(file_el, f"{{{XLF_NS}}}body")

        for idx, seg in enumerate(segments):
            unit_el = ET.SubElement(body, f"{{{XLF_NS}}}trans-unit", {"id": str(idx + 1)})

            src_el = ET.SubElement(unit_el, f"{{{XLF_NS}}}source")
            src_el.text = seg["source"]

            seg_src = ET.SubElement(unit_el, f"{{{XLF_NS}}}seg-source")
            mrk_src = ET.SubElement(seg_src, f"{{{XLF_NS}}}mrk", {"mtype": "seg", "mid": "1"})
            mrk_src.text = seg["source"]

            tgt_el = ET.SubElement(unit_el, f"{{{XLF_NS}}}target")
            if seg["target"]:
                mrk_tgt = ET.SubElement(tgt_el, f"{{{XLF_NS}}}mrk", {"mtype": "seg", "mid": "1"})
                mrk_tgt.text = seg["target"]

            seg_defs = ET.SubElement(unit_el, f"{{{SDL_NS}}}seg-defs")
            seg_def = ET.SubElement(seg_defs, f"{{{SDL_NS}}}seg", {
                "id": "1",
                "conf": "Translated" if seg["target"] else "Draft",
            })

        tree = ET.ElementTree(root)
        tree.write(output_path, encoding="utf-8", xml_declaration=True)
