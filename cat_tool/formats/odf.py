from cat_tool.formats._text_base import make_segments_from_texts


class OdfHandler:
    @staticmethod
    def _is_in_table_cell(element):
        from odf.table import TableCell
        parent = getattr(element, 'parent', None)
        while parent is not None:
            if isinstance(parent, TableCell):
                return True
            parent = getattr(parent, 'parent', None)
        return False

    def load(self, file_path):
        from odf.opendocument import load
        from odf.text import P, H
        from odf.table import Table, TableRow, TableCell
        from odf.element import Text as OdfText
        doc = load(file_path)
        texts = []
        locations = []
        para_counter = 0
        heading_counter = 0
        table_counter = 0

        for p in doc.getElementsByType(P):
            if self._is_in_table_cell(p):
                continue
            t = "".join(n.data for n in p.childNodes if n.nodeType == OdfText.TEXT_NODE).strip()
            if t:
                texts.append(t)
                locations.append({"type": "paragraph", "index": para_counter})
                para_counter += 1
        for h in doc.getElementsByType(H):
            t = "".join(n.data for n in h.childNodes if n.nodeType == OdfText.TEXT_NODE).strip()
            if t:
                texts.append(t)
                locations.append({"type": "heading", "index": heading_counter})
                heading_counter += 1
        for table in doc.getElementsByType(Table):
            for ri, row in enumerate(table.getElementsByType(TableRow)):
                for ci, cell in enumerate(row.getElementsByType(TableCell)):
                    t = "".join(n.data for n in cell.childNodes if n.nodeType == OdfText.TEXT_NODE).strip()
                    if t:
                        texts.append(t)
                        locations.append({"type": "table_cell", "table_index": table_counter, "row_index": ri, "col_index": ci})
            table_counter += 1

        return make_segments_from_texts(texts, "ODF ", source_locations=locations)

    def render(self, original_path, segments, output_path):
        from odf.opendocument import load
        from odf.text import P, H
        from odf.table import Table, TableRow, TableCell
        from odf.element import Text as OdfText
        from copy import deepcopy

        doc = load(original_path)
        seg_iter = iter(segments)

        for p in doc.getElementsByType(P):
            if self._is_in_table_cell(p):
                continue
            t = "".join(n.data for n in p.childNodes if n.nodeType == OdfText.TEXT_NODE).strip()
            if t:
                seg = next(seg_iter, None)
                if seg and seg.get("source_location", {}).get("type") == "paragraph":
                    target = seg.get("target", "").strip()
                    if target:
                        for child in list(p.childNodes):
                            if child.nodeType == OdfText.TEXT_NODE:
                                p.removeChild(child)
                        p.appendChild(p.ownerDocument.createTextNode(target))

        for h in doc.getElementsByType(H):
            t = "".join(n.data for n in h.childNodes if n.nodeType == OdfText.TEXT_NODE).strip()
            if t:
                seg = next(seg_iter, None)
                if seg and seg.get("source_location", {}).get("type") == "heading":
                    target = seg.get("target", "").strip()
                    if target:
                        for child in list(h.childNodes):
                            if child.nodeType == OdfText.TEXT_NODE:
                                h.removeChild(child)
                        h.appendChild(h.ownerDocument.createTextNode(target))

        for table in doc.getElementsByType(Table):
            for ri, row in enumerate(table.getElementsByType(TableRow)):
                for ci, cell in enumerate(row.getElementsByType(TableCell)):
                    t = "".join(n.data for n in cell.childNodes if n.nodeType == OdfText.TEXT_NODE).strip()
                    if t:
                        seg = next(seg_iter, None)
                        if seg and seg.get("source_location", {}).get("type") == "table_cell":
                            target = seg.get("target", "").strip()
                            if target:
                                for child in list(cell.childNodes):
                                    if child.nodeType == OdfText.TEXT_NODE:
                                        cell.removeChild(child)
                                cell.appendChild(cell.ownerDocument.createTextNode(target))

        doc.save(output_path)
