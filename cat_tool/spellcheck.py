import os
import re
import shutil
import zipfile
from spylls.hunspell import Dictionary

DICTS_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "mcat", "dicts")


class SpellChecker:
    def __init__(self):
        self.dictionaries = []
        self._loaded_names = []
        os.makedirs(DICTS_DIR, exist_ok=True)

    def auto_load(self):
        for name in os.listdir(DICTS_DIR):
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
        lang_id = self._lang_id_from_archive(archive_path)
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

    def check(self, word):
        if not self.dictionaries:
            return True
        for d in self.dictionaries:
            if d.lookup(word):
                return True
        return False

    def suggest(self, word):
        suggestions = set()
        for d in self.dictionaries:
            for s in d.suggest(word):
                suggestions.add(s)
        return sorted(suggestions)

    def check_text(self, text):
        words = re.findall(r"\b[^\W\d_]+\b", text, re.UNICODE)
        errors = []
        seen = set()
        for word in words:
            if word.lower() in seen:
                continue
            if not self.check(word):
                seen.add(word.lower())
                errors.append((word, self.suggest(word)))
        return errors
