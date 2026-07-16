import os
import xml.etree.ElementTree as ET
from cat_tool.formats.tag_utils import extract_all_tags, apply_tags


class MqxliffHandler:
    def load(self, file_path):
        ns = "urn:oasis:names:tc:xliff:document:1.2"
        segments = []
        tree = ET.parse(file_path)
        root = tree.getroot()
        body = root.find(f".//{{{ns}}}body")
        if body is None:
            raise ValueError("Invalid MQXLIFF: no <body> element")
        for idx, unit_el in enumerate(body.findall(f"{{{ns}}}trans-unit")):
            src_el = unit_el.find(f"{{{ns}}}source")
            tgt_el = unit_el.find(f"{{{ns}}}target")
            src_text = "".join(src_el.itertext()).strip() if src_el is not None else ""
            tgt_text = "".join(tgt_el.itertext()).strip() if tgt_el is not None else ""

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
        ns = "urn:oasis:names:tc:xliff:document:1.2"
        xsi_ns = "http://www.w3.org/2001/XMLSchema-instance"
        ET.register_namespace("", ns)
        ET.register_namespace("xsi", xsi_ns)

        root = ET.Element(f"{{{ns}}}xliff", {"version": "1.2"})
        root.set(f"{{{xsi_ns}}}schemaLocation", f"{ns} xliff-core-1.2-transitional.xsd")

        file_el = ET.SubElement(root, f"{{{ns}}}file", {
            "original": os.path.basename(output_path),
            "source-language": src_lang,
            "target-language": tgt_lang,
            "datatype": "x-memoq",
        })

        body = ET.SubElement(file_el, f"{{{ns}}}body")
        for idx, seg in enumerate(segments):
            unit_el = ET.SubElement(body, f"{{{ns}}}trans-unit", {"id": str(idx + 1)})
            src_el = ET.SubElement(unit_el, f"{{{ns}}}source")
            src_el.text = seg["source"]
            tgt_el = ET.SubElement(unit_el, f"{{{ns}}}target")
            tgt_el.text = seg["target"] if seg["target"] else ""

        tree = ET.ElementTree(root)
        tree.write(output_path, encoding="utf-8", xml_declaration=True)
