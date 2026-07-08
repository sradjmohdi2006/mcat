import json
import os

SETTINGS_FILE = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "mcat", "settings.json")

DEFAULTS = {
    "source_font_size": 13,
    "target_font_size": 13,
    "auto_save_on_segment_change": False,
    "fuzzy_match_min_score": 40.0,
    "show_tag_placeholders": True,
}


class AppSettings:
    def __init__(self):
        self._data = dict(DEFAULTS)

    def load(self):
        try:
            with open(SETTINGS_FILE, encoding="utf-8") as f:
                stored = json.load(f)
            self._data = {**DEFAULTS, **stored}
        except (FileNotFoundError, json.JSONDecodeError):
            self._data = dict(DEFAULTS)
        return self

    def save(self):
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def __contains__(self, key):
        return key in self._data

    def get(self, key, default=None):
        return self._data.get(key, default)

    def as_dict(self):
        return dict(self._data)
