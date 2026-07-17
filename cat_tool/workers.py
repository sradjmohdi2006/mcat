from PyQt5.QtCore import QObject, pyqtSignal


class SegmentationWorker(QObject):
    finished = pyqtSignal(list, str)
    error = pyqtSignal(str)
    chunk_ready = pyqtSignal(list, int, str)

    def __init__(self):
        super().__init__()
        self._file_path = None

    def load_file(self, file_path):
        self._file_path = file_path
        try:
            from cat_tool.file_handler import CATFileHandler
            handler = CATFileHandler()
            segments = handler.load_file(file_path)
            self._emit_chunks(segments, file_path)
            self.finished.emit(segments, file_path)
        except Exception as e:
            self.error.emit(str(e))

    def open_project_source(self, index, project):
        try:
            segments, label, ok, error = project.open_project_source_file(index)
            if not ok:
                self.error.emit(error or "Unknown error opening source file")
                return
            self._emit_chunks(segments, label)
            self.finished.emit(segments, label)
        except Exception as e:
            self.error.emit(str(e))

    def _emit_chunks(self, segments, label):
        chunk_size = 10
        for i in range(0, len(segments), chunk_size):
            chunk = segments[i:i + chunk_size]
            self.chunk_ready.emit(chunk, i + len(chunk), label)


class EmbeddingWorker(QObject):
    finished = pyqtSignal(int)
    error = pyqtSignal(str, int)

    def __init__(self, db_path):
        super().__init__()
        self.db_path = db_path
        self._tm = None

    def _get_tm(self):
        if self._tm is None:
            from cat_tool.tm import TranslationMemory
            self._tm = TranslationMemory(self.db_path)
        return self._tm

    def unload_model(self):
        if self._tm is not None:
            self._tm.unload_model()

    def add_embedding(self, source, row_id):
        try:
            tm = self._get_tm()
            tm._add_embedding_for_row(source, row_id)
            self.finished.emit(row_id)
        except Exception as e:
            self.error.emit(str(e), row_id)


class FuzzyMatchWorker(QObject):
    finished = pyqtSignal(list)

    def __init__(self, db_path):
        super().__init__()
        self.db_path = db_path

    def find_matches(self, source_text, source_lang, target_lang, min_score=40.0, limit=5):
        try:
            from cat_tool.tm import TranslationMemory
            tm = TranslationMemory(self.db_path)
            matches = tm.get_fuzzy_matches(
                source_text, min_score=min_score, limit=limit,
                source_lang=source_lang, target_lang=target_lang
            )
            self.finished.emit(matches)
        except Exception:
            self.finished.emit([])
