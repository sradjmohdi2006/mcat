from cat_tool.formats._text_base import make_segments_from_texts


class XlsHandler:
    def load(self, file_path):
        import xlrd
        wb = xlrd.open_workbook(file_path)
        texts = []
        locations = []
        for si in range(wb.nsheets):
            ws = wb.sheet_by_index(si)
            for ri in range(ws.nrows):
                for ci in range(ws.ncols):
                    cell = ws.cell(ri, ci)
                    if cell.ctype != xlrd.XL_CELL_EMPTY:
                        t = str(cell.value).strip()
                        if t:
                            texts.append(t)
                            locations.append({"sheet": si, "row": ri, "col": ci})
        return make_segments_from_texts(texts, "Cell ", source_locations=locations)

    def render(self, original_path, segments, output_path):
        try:
            import xlrd
            from xlutils.copy import copy
        except ImportError:
            raise ImportError("xlutils is required to render .xls files. Install it with: pip install xlutils")
        rb = xlrd.open_workbook(original_path, formatting_info=True)
        wb = copy(rb)
        for seg in segments:
            loc = seg.get("source_location", {})
            if not loc:
                continue
            target = seg.get("target", "").strip()
            if not target:
                continue
            ws = wb.get_sheet(loc["sheet"])
            ws.write(loc["row"], loc["col"], target)
        wb.save(output_path)
