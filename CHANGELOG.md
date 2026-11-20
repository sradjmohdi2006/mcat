# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Manual segmentation**:
  - New Project option **Segment this project manually** skips automatic segmentation and opens a Naming phase
  - Read-only document view for defining unit starts and ends on words or punctuation
  - `Set Unit Start` / `Set Unit End` via context menu, `Shift+F10`, Menu key, or keyboard shortcuts
  - `Split` commits marked units; `Split All` also creates units from every remaining gap (trimmed and split at block boundaries)
  - Finished segmentation is locked by default; **Edit Segmentation** warns before changing existing rows
  - Units, targets, and lock state persist in the project file so translations survive reopening
- **Translation memory and term base import**:
  - Import TMX translation units into the translation memory
  - Import TMX files into the glossary
  - Import TBX term bases into the glossary, with definitions and language detection
  - Batch import multiple TMX/TBX files at once, with an add/remove review list
  - Detect TMX files that contain only single-word entries and offer to store them as glossary terms instead of translation memory units
- **Optional Earth-observation data sources** (`eo_sources/`, see `EO_SOURCES.md`):
  - Copernicus Data Space Ecosystem: OData/STAC Sentinel-1 search, OAuth2 download, WMS/WMTS capabilities
  - NASA: APOD, EPIC, Earth imagery, Mars rover photos, GIBS capabilities, CMR metadata
  - Google Maps: geocoding, directions, elevation and time zone with XML output
  - Common XML layer that normalises JSON, XML and image-backed APIs into one document shape
- **Unified Search System** (`Ctrl+Shift+F`): Search across 4 sources simultaneously:
  - In-Memory segments (currently loaded file)
  - TM Sources (translation memory source segments)
  - TM Targets (translation memory target segments)
  - Glossary (terminology database with descriptions)
- **Fuzzy Matching**: RapidFuzz algorithms (ratio, token_sort_ratio, partial_ratio)
- **Semantic Search**: Vector embeddings via fastembed + sqlite-vec
- **Search Dialog**: Tabbed results, filters, language filtering, field selection
- **Glossary Search**: Search terms, translations, and descriptions
- **Search Integration**: Double-click to navigate (in-memory) or apply (TM/Glossary)

### Changed
- Updated SearchFetcher to accept both TM and Glossary database paths
- Enhanced SearchDialog with Glossary tab and field selectors
- Improved result display with color-coded scores and context labels

### Fixed
- Various UI improvements and bug fixes

## [1.0.0] - 2024-01-15

### Added
- Initial release
- Multi-format support (PO, XLIFF, MQXLIFF, SDLXLIFF, TMX, TS, CSV, TXT, PDF, DOCX, PPTX, XLSX, ODT, ODS, ODP)
- Translation Memory with fuzzy matching
- Glossary/Terminology management with collections
- Project management (native, OmegaT, memoQ)
- Quality Assurance checks
- Spell checking (Hunspell)
- Dark theme UI
- Keyboard shortcuts
- Tag handling
- Chapter/Bookmark view
- Windows installer (Inno Setup)