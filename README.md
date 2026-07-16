# mcat — Multi-Format CAT Tool

A desktop computer-assisted translation (CAT) tool with support for multiple file formats, translation memory, glossary management, spell checking, and quality assurance.

## Features

- **File formats**: PO, XLIFF (memoQ mqxliff, SDL Trados sdlxliff), TXT, DOCX, XLSX, PPTX, ODT, PDF, mcat.db
- **Translation Memory**: Fuzzy matching with configurable threshold
- **Glossary**: Term management with TMX import/export
- **QA Checks**: Missing translations, tag mismatch, number mismatch, inconsistent translations, terminology, whitespace
- **Spell Checking**: Hunspell-based with auto-downloading dictionaries
- **Segmentation**: Customizable sentence segmentation rules

## Installation

Download `mcat_setup.exe` from the [latest release](https://github.com/sradjmohdi2006/mcat/releases/latest) and run the installer.

### From source

```bash
pip install -r requirements.txt
python mcat.py
```

## Build

```bash
pyinstaller -y mcat.spec
```

## Tests

```bash
python -m pytest tests/ -v
```

## Usage

```bash
mcat.py [file-to-translate]
```

## Supported Formats

| Format | Extension | Handler |
|--------|-----------|---------|
| PO file | `.po` | Gettext PO |
| memoQ XLIFF | `.mqxliff` | MqxliffHandler |
| SDL Trados XLIFF | `.sdlxliff` | SdlxliffHandler |
| Plain text | `.txt` | TextHandler |
| Word document | `.docx` | DocxHandler |
| Excel spreadsheet | `.xlsx` | XlsxHandler |
| PowerPoint | `.pptx` | PptxHandler |
| OpenDocument | `.odt`, `.ods`, `.odp` | OdfHandler |
| PDF | `.pdf` | PdfHandler |
| mcat database | `.mcat.db` | McatDbHandler |

## License

See [EULA.txt](EULA.txt).
