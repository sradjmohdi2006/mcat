# mcat - Modern Computer-Aided Translation Tool

A powerful, open-source CAT (Computer-Aided Translation) tool built with Python and PyQt5. Designed for professional translators and localization teams.

![mcat Screenshot](docs/screenshot.png)

## Features

### Core Translation Features
- **Multi-format Support**: PO, XLIFF, MQXLIFF, SDLXLIFF, TMX, TS, CSV, TXT, PDF, DOCX, PPTX, XLSX, ODT, ODS, ODP
- **Translation Memory (TM)**: SQLite-based with fuzzy matching (rapidfuzz) and semantic search (fastembed + sqlite-vec)
- **Glossary/Terminology Management**: SQLite-based with collections, TMX import/export
- **Segmentation**: Language-aware segmentation rules (SRX-compatible)
- **Quality Assurance**: Built-in QA checks (terminology, consistency, formatting, numbers, etc.)
- **Spell Checking**: Hunspell integration with multi-language support

### Advanced Search (New!)
- **Unified Search** across 4 sources:
  - **In-Memory**: Currently loaded file segments
  - **TM Sources**: Translation memory source segments
  - **TM Targets**: Translation memory target (translated) segments
  - **Glossary**: Terminology database (source terms, translations, descriptions)
- **Fuzzy Matching**: RapidFuzz (ratio, token_sort_ratio, partial_ratio)
- **Semantic Search**: Vector embeddings via fastembed + sqlite-vec
- **Language Filtering**: Filter by source/target language
- **Real-time Results**: Debounced live search with tabbed results

### Project Management
- **Project Formats**: Native (.mcatproj), OmegaT, memoQ import/export
- **Recent Projects**: Quick access to recent projects
- **Multiple Source Files**: Manage multiple source files per project

### User Interface
- **Dark Theme**: Modern, eye-friendly dark UI
- **Keyboard Shortcuts**: Full shortcut support (customizable)
- **Split View**: Source/Target side-by-side editing
- **Sidebars**: TM fuzzy matches, Glossary matches, Terminology
- **Chapter/Bookmark View**: PDF outlines, DOCX headings
- **Tag Handling**: Inline tag protection and insertion

## Installation

### Windows (Recommended)
Download the latest installer from [Releases](https://github.com/yourusername/mcat/releases).

### From Source
```bash
# Clone the repository
git clone https://github.com/yourusername/mcat.git
cd mcat

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Run
python mcat.py
```

### Requirements
- Python 3.10+
- PyQt5
- rapidfuzz
- fastembed
- sqlite-vec (with vec0 extension)
- spylls (for spell checking)
- python-docx, openpyxl, pptx, pymupdf (for document formats)

See `requirements.txt` for complete list.

## Quick Start

1. **Create a Project**: `Ctrl+N` → New Project → Set name, languages, add source files
2. **Open a File**: `Ctrl+O` → Select translation file (PO, XLIFF, MQXLIFF, etc.)
3. **Translate**: Use `Ctrl+Enter` to confirm and move to next segment
4. **Search**: `Ctrl+Shift+F` → Search across memory, TM, and glossary
5. **TM Match**: Double-click TM suggestion in sidebar or search results to apply
6. **Glossary**: `Ctrl+G` to add terms, `Ctrl+Shift+G` to manage
7. **Render**: `Ctrl+R` to generate translated output file

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+N` | New Project |
| `Ctrl+Shift+O` | Open Project |
| `Ctrl+O` | Open File |
| `Ctrl+S` | Save File |
| `Ctrl+Shift+S` | Save Project |
| `Ctrl+R` | Render Translated File |
| `Ctrl+Enter` | Confirm & Next Segment |
| `Ctrl+Down/Up` | Next/Previous Segment |
| `Ctrl+U` | Next Untranslated |
| `Ctrl+F` | Toggle Fuzzy |
| `Ctrl+G` | Add Glossary Term |
| `Ctrl+Shift+G` | View/Manage Glossary |
| `Ctrl+Shift+F` | **Unified Search (NEW!)** |
| `Ctrl+M` | Import PO into TM |
| `Ctrl+Shift+Q` | Quality Assurance |
| `F7` | Spell Check |
| `F1` / `Ctrl+Shift+H` | Keyboard Shortcuts |

## Unified Search Guide

Press `Ctrl+Shift+F` to open the Search dialog.

### Search Sources
- **In-Memory**: Currently loaded file segments
- **TM Sources**: Source segments in translation memory
- **TM Targets**: Translated segments in translation memory
- **Glossary**: Terminology entries (terms, translations, descriptions)

### Match Types
- **Fuzzy** (default): RapidFuzz string similarity
- **Semantic**: Vector embedding similarity (requires embedding model)

### Filters
- **Min Score**: 0-100% threshold
- **Max Results**: 10-500
- **Languages**: Filter by source/target language
- **Fields**: Choose which fields to search (source, target, description, etc.)

### Results
- **All Results tab**: Combined results from all sources, sorted by score
- **Source-specific tabs**: In-Memory, TM Sources, TM Targets, Glossary
- **Color-coded scores**: Green ≥90%, Orange ≥70%, Yellow <70%
- **Actions**: Double-click to navigate (in-memory) or apply (TM/Glossary)

## Building from Source

### Windows Executable (PyInstaller)
```bash
# Install PyInstaller
pip install pyinstaller

# Build
pyinstaller mcat.spec

# Output: dist/mcat/mcat.exe
```

### Installer (Inno Setup)
```bash
# Requires Inno Setup 6+
iscc setup.iss

# Output: mcat_setup.exe
```

## Project Structure

```
mcat/
├── mcat.py                 # Entry point
├── mcat.spec               # PyInstaller spec
├── setup.iss               # Inno Setup script
├── requirements.txt        # Python dependencies
├── README.md               # This file
├── cat_tool/               # Main package
│   ├── ui.py               # Main window & UI
│   ├── state_manager.py    # Application state
│   ├── tm.py               # Translation Memory
│   ├── glossary.py         # Glossary/Terminology
│   ├── project.py          # Project management
│   ├── file_handler.py     # File I/O abstraction
│   ├── segmentation.py     # Segmentation rules
│   ├── search_fetcher.py   # Unified search engine (NEW!)
│   ├── suggest.py          # Auto-complete/suggestions
│   ├── qa.py               # Quality Assurance
│   ├── spellcheck.py       # Spell checking
│   ├── workers.py          # Background threads
│   ├── settings.py         # Application settings
│   ├── formats/            # File format handlers
│   │   ├── mcatdb.py       # Native format
│   │   ├── po.py           # PO/POT
│   │   ├── xliff.py        # XLIFF
│   │   ├── mqxliff.py      # memoQ XLIFF
│   │   ├── sdlxliff.py     # SDL Trados XLIFF
│   │   ├── tmx.py          # TMX
│   │   ├── ts.py           # Qt TS
│   │   ├── pdf.py          # PDF
│   │   ├── docx.py         # Word
│   │   ├── pptx.py         # PowerPoint
│   │   ├── xlsx.py         # Excel
│   │   └── factory.py      # Format factory
│   └── dialogs/            # Dialog windows
│       ├── search_dialog.py    # Unified search (NEW!)
│       ├── view_dialogs.py     # Chapter view, tags, shortcuts
│       ├── glossary_dialogs.py # Glossary management
│       ├── project_dialogs.py  # Project creation/settings
│       ├── spellcheck_dialog.py
│       └── settings_dialog.py
├── tests/                  # Test suite
└── dist/                   # Build output (gitignored)
```

## Configuration

### Data Directory
- Windows: `%APPDATA%\mcat\`
  - `translation_memory.db` - TM database
  - `glossary.db` - Glossary database
  - `settings.json` - Application settings
  - `recent_projects.json` - Recent projects list
  - `segmentation_rules/` - Custom SRX rules

### Settings (Tools → Options)
- Font sizes (source/target)
- TM fuzzy threshold
- Auto-save interval
- Spell check language
- Segmentation rules

## Translation Memory Details

### Database Schema
```sql
CREATE TABLE translation_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT UNIQUE,
    target TEXT,
    source_lang TEXT DEFAULT '',
    target_lang TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Vector embeddings for semantic search (sqlite-vec)
CREATE VIRTUAL TABLE vec_embeddings USING vec0(
    embedding int8[384] distance_metric=cosine
);
```

### Matching Algorithms
1. **Exact Match**: 100% - Identical source text
2. **Fuzzy Match**: 30-99% - RapidFuzz algorithms
   - `ratio`: Levenshtein similarity
   - `token_sort_ratio`: Token-order-independent
   - `partial_ratio`: Best substring match
3. **Semantic Match**: Cosine similarity of embeddings
   - Model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
   - 384 dimensions, int8 quantized for sqlite-vec

## Glossary Details

### Database Schema
```sql
CREATE TABLE glossary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_term TEXT UNIQUE,
    target_translation TEXT,
    description TEXT,
    source_lang TEXT DEFAULT '',
    target_lang TEXT DEFAULT ''
);

CREATE TABLE collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    description TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE collection_terms (
    collection_id INTEGER,
    term_source TEXT,
    PRIMARY KEY (collection_id, term_source),
    FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE
);
```

### Collections
Organize terms into named collections (e.g., "Legal", "Medical", "UI Strings")
- Import/export collections as TMX
- Filter glossary matches by collection

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

### Development Setup
```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=cat_tool --cov-report=html
```

### Code Style
- Follow PEP 8
- Type hints encouraged
- Docstrings for public methods
- Run `black cat_tool/` before committing

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [rapidfuzz](https://github.com/maxbachmann/rapidfuzz) - Fast string matching
- [fastembed](https://github.com/qdrant/fastembed) - Fast embedding generation
- [sqlite-vec](https://github.com/asg017/sqlite-vec) - Vector search in SQLite
- [spylls](https://github.com/spylls/spylls) - Pure Python Hunspell
- [PyQt5](https://www.riverbankcomputing.com/software/pyqt/) - GUI framework
- [translate-toolkit](https://toolkit.translatehouse.org/) - Translation file formats

## Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/mcat/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/mcat/discussions)
- **Wiki**: [GitHub Wiki](https://github.com/yourusername/mcat/wiki)

---

**mcat** - Making Computer-Aided Translation accessible to everyone.