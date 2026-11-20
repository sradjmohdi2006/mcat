import os
import re
import shutil
import threading
import zipfile
from difflib import get_close_matches

from spylls.hunspell import Dictionary

DICTS_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "mcat", "dicts")
PERSONAL_DIC_DIR = os.path.join(DICTS_DIR, "personal")
PERSONAL_DIC_PATH = os.path.join(PERSONAL_DIC_DIR, "personal.dic")
PERSONAL_AFF_PATH = os.path.join(PERSONAL_DIC_DIR, "personal.aff")
WORD_RE = re.compile(r"\b[^\W\d_]+\b", re.UNICODE)


class SpellChecker:
    def __init__(self):
        self.dictionaries = []
        self._loaded_names = []
        self._custom_words = set()
        self._segment_index = {}
        self._lock = threading.RLock()
        os.makedirs(DICTS_DIR, exist_ok=True)
        os.makedirs(PERSONAL_DIC_DIR, exist_ok=True)
        self._load_personal_index()

    def auto_load(self):
        for name in os.listdir(DICTS_DIR):
            if name.lower() == "personal":
                continue
            dir_path = os.path.join(DICTS_DIR, name)
            if not os.path.isdir(dir_path):
                continue
            for f in os.listdir(dir_path):
                if f.endswith(".dic"):
                    base = os.path.join(dir_path, os.path.splitext(f)[0])
                    aff = base + ".aff"
                    if os.path.exists(aff):
                        try:
                            d = Dictionary.from_files(base)
                            self.dictionaries.append(d)
                            self._loaded_names.append(name)
                        except Exception:
                            pass
                    break

    def _lang_id_from_archive(self, archive_path):
        candidates = []
        with zipfile.ZipFile(archive_path) as z:
            for name in z.namelist():
                if name.endswith(".dic"):
                    base = os.path.splitext(os.path.basename(name))[0]
                    if "_" in base or "-" in base:
                        candidates.append(base)
        if not candidates:
            base = os.path.splitext(os.path.basename(archive_path))[0]
            return base.replace(" ", "_").lower()
        return candidates[0]

    def load_from_archive(self, archive_path):
        try:
            lang_id = self._lang_id_from_archive(archive_path)
        except Exception:
            return False
        target_dir = os.path.join(DICTS_DIR, lang_id)
        os.makedirs(target_dir, exist_ok=True)

        extracted = False
        with zipfile.ZipFile(archive_path) as z:
            for name in z.namelist():
                if name.endswith(".dic") or name.endswith(".aff"):
                    dest = os.path.join(target_dir, os.path.basename(name))
                    if not os.path.exists(dest):
                        with z.open(name) as src, open(dest, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                    extracted = True

        if not extracted:
            return False

        return self._load_from_dir(target_dir, lang_id)

    def load_dictionary(self, dic_path, aff_path=None):
        if aff_path is None:
            aff_path = os.path.splitext(dic_path)[0] + ".aff"
        if not os.path.exists(aff_path):
            return False

        base_name = os.path.splitext(os.path.basename(dic_path))[0]
        target_dir = os.path.join(DICTS_DIR, base_name)
        os.makedirs(target_dir, exist_ok=True)

        shutil.copy2(dic_path, os.path.join(target_dir, os.path.basename(dic_path)))
        shutil.copy2(aff_path, os.path.join(target_dir, os.path.basename(aff_path)))

        return self._load_from_dir(target_dir, base_name)

    def _load_from_dir(self, dir_path, name):
        if name in self._loaded_names:
            return True
        for f in os.listdir(dir_path):
            if f.endswith(".dic"):
                base = os.path.join(dir_path, os.path.splitext(f)[0])
                try:
                    d = Dictionary.from_files(base)
                    self.dictionaries.append(d)
                    self._loaded_names.append(name)
                    return True
                except Exception:
                    return False
        return False

    @property
    def has_dict(self):
        return len(self.dictionaries) > 0

    @property
    def loaded_names(self):
        return list(self._loaded_names)

    # ------------------------------------------------------------------
    # Learned index (custom Hunspell .dic + segment cache)
    # ------------------------------------------------------------------
    def _load_personal_index(self):
        """Restore learned words from the personal Hunspell dictionary."""
        if not os.path.exists(PERSONAL_DIC_PATH):
            self._write_personal_dic()
            return
        try:
            with open(PERSONAL_DIC_PATH, encoding="utf-8") as handle:
                lines = handle.read().splitlines()
            for line in lines[1:]:  # first line is the word count
                word = line.split("/", 1)[0].strip()
                if word:
                    self._custom_words.add(word.lower())
        except OSError:
            pass

    def _write_personal_dic(self):
        """Persist learned words so they survive a restart."""
        words = sorted(self._custom_words)
        try:
            if not os.path.exists(PERSONAL_AFF_PATH):
                with open(PERSONAL_AFF_PATH, "w", encoding="utf-8") as handle:
                    handle.write("SET UTF-8\n")
            with open(PERSONAL_DIC_PATH, "w", encoding="utf-8") as handle:
                handle.write(f"{len(words)}\n")
                for word in words:
                    handle.write(word + "\n")
        except OSError:
            pass

    @property
    def indexed_words(self):
        with self._lock:
            return sorted(self._custom_words)

    @property
    def indexed_segments(self):
        with self._lock:
            return dict(self._segment_index)

    def index_translation(self, source, target, previous_target=""):
        """Upsert a segment and its words into the learned index.

        The first translation of a segment inserts it.  Later edits replace
        the stored entry instead of adding a duplicate.  Words removed by a
        correction are dropped from the custom dictionary so the correction
        really replaces what was indexed.
        """
        with self._lock:
            errors = self._collect_errors(target or "", self._check_dicts)
            old_words = set(WORD_RE.findall(previous_target or ""))
            new_words = set(WORD_RE.findall(target or ""))
            for word in old_words - new_words:
                self._custom_words.discard(word.lower())
            for word in new_words:
                self._custom_words.add(word.lower())
            entry = {"target": target or "", "errors": errors}
            self._segment_index[source] = entry
            self._write_personal_dic()
            return dict(entry)

    def index_correction(self, source, old_word, new_word):
        """Replace one indexed word with its correction."""
        with self._lock:
            entry = self._segment_index.get(source, {})
            target = entry.get("target", "")
            pattern = r"\b" + re.escape(old_word) + r"\b"
            updated = re.sub(pattern, new_word, target, count=1)
            self._custom_words.discard(old_word.lower())
            if new_word:
                self._custom_words.add(new_word.lower())
            if source in self._segment_index:
                entry["target"] = updated
                entry["errors"] = self._collect_errors(updated, self._check_dicts)
            self._write_personal_dic()
            return updated

    # ------------------------------------------------------------------
    # Checking
    # ------------------------------------------------------------------
    def _check_dicts(self, word):
        if not self.dictionaries:
            return True
        for d in self.dictionaries:
            if d.lookup(word):
                return True
        return False

    def check(self, word):
        with self._lock:
            if word.lower() in self._custom_words:
                return True
        return self._check_dicts(word)

    def suggest(self, word):
        suggestions = set()
        for d in self.dictionaries:
            for s in d.suggest(word):
                suggestions.add(s)
        with self._lock:
            custom = list(self._custom_words)
        if custom:
            suggestions.update(get_close_matches(word.lower(), custom, n=8, cutoff=0.7))
        return sorted(suggestions)

    def _collect_errors(self, text, checker):
        if not text:
            return []
        errors = []
        seen = set()
        for word in WORD_RE.findall(text):
            if word.lower() in seen:
                continue
            if not checker(word):
                seen.add(word.lower())
                errors.append((word, self.suggest(word)))
        return errors

    def check_text(self, text):
        return self._collect_errors(text, self.check)
