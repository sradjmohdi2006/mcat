import json
import os
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime


RECENT_FILE = "recent_projects.json"


class Project:
    def __init__(self):
        self.name = ""
        self.source_lang = ""
        self.target_lang = ""
        self.source_files = []
        self.file_path = None
        self.created_at = ""
        self.modified_at = ""

    @staticmethod
    def default_dir():
        d = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "mcat")
        os.makedirs(d, exist_ok=True)
        return d

    def new(self, name, source_lang, target_lang, source_files):
        now = datetime.now().isoformat()
        self.name = name
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.source_files = list(source_files)
        self.file_path = None
        self.created_at = now
        self.modified_at = now

    def to_dict(self):
        return {
            "version": 1,
            "name": self.name,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "source_files": self.source_files,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
        }

    @staticmethod
    def from_dict(data, file_path=None):
        p = Project()
        p.name = data.get("name", "")
        p.source_lang = data.get("source_lang", "")
        p.target_lang = data.get("target_lang", "")
        p.source_files = data.get("source_files", [])
        p.file_path = file_path
        p.created_at = data.get("created_at", "")
        p.modified_at = data.get("modified_at", "")
        return p

    def save(self, file_path=None):
        if file_path:
            self.file_path = file_path
        if not self.file_path:
            raise ValueError("No file path set for project save")
        self.modified_at = datetime.now().isoformat()
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        return self.file_path

    @staticmethod
    def load(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Project.from_dict(data, file_path)

    @staticmethod
    def get_recent():
        path = os.path.join(Project.default_dir(), RECENT_FILE)
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    @staticmethod
    def add_recent(file_path, name):
        recents = Project.get_recent()
        recents = [r for r in recents if r.get("path") != file_path]
        recents.insert(0, {"path": file_path, "name": name, "opened": datetime.now().isoformat()})
        recents = recents[:10]
        path = os.path.join(Project.default_dir(), RECENT_FILE)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(recents, f, indent=2)
        except Exception:
            pass

    def save_as_omegat(self, dir_path):
        self.modified_at = datetime.now().isoformat()
        os.makedirs(dir_path, exist_ok=True)
        src_dir = os.path.join(dir_path, "source")
        tgt_dir = os.path.join(dir_path, "target")
        tm_dir = os.path.join(dir_path, "tm")
        glos_dir = os.path.join(dir_path, "glossary")
        for d in (src_dir, tgt_dir, tm_dir, glos_dir):
            os.makedirs(d, exist_ok=True)

        for f in self.source_files:
            if os.path.exists(f):
                shutil.copy2(f, os.path.join(src_dir, os.path.basename(f)))

        root = ET.Element("omegat")
        proj_el = ET.SubElement(root, "project")
        ET.SubElement(proj_el, "source_lang").text = self.source_lang.upper()
        ET.SubElement(proj_el, "target_lang").text = self.target_lang.upper()
        ET.SubElement(proj_el, "source_dir").text = "source"
        ET.SubElement(proj_el, "target_dir").text = "target"
        ET.SubElement(proj_el, "tm_dir").text = "tm"
        ET.SubElement(proj_el, "glossary_dir").text = "glossary"
        tree = ET.ElementTree(root)
        tree.write(os.path.join(dir_path, "omegat.project"), encoding="utf-8", xml_declaration=True)

    @staticmethod
    def load_omegat(dir_path):
        proj_file = os.path.join(dir_path, "omegat.project")
        if not os.path.exists(proj_file):
            raise FileNotFoundError(f"Not an OmegaT project: {dir_path}")
        tree = ET.parse(proj_file)
        root = tree.getroot()
        pe = root.find("project")
        if pe is None:
            raise ValueError("Invalid omegat.project: missing <project> element")

        p = Project()
        p.name = os.path.basename(dir_path)
        p.file_path = dir_path
        p.created_at = datetime.now().isoformat()
        p.modified_at = datetime.now().isoformat()

        raw_sl = (pe.findtext("source_lang") or "").strip()
        raw_tl = (pe.findtext("target_lang") or "").strip()
        p.source_lang = raw_sl.lower()
        p.target_lang = raw_tl.lower()

        source_dir_name = (pe.findtext("source_dir") or "source").strip()
        source_dir = os.path.join(dir_path, source_dir_name)
        p.source_files = []
        if os.path.isdir(source_dir):
            for entry in sorted(os.listdir(source_dir)):
                full = os.path.join(source_dir, entry)
                if os.path.isfile(full):
                    p.source_files.append(full)
        return p

    def save_as_memoq(self, dir_path, handler):
        self.modified_at = datetime.now().isoformat()
        os.makedirs(dir_path, exist_ok=True)
        src_dir = os.path.join(dir_path, "source")
        tgt_dir = os.path.join(dir_path, "target")
        os.makedirs(src_dir, exist_ok=True)
        os.makedirs(tgt_dir, exist_ok=True)

        for f in self.source_files:
            if os.path.exists(f):
                shutil.copy2(f, os.path.join(src_dir, os.path.basename(f)))

        manifest = ET.Element("memoQProject")
        ET.SubElement(manifest, "name").text = self.name
        ET.SubElement(manifest, "source_lang").text = self.source_lang
        ET.SubElement(manifest, "target_lang").text = self.target_lang
        ET.SubElement(manifest, "created_at").text = self.created_at
        ET.SubElement(manifest, "modified_at").text = self.modified_at
        ET.SubElement(manifest, "tool").text = "mcat"
        ET.indent(manifest)
        tree = ET.ElementTree(manifest)
        tree.write(os.path.join(dir_path, "manifest.xml"), encoding="utf-8", xml_declaration=True)

        mqxliff_path = os.path.join(tgt_dir, f"{self.name}.mqxliff")
        handler.save_as_mqxliif(mqxliff_path, self.source_lang, self.target_lang)

    @staticmethod
    def load_memoq(dir_path):
        manifest_file = os.path.join(dir_path, "manifest.xml")
        if not os.path.exists(manifest_file):
            raise FileNotFoundError(f"Not a memoQ project: {dir_path}")

        tree = ET.parse(manifest_file)
        root = tree.getroot()
        p = Project()
        p.name = (root.findtext("name") or "").strip()
        p.file_path = dir_path
        p.source_lang = (root.findtext("source_lang") or "en").strip()
        p.target_lang = (root.findtext("target_lang") or "es").strip()
        p.created_at = root.findtext("created_at") or ""
        p.modified_at = root.findtext("modified_at") or ""

        src_dir = os.path.join(dir_path, "source")
        p.source_files = []
        if os.path.isdir(src_dir):
            for entry in sorted(os.listdir(src_dir)):
                full = os.path.join(src_dir, entry)
                if os.path.isfile(full):
                    p.source_files.append(full)

        tgt_dir = os.path.join(dir_path, "target")
        p.mqxliff_files = []
        if os.path.isdir(tgt_dir):
            for entry in sorted(os.listdir(tgt_dir)):
                if entry.endswith(".mqxliff"):
                    p.mqxliff_files.append(os.path.join(tgt_dir, entry))

        return p

    def __str__(self):
        return f"Project({self.name}, {self.source_lang}->{self.target_lang}, files={len(self.source_files)})"
